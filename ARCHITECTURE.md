# Architecture Overview

## System Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                   Browser  (Vanilla JS / React)              │
│   Left: Upload + Docs  │  Center: Chat  │  Right: Memory    │
└───────────┬────────────────────────────────────┬─────────────┘
            │ HTTP / SSE                          │ HTTP
┌───────────▼────────────────────────────────────▼─────────────┐
│                  FastAPI  (async, uvicorn)                    │
│  POST /upload          GET /ask (SSE)     GET /memory         │
│  GET  /documents       GET /memory/insights  DELETE /memory/*  │
│  DELETE /documents     GET /graph/*        POST /analyze       │
│  GET /health                                                  │
└──────────┬────────────────────────┬───────────────────────────┘
           │                        │
┌──────────▼──────────┐  ┌──────────▼──────────────────────────┐
│   Ingest Engine     │  │         RAG Pipeline                 │
│                     │  │                                      │
│ 1. Load (PDF/TXT/   │  │ 1. HyDE: generate hypothetical       │
│    HTML)            │  │    answer → embed that, not query    │
│ 2. Detect sections  │  │ 2. BM25 (sparse, raw query)         │
│    PDF: font size   │  │    + FAISS/MMR (dense, HyDE vector) │
│    Text: ## markers │  │    → EnsembleRetriever (RRF)         │
│ 3. Semantic chunk   │  │ 3. CrossEncoder rerank → top 4       │
│    (NLTK sentence   │  │ 4. Metadata filter (src/section/page)│
│    boundaries)      │  │ 5. Child → parent expand (SQLite)    │
│ 4. Async batch      │  │ 6. Graph context: 2-hop entity walk  │
│    embed (parallel) │  │ 7. Inject memory into prompt         │
│ 5. FAISS upsert     │  │ 8. Stream tokens via SSE             │
│ 6. Graph extract    │  │ 9. Background: cache+memory+log      │
└──────────┬──────────┘  └──────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                      Storage Layer                           │
│                                                              │
│  Redis              FAISS shards         SQLite             │
│  emb:{sha256}       vectorstore/         users              │
│  qry:{uid}:{hash}     user_{id}/         documents          │
│  TTL: 24h / 1h      NetworkX graphs      chunks             │
│                       user_{id}/         queries            │
│                       graph.pkl                             │
│                                                              │
│                     memory/user_{id}/                        │
│                       USER_MEMORY.md                         │
│                       COMPANY_MEMORY.md                      │
└──────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                   Ollama  (local)                            │
│  llama3.1:8b     Chat, HyDE expansion, streaming             │
│  mistral:7b      Memory + graph extraction (format="json")   │
│  nomic-embed-text Dense embeddings, 768-dim                  │
└──────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Smart Chunking (app/core/ingest.py)

Two phases run on every uploaded document before any embedding.

**Phase 1 — Section detection.** PDFs: PyMuPDF reads font metadata. A span is a heading if font size ≥ 1.2× body, length < 120 chars, and title-case. Text/Markdown: split on `##`, `===`, `---` markers. Output: named sections — Introduction, Methods, Results, etc.

**Phase 2 — Semantic splitting within sections.** NLTK sentence tokenizer splits each section. Sentences are accumulated until ~1200 chars, then the last 2 sentences carry over as overlap. No chunk ever cuts mid-sentence.

**Parent-child architecture.** Child chunks (~300–1200 chars) are embedded into FAISS. Parent paragraphs are stored in SQLite `chunks.parent_text`. At retrieval: child found → parent fetched → parent sent to LLM. Retrieval stays precise; LLM context stays rich.

### Hybrid Retrieval (app/core/retriever.py)

**HyDE.** llama3.1:8b generates a hypothetical answer paragraph. That is embedded, not the raw query. Documents with real answers are closer to a well-formed answer than to a terse question.

**EnsembleRetriever.** BM25 (weight 0.35) handles exact terms — acronyms, author names, identifiers. FAISS/MMR (weight 0.65) handles semantic paraphrases. Fused via Reciprocal Rank Fusion.

**CrossEncoder reranking.** cross-encoder/ms-marco-MiniLM-L-6-v2 re-scores each chunk by reading query+document together (full attention, not cosine). Top 4 pass through. Model loaded once at startup in `app.state.reranker`.

**Parent expansion.** Retrieved children are deduplicated by `(doc_id, parent_idx)`, replaced with full parent paragraphs from SQLite before the LLM receives context.

### Knowledge Graph (app/core/graph.py)

On ingest, every parent chunk is sent to mistral:7b (`format="json"`) which extracts entities and relationships. These build a per-user NetworkX directed graph (persisted as pickle). At query time: extract entities from question → match graph nodes → walk 2-hop neighbours (sorted by edge weight) → prepend subgraph as structured context. LLM can cite `[Graph: BERT → developed_by → Google]`.

### Memory Engine (app/core/memory.py)

After every answered query, mistral:7b runs on query+answer. Returns `{should_write, target, summary, confidence}`. Writes to USER_MEMORY.md or COMPANY_MEMORY.md only if confidence >= 0.80. One fact per write, never raw transcripts. User memory injected into every RAG system prompt.

### Multi-User Isolation

| Resource | Path |
|----------|------|
| FAISS index | vectorstore/user_{id}/faiss_index |
| BM25 corpus | vectorstore/user_{id}/bm25_corpus.pkl |
| Knowledge graph | vectorstore/user_{id}/knowledge_graph.pkl |
| User memory | memory/user_{id}/USER_MEMORY.md |
| Company memory | memory/user_{id}/COMPANY_MEMORY.md |

Concurrent FAISS writes use `user_locks: dict[str, asyncio.Lock]` — one lock per user, zero contention across users.

### Streaming and Caching

All `/ask` responses stream via SSE. First token < 1s on CPU. Redis caches embeddings (TTL 24h) and full query results (TTL 1h). Repeat queries: ~200ms. Cache invalidated per-user on every upload.
