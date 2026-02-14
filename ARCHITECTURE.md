# Architecture Overview

## Overview
This system implements:
- **Ingestion:** file parsing → chunking → embedding/indexing
- **Retrieval:** query → search (vector and/or BM25) → optional rerank
- **Answering:** LLM generates response strictly from retrieved context + returns citations
- **Memory:** selective extraction writes durable knowledge into markdown files

## Components
### 1) Ingestion
- Input formats: (e.g., PDF/HTML/TXT)
- Chunking strategy: (section-aware / fixed size / semantic)
- Metadata tracked: (source file, page, section, chunk_id)

### 2) Index / Storage
- Vector store: (FAISS/Chroma/pgvector/etc)
- Optional lexical index: (BM25)
- Persistence: (local disk / sqlite / postgres)

### 3) Retrieval + Grounding
- Retrieval method: (top-k, filters)
- Citation format: how citations map to chunks/pages/sections
- Failure behavior: what happens when retrieval is empty/low confidence

### 4) Memory
- Decision policy: what qualifies as “high-signal”
- Safety: excludes secrets/sensitive info
- Output targets:
  - `USER_MEMORY.md`
  - `COMPANY_MEMORY.md`

### 5) Optional Sandbox Tooling
- Tool interface for Open-Meteo
- Isolation boundaries (how code execution is restricted)
- Rate limiting / timeouts

## Tradeoffs
- Why you chose your chunking strategy
- Why you chose your vector store
- How you balanced correctness vs simplicity
- What you would improve next