import asyncio
import os
import pickle
from typing import Any, Dict, List, Optional, Sequence

from langchain.chains.hyde.base import HypotheticalDocumentEmbedder
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from app.config import settings
from app.core.memory import read_user_memory
from app.db import get_db, get_parent_texts

RAG_PROMPT = """You are a precise research assistant with access to both a knowledge graph and document chunks.
Answer ONLY using the provided CONTEXT (graph facts + document chunks).
If the knowledge graph mentions relevant entities or relationships, use them to enrich your answer.
If the context does not contain enough information, respond with exactly:
"I don't have enough information in the uploaded documents to answer this."
Cite document sources inline: [Source: <filename>, Chunk <n>]
Cite graph facts as: [Graph: <entity> → <relation> → <entity>]
Do NOT invent citations. Do NOT use prior knowledge outside the CONTEXT.
{memory_context}
CONTEXT:
{context}

QUESTION: {question}
"""

CROSS_DOC_PROMPT = """You are a precise research assistant comparing information across documents.
Answer ONLY using the provided CONTEXT. When comparing or contrasting, explicitly cite which source each claim comes from.
If the context does not contain enough information, respond with exactly:
"I don't have enough information in the uploaded documents to answer this."
Cite every claim: [Source: <filename>, Chunk <n>]
{memory_context}
CONTEXT:
{context}

QUESTION: {question}
"""


def _get_embeddings():
    if settings.sanity_mock:
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=768)
    return OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)


def _get_llm():
    if settings.sanity_mock:
        from langchain_community.chat_models import FakeListChatModel
        return FakeListChatModel(responses=["I don't have enough information in the uploaded documents to answer this."])
    return ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        timeout=120,
    )


def _get_hyde_embeddings():
    if settings.sanity_mock:
        from langchain_community.embeddings import FakeEmbeddings
        return FakeEmbeddings(size=768)
    base_emb = OllamaEmbeddings(model=settings.ollama_embed_model, base_url=settings.ollama_base_url)
    llm = ChatOllama(model=settings.ollama_chat_model, base_url=settings.ollama_base_url, temperature=0.4)
    return HypotheticalDocumentEmbedder.from_llm(llm, base_emb, "web_search")


class HyDEFAISSRetriever(BaseRetriever):
    """FAISS retriever that uses HyDE for query embedding."""
    store: FAISS
    hyde_embeddings: HypotheticalDocumentEmbedder
    k: int = 8
    fetch_k: int = 30
    lambda_mult: float = 0.7

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional[CallbackManagerForRetrieverRun] = None,
    ) -> List[Document]:
        embedding = self.hyde_embeddings.embed_query(query)
        return self.store.max_marginal_relevance_search_by_vector(
            embedding,
            k=self.k,
            fetch_k=self.fetch_k,
            lambda_mult=self.lambda_mult,
        )


def build_bm25_retriever(user_docs: List[Document], k: int = 8) -> BM25Retriever:
    retriever = BM25Retriever.from_documents(user_docs, k=k)
    retriever.k = k
    return retriever


def _get_retriever(user_id: str) -> Optional[Any]:
    vectorstore_path = f"vectorstore/user_{user_id}"
    faiss_path = os.path.join(vectorstore_path, "faiss_index")
    bm25_path = os.path.join(vectorstore_path, "bm25_corpus.pkl")

    if not os.path.exists(faiss_path):
        return None

    embeddings = _get_embeddings()
    store = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)

    docs_for_bm25: List[Document] = []
    if os.path.exists(bm25_path):
        with open(bm25_path, "rb") as f:
            docs_for_bm25 = pickle.load(f)

    bm25_retriever = build_bm25_retriever(docs_for_bm25, k=settings.retrieval_k)
    bm25_retriever.k = settings.retrieval_k

    if settings.hyde_enabled and not settings.sanity_mock:
        hyde_emb = _get_hyde_embeddings()
        faiss_retriever = HyDEFAISSRetriever(
            store=store,
            hyde_embeddings=hyde_emb,
            k=settings.retrieval_k,
            fetch_k=settings.retrieval_fetch_k,
            lambda_mult=0.7,
        )
    else:
        faiss_retriever = store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": settings.retrieval_k,
                "fetch_k": settings.retrieval_fetch_k,
                "lambda_mult": 0.7,
            },
        )

    return EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[settings.ensemble_bm25_weight, settings.ensemble_faiss_weight],
    )


def apply_metadata_filters(
    docs: List[Document],
    filter_source: Optional[str] = None,
    filter_section: Optional[str] = None,
    filter_page: Optional[int] = None,
) -> List[Document]:
    result = docs
    if filter_source:
        result = [d for d in result if d.metadata.get("source") == filter_source]
    if filter_section:
        result = [d for d in result if filter_section.lower() in (d.metadata.get("section") or "").lower()]
    if filter_page is not None:
        result = [d for d in result if d.metadata.get("page") == filter_page]
    return result if result else docs


async def expand_to_parents(
    user_id: str,
    child_docs: List[Document],
) -> List[Document]:
    """Replace retrieved child chunks with their full parent paragraphs from SQLite."""
    seen: set = set()
    parent_keys: List[tuple] = []
    for doc in child_docs:
        meta = doc.metadata
        doc_id = meta.get("doc_id")
        parent_idx = meta.get("parent_idx", 0)
        key = (doc_id, parent_idx)
        if key not in seen:
            seen.add(key)
            parent_keys.append((doc_id, parent_idx))

    conn = await get_db()
    try:
        texts = await get_parent_texts(conn, user_id, parent_keys)
    finally:
        await conn.close()

    key_to_text = {k: t for k, t in zip(parent_keys, texts)}
    expanded: List[Document] = []
    for doc in child_docs:
        key = (doc.metadata.get("doc_id"), doc.metadata.get("parent_idx", 0))
        parent_text = key_to_text.get(key, doc.page_content)
        expanded.append(
            Document(
                page_content=parent_text,
                metadata=dict(doc.metadata),
            )
        )
    return expanded


async def ask_stream(
    user_id: str,
    query: str,
    filter_source: Optional[str] = None,
    filter_section: Optional[str] = None,
    filter_page: Optional[int] = None,
    graph_store: Optional[Dict[str, Any]] = None,
    reranker_model: Optional[Any] = None,
) -> Dict[str, Any]:
    retriever = _get_retriever(user_id)
    if not retriever:
        return {"answer": "No documents indexed yet. Please upload a file first.", "citations": [], "source_docs": []}

    from app.core.cache import query_cache
    cached = await query_cache.get(user_id, query)
    if cached:
        return {"answer": cached["answer"], "citations": cached["citations"], "cached": True}

    def _retrieve():
        return retriever.invoke(query)

    raw_docs = await asyncio.to_thread(_retrieve)
    if not raw_docs:
        return {"answer": "I don't have enough information in the uploaded documents to answer this.", "citations": [], "source_docs": []}

    if len(raw_docs) >= 4 and reranker_model is not None and not settings.sanity_mock:
        compressor = CrossEncoderReranker(model=reranker_model, top_n=4)
        def _compress():
            return compressor.compress_documents(raw_docs, query)
        reranked = await asyncio.to_thread(_compress)
        docs_to_use = reranked if reranked else raw_docs
    else:
        docs_to_use = raw_docs

    filtered = apply_metadata_filters(docs_to_use, filter_source, filter_section, filter_page)
    context_docs = await expand_to_parents(user_id, filtered)

    graph_context = ""
    if graph_store:
        from app.core.graph import get_graph_context
        graph_context = await get_graph_context(query, user_id, graph_store)

    context_parts = []
    for d in context_docs:
        meta = d.metadata
        header = (
            f"[Source: {meta.get('source', '?')} | Section: {meta.get('section', '?')} "
            f"| Page: {meta.get('page', '?')} | Chunk {meta.get('child_idx', 0)}]\n"
        )
        context_parts.append(header + d.page_content)

    context = "\n\n---\n\n".join(context_parts)

    if graph_context:
        full_context = graph_context + "\n\n=== Retrieved Document Chunks ===\n\n" + context
    else:
        full_context = context

    user_memory = await read_user_memory(user_id)
    memory_context = ""
    if user_memory and user_memory.strip():
        summary = user_memory.strip()[:500]
        memory_context = f"Known facts about this user (preferred when relevant):\n{summary}\n\n"

    is_cross_doc = any(kw in query.lower() for kw in ["compare", "difference", "both", "versus", "vs", "contrast"])
    prompt_template = CROSS_DOC_PROMPT if is_cross_doc else RAG_PROMPT
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question", "memory_context"])
    llm = _get_llm()
    chain = prompt | llm

    def _invoke():
        return chain.invoke({"context": full_context, "question": query, "memory_context": memory_context})

    answer = await asyncio.to_thread(_invoke)
    answer_text = answer.content if hasattr(answer, "content") else str(answer)

    citations = []
    for d in context_docs[:5]:
        meta = d.metadata
        citations.append({
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("child_idx", meta.get("parent_idx", -1)),
            "section": meta.get("section", ""),
            "page": meta.get("page"),
            "excerpt": d.page_content[:150] + ("..." if len(d.page_content) > 150 else ""),
        })

    result = {"answer": answer_text, "citations": citations, "source_docs": context_docs}
    asyncio.create_task(query_cache.set(user_id, query, {"answer": answer_text, "citations": citations}))
    return result
