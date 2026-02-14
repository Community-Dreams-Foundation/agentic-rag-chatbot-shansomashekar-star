# Proximal Energy — Agentic RAG Chatbot Challenge

## Goal
Build a small chatbot (web app or CLI) that demonstrates how you’d ship an AI-first feature:
**file-grounded Q&A (RAG)**, **durable memory**, and optionally **safe compute**.

Partial implementations are acceptable, but the more you integrate successfully, the better.

---

## What to Build

### Feature A — File Upload + RAG (Core)
Users can:
- Upload files and add them to a RAG pipeline (chunk → index → search)
- Ask questions later and receive answers grounded in the uploaded content
- Provide **citations** pointing to the source chunks/sections used

**Minimum expectation:** working ingestion + retrieval + grounded response + citations.

**Suggested test data:** open-access arXiv PDFs/HTML.

Extra points:
- Hybrid retrieval (BM25 + embeddings), reranking, metadata filters
- Smart chunking (section-aware, semantic boundaries)
- Knowledge-graph flavored RAG (HippoRAG-style)

---

### Feature B — Persistent Memory (Core-ish)
Write durable memory into two markdown files:
- `USER_MEMORY.md` — user-specific high-signal facts
- `COMPANY_MEMORY.md` — org-wide reusable learnings

Rules:
- Memory must be **selective** (no raw transcript dumping)
- Store only high-signal, reusable knowledge
- Avoid secrets or sensitive info

Implementation hint (optional):
Use a structured decision like:
`{should_write, target, summary, confidence}` and only append when confident.

---

### Feature C — Safe Python Sandbox + Open-Meteo (Optional)
Optional tool calling with safe execution boundaries:
- Call Open-Meteo time series API (no key)
- Compute basic analytics (rolling averages, volatility, missingness, anomalies)
- Return clear explanation of findings

We care about **safe execution + clean tool interface**, not perfect data science.

---

## Deliverables (Required)
Your repository must include:
- `README.md` with setup + run instructions
- A brief architecture overview (`ARCHITECTURE.md` or a section below)
- A working demo flow (based on what you implemented):
  - Upload → index → ask questions with citations
  - Memory written into `USER_MEMORY.md` and `COMPANY_MEMORY.md`
  - (Optional) Sandbox + Open-Meteo time series analysis
- Basic tests OR at least a sanity-check script (preferred)
- A short video walkthrough (5–10 minutes) demonstrating:
  - working product end-to-end
  - key design choices + tradeoffs
  - what you would improve next

---

## Submission Instructions
1) Implement your solution in this repo.
2) Add your video link here:

### Video Walkthrough
<PASTE LINK HERE>

3) Ensure the sanity check runs:
```bash
bash scripts/sanity_check.sh