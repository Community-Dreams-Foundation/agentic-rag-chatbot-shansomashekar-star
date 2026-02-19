"""
Set protobuf to pure-Python impl before any transformers import.
Avoids 'FieldDescriptor' has no attribute 'is_repeated' with protobuf 5.x.
"""
import os
if "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION" not in os.environ:
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import asyncio
import json
import logging
import pickle
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager

import aiofiles
from typing import Optional
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth.middleware import get_current_user, get_optional_user, get_user_from_token_or_header
from app.auth.router import router as auth_router
from app.config import settings
from app.core.cache import query_cache
from app.core.ingest import ingest_document
from app.core.memory import extract_and_store_memory
from app.core.retriever import ask_stream
from app.core.sandbox import get_agent_executor
from app.db import delete_document_chunks, get_chunk_count_for_user, get_db, get_documents_for_user, init_schema
from app.schemas import AnalyzeRequest, AnalyzeResponse

logger = logging.getLogger(__name__)
VERSION = "3.0"
MAX_MB = settings.max_upload_mb
SUPPORTED = set(settings.supported_types.split(","))
user_locks: dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


@asynccontextmanager
async def lifespan(app):
    os.makedirs("data", exist_ok=True)
    os.makedirs("vectorstore", exist_ok=True)
    os.makedirs("memory", exist_ok=True)
    os.makedirs("artifacts", exist_ok=True)
    conn = await get_db()
    try:
        await init_schema(conn)
    finally:
        await conn.close()

    app.state.graph_store = {}
    for name in os.listdir("vectorstore"):
        if name.startswith("user_") and os.path.isdir(os.path.join("vectorstore", name)):
            graph_path = os.path.join("vectorstore", name, "knowledge_graph.pkl")
            if os.path.exists(graph_path):
                try:
                    with open(graph_path, "rb") as f:
                        import pickle
                        G = pickle.load(f)
                    user_id = name.replace("user_", "")
                    app.state.graph_store[user_id] = G
                except Exception:
                    pass

    app.state.reranker = None
    if not settings.sanity_mock:
        try:
            from langchain_community.cross_encoders import HuggingFaceCrossEncoder
            app.state.reranker = HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception as e:
            logger.warning("Cross-encoder not loaded: %s", e)

    yield
    for lock in user_locks.values():
        pass


app = FastAPI(title="Agentic RAG Chatbot", version=VERSION, lifespan=lifespan)
app.include_router(auth_router)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc), "type": type(exc).__name__})


static_dir = os.path.join(os.path.dirname(__file__), "static")
react_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
react_index = os.path.join(react_dist, "index.html")

if os.path.exists(react_index):
    app.mount("/assets", StaticFiles(directory=os.path.join(react_dist, "assets")), name="assets")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.get("/")
async def index(request: Request):
    if os.path.exists(react_index):
        return FileResponse(react_index)
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": "ollama", "version": VERSION}


@app.get("/ask")
async def ask_stream_route(
    request: Request,
    query: str,
    token: str = "",
    filter_source: Optional[str] = None,
    filter_section: Optional[str] = None,
    filter_page: Optional[int] = None,
    user=Depends(get_user_from_token_or_header),
):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Empty query")

    user_id = user["id"]
    conn = await get_db()
    try:
        count = await get_chunk_count_for_user(conn, user_id)
    finally:
        await conn.close()

    if count == 0:
        raise HTTPException(status_code=503, detail={"error": "No documents indexed yet", "action": "upload_first"})

    graph_store = getattr(request.app.state, "graph_store", {})
    reranker = getattr(request.app.state, "reranker", None)

    async def event_gen():
        try:
            result = await ask_stream(
                user_id,
                query,
                filter_source=filter_source,
                filter_section=filter_section,
                filter_page=filter_page,
                graph_store=graph_store,
                reranker_model=reranker,
            )
            if result.get("cached"):
                yield f"data: {json.dumps({'type': 'cached', 'answer': result['answer'], 'citations': result['citations']})}\n\n"
                mem = await extract_and_store_memory(user_id, query, result["answer"])
                yield f"data: {json.dumps({'type': 'memory', 'data': mem})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'token', 'text': result['answer']})}\n\n"
                yield f"data: {json.dumps({'type': 'citations', 'data': result['citations']})}\n\n"
                mem = await extract_and_store_memory(user_id, query, result["answer"])
                yield f"data: {json.dumps({'type': 'memory', 'data': mem})}\n\n"
        except Exception as e:
            logger.exception("Ask failed: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail={"error": "Unsupported type", "supported_types": list(SUPPORTED), "max_size_mb": MAX_MB},
        )

    job_id = str(uuid.uuid4())
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            temp_path = tmp.name
            size = 0
            while chunk := await file.read(8192):
                size += len(chunk)
                if size > MAX_MB * 1024 * 1024:
                    os.remove(temp_path)
                    raise HTTPException(status_code=413, detail={"error": f"File too large (max {MAX_MB}MB)"})
                tmp.write(chunk)

        lock = _get_user_lock(user["id"])
        async with lock:
            graph_store = getattr(request.app.state, "graph_store", {})
            result = await ingest_document(user["id"], temp_path, file.filename, graph_store=graph_store)
        await query_cache.invalidate_user(user["id"])
        return {"job_id": job_id, "doc_id": result["doc_id"], "filename": result["filename"], "chunks": result["chunks"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail={"error": str(e)[:200]})
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@app.get("/documents")
async def list_docs(user=Depends(get_current_user)):
    conn = await get_db()
    try:
        docs = await get_documents_for_user(conn, user["id"])
        return docs
    finally:
        await conn.close()


@app.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, user=Depends(get_current_user)):
    conn = await get_db()
    try:
        n = await delete_document_chunks(conn, user["id"], doc_id)
        if n == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        await query_cache.invalidate_user(user["id"])
        faiss_dir = f"vectorstore/user_{user['id']}"
        bm25_path = os.path.join(faiss_dir, "bm25_corpus.pkl")
        if os.path.exists(bm25_path):
            async with aiofiles.open(bm25_path, "rb") as f:
                chunks = pickle.loads(await f.read())
            remaining = [c for c in chunks if c.metadata.get("doc_id") != doc_id]
            async with aiofiles.open(bm25_path, "wb") as f:
                await f.write(pickle.dumps(remaining))
            if not remaining:
                for p in [faiss_dir + "/faiss_index", faiss_dir + "/faiss_index.pkl"]:
                    if os.path.exists(p):
                        os.remove(p)
            else:
                from langchain_community.vectorstores import FAISS
                from langchain_ollama import OllamaEmbeddings
                emb = OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)
                store = await asyncio.to_thread(FAISS.from_documents, remaining, emb)
                await asyncio.to_thread(store.save_local, os.path.join(faiss_dir, "faiss_index"))
        return {"status": "deleted", "doc_id": doc_id}
    finally:
        await conn.close()


@app.get("/memory")
async def get_memory(user=Depends(get_current_user)):
    mem_dir = f"memory/user_{user['id']}"
    user_mem, company_mem = "", ""
    for name, target_key in [("USER_MEMORY.md", "user_memory"), ("COMPANY_MEMORY.md", "company_memory")]:
        path = os.path.join(mem_dir, name)
        if os.path.exists(path):
            async with aiofiles.open(path, "r") as f:
                content = await f.read()
                if target_key == "user_memory":
                    user_mem = content
                else:
                    company_mem = content
    return {"user_memory": user_mem, "company_memory": company_mem}


@app.get("/memory/insights")
async def get_memory_insights(user=Depends(get_current_user)):
    from app.core.memory import get_memory_insights as _get_insights
    insights = await _get_insights(user["id"])
    return {"insights": insights}


@app.delete("/memory/{target}")
async def delete_memory(target: str, user=Depends(get_current_user)):
    if target not in ("USER_MEMORY", "COMPANY_MEMORY"):
        raise HTTPException(status_code=400, detail="target must be USER_MEMORY or COMPANY_MEMORY")
    mem_dir = f"memory/user_{user['id']}"
    filename = f"{target}.md"
    path = os.path.join(mem_dir, filename)
    if os.path.exists(path):
        os.remove(path)
    return {"status": "cleared", "target": target}


@app.get("/graph/entities")
async def graph_entities(request: Request, user=Depends(get_current_user)):
    graph_store = getattr(request.app.state, "graph_store", {})
    G = graph_store.get(user["id"])
    if not G or G.number_of_nodes() == 0:
        return []
    entities = []
    for node in G.nodes():
        data = G.nodes[node]
        degree = G.degree(node)
        entities.append({
            "id": node,
            "label": data.get("label", node),
            "type": data.get("type", "concept"),
            "doc_sources": list(set(data.get("doc_sources", []))),
            "degree": degree,
        })
    entities.sort(key=lambda e: e["degree"], reverse=True)
    return entities


@app.get("/graph/neighbors/{entity_id:path}")
async def graph_neighbors(request: Request, entity_id: str, user=Depends(get_current_user)):
    graph_store = getattr(request.app.state, "graph_store", {})
    G = graph_store.get(user["id"])
    if not G or not G.has_node(entity_id):
        return []
    neighbors = []
    for n in G.neighbors(entity_id):
        data = G[entity_id][n]
        node_data = G.nodes[n]
        neighbors.append({
            "id": n,
            "label": node_data.get("label", n),
            "type": node_data.get("type", "concept"),
            "relation": data.get("relation", "related_to"),
            "weight": data.get("weight", 1),
        })
    return neighbors


@app.get("/graph/full")
async def graph_full(request: Request, user=Depends(get_current_user)):
    """Returns nodes and edges for D3 force-directed graph."""
    graph_store = getattr(request.app.state, "graph_store", {})
    G = graph_store.get(user["id"])
    if not G or G.number_of_nodes() == 0:
        return {"nodes": [], "edges": []}
    nodes = []
    for n in G.nodes():
        d = G.nodes[n]
        nodes.append({
            "id": n,
            "label": d.get("label", n),
            "type": d.get("type", "concept"),
            "degree": G.degree(n),
        })
    edges = []
    seen = set()
    for u, v, data in G.edges(data=True):
        key = (min(u, v), max(u, v))
        if key not in seen:
            seen.add(key)
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", "related_to"),
                "weight": data.get("weight", 1),
            })
    return {"nodes": nodes, "edges": edges}


@app.get("/graph/stats")
async def graph_stats(request: Request, user=Depends(get_current_user)):
    graph_store = getattr(request.app.state, "graph_store", {})
    G = graph_store.get(user["id"])
    if not G or G.number_of_nodes() == 0:
        return {"nodes": 0, "edges": 0, "density": 0.0, "top_entities": []}
    n, m = G.number_of_nodes(), G.number_of_edges()
    density = (2 * m) / (n * (n - 1)) if n > 1 else 0.0
    top = sorted(G.nodes(), key=lambda x: G.degree(x), reverse=True)[:10]
    top_entities = [{"id": x, "label": G.nodes[x].get("label", x), "degree": G.degree(x)} for x in top]
    return {"nodes": n, "edges": m, "density": round(density, 4), "top_entities": top_entities}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, user=Depends(get_current_user)):
    try:
        agent = get_agent_executor()
        out = agent.invoke({"input": req.request})
        return AnalyzeResponse(result=out.get("output", str(out)))
    except Exception as e:
        logger.exception("Analyze failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
