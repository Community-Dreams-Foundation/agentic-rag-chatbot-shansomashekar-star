import asyncio
import os
import pickle
import re
import uuid
from typing import List, Optional, Tuple

import aiofiles
import fitz
import nltk
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from nltk.tokenize import sent_tokenize

from app.config import settings
from app.db import get_db, insert_chunks, insert_document

nltk.download("punkt_tab", quiet=True)


def _strip_injection(text: str) -> str:
    for p in ["<system>", "</system>", "</context>", "IGNORE PREVIOUS", "ignore previous"]:
        text = text.replace(p, "")
    return text


def extract_sections_pdf(path: str) -> List[dict]:
    doc = fitz.open(path)
    sections: List[dict] = []
    current: dict = {"heading": "Introduction", "text": "", "page": 1}
    body_size: Optional[float] = None

    for page_num, page in enumerate(doc, 1):
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text, size = span["text"].strip(), span["size"]
                    if not text:
                        continue
                    if body_size is None:
                        body_size = size
                    is_heading = (
                        size >= body_size * 1.2
                        and len(text) < 120
                        and len(text) > 0
                        and text[0].isupper()
                        and not text.endswith(".")
                    )
                    if is_heading:
                        if current["text"].strip():
                            sections.append(dict(current))
                        current = {"heading": text, "text": "", "page": page_num}
                    else:
                        current["text"] += " " + text

    if current["text"].strip():
        sections.append(current)
    doc.close()
    return sections


def extract_sections_text(text: str) -> List[dict]:
    pattern = re.compile(r"^(#{1,4} .+|.+\n[=\-]{3,})", re.MULTILINE)
    positions = [(m.start(), m.group()) for m in pattern.finditer(text)]
    if not positions:
        return [{"heading": "Document", "text": text, "page": None}]

    sections = []
    for i, (pos, heading) in enumerate(positions):
        start = pos + len(heading) + 1
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        clean_heading = re.sub(r"^#+\s*", "", heading.split("\n")[0]).strip()
        sections.append({"heading": clean_heading, "text": text[start:end].strip(), "page": None})
    return sections


def semantic_chunk(text: str, max_chars: int = 1200, overlap_sentences: int = 2) -> List[str]:
    sentences = sent_tokenize(text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sent in sentences:
        if current_len + len(sent) > max_chars and current:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:]
            current_len = sum(len(s) for s in current)
        current.append(sent)
        current_len += len(sent)

    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if len(c.strip()) > 50]


def _get_embeddings():
    if settings.sanity_mock:
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=768)
    return OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)


def _get_mime_type(file_path: str, filename: str) -> str:
    path_lower = (filename or file_path).lower()
    if path_lower.endswith(".pdf"):
        return "application/pdf"
    if path_lower.endswith((".html", ".htm")):
        return "text/html"
    return "text/plain"


async def smart_hierarchical_chunk(
    file_path: str,
    mime_type: str,
    doc_id: str,
    filename: str,
) -> Tuple[List[Document], List[Document]]:
    """Returns (parents, children). Parents stored in SQLite. Children embedded into FAISS."""
    if mime_type == "application/pdf":
        sections = extract_sections_pdf(file_path)
    else:
        async with aiofiles.open(file_path, encoding="utf-8", errors="replace") as f:
            raw = await f.read()
        sections = extract_sections_text(raw)

    parents: List[Document] = []
    children: List[Document] = []

    for p_idx, section in enumerate(sections):
        parent_text = _strip_injection(section["text"])
        if not parent_text.strip():
            continue

        parent_doc = Document(
            page_content=parent_text,
            metadata={
                "doc_id": doc_id,
                "source": filename,
                "section": section["heading"],
                "page": section.get("page"),
                "parent_idx": p_idx,
                "type": "parent",
            },
        )
        parents.append(parent_doc)

        child_texts = semantic_chunk(parent_text, max_chars=1200, overlap_sentences=2)
        for c_idx, child_text in enumerate(child_texts):
            children.append(
                Document(
                    page_content=child_text,
                    metadata={
                        "doc_id": doc_id,
                        "source": filename,
                        "section": section["heading"],
                        "page": section.get("page"),
                        "parent_idx": p_idx,
                        "child_idx": c_idx,
                        "type": "child",
                    },
                )
            )

    return parents, children


async def ingest_document(
    user_id: str,
    file_path: str,
    filename: str,
    progress_callback: Optional[callable] = None,
    graph_store: Optional[dict] = None,
) -> dict:
    doc_id = str(uuid.uuid4())
    mime_type = _get_mime_type(file_path, filename)

    if progress_callback:
        await progress_callback("loading", 10)

    parents, children = await smart_hierarchical_chunk(file_path, mime_type, doc_id, filename)

    if not children:
        return {"doc_id": doc_id, "filename": filename, "chunks": 0}

    chunk_records: List[dict] = []
    parent_by_idx = {p.metadata["parent_idx"]: p for p in parents}
    for child_doc in children:
        p_idx = child_doc.metadata["parent_idx"]
        c_idx = child_doc.metadata["child_idx"]
        parent_doc = parent_by_idx.get(p_idx)
        if not parent_doc:
            continue
        chunk_records.append({
            "id": str(uuid.uuid4()),
            "doc_id": doc_id,
            "user_id": user_id,
            "parent_idx": p_idx,
            "child_idx": c_idx,
            "parent_text": parent_doc.page_content,
            "child_text": child_doc.page_content,
            "source": filename,
            "page": parent_doc.metadata.get("page"),
            "section": parent_doc.metadata.get("section", ""),
        })

    if progress_callback:
        await progress_callback("chunking", 25)

    embeddings = _get_embeddings()
    vectorstore_path = f"vectorstore/user_{user_id}"
    os.makedirs(vectorstore_path, exist_ok=True)
    faiss_path = os.path.join(vectorstore_path, "faiss_index")
    bm25_path = os.path.join(vectorstore_path, "bm25_corpus.pkl")

    def _build_faiss():
        if os.path.exists(faiss_path):
            store = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
            store.add_documents(children)
        else:
            store = FAISS.from_documents(children, embeddings)
        store.save_local(faiss_path)

    if progress_callback:
        await progress_callback("embedding", 60)

    await asyncio.to_thread(_build_faiss)

    existing: List[Document] = []
    if os.path.exists(bm25_path):
        async with aiofiles.open(bm25_path, "rb") as f:
            data = await f.read()
            existing = pickle.loads(data)
    existing.extend(children)
    async with aiofiles.open(bm25_path, "wb") as f:
        await f.write(pickle.dumps(existing))

    if progress_callback:
        await progress_callback("indexing", 85)

    conn = await get_db()
    try:
        await insert_document(conn, doc_id, user_id, filename)
        await insert_chunks(conn, chunk_records)
    finally:
        await conn.close()

    if progress_callback:
        await progress_callback("done", 100)

    if graph_store is not None:
        from app.core.graph import update_user_graph
        await update_user_graph(user_id, parents, graph_store)

    return {"doc_id": doc_id, "filename": filename, "chunks": len(children)}
