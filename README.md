# Agentic RAG Chatbot — Hackathon Challenge

## Overview
Build a chatbot (Web App or CLI) that demonstrates how you’d ship an AI-first product feature:
- **File-grounded Q&A (RAG)** with **citations**
- **Durable memory** written to markdown
- *(Optional)* **Safe compute** tool calling with Open-Meteo time series analysis

You may implement one feature or multiple. Partial implementations are acceptable.

---

## What You Need To Build

### Feature A — File Upload + RAG (Core)
Users can:
- Upload files and add them to a RAG pipeline (parse → chunk → index)
- Ask questions later and receive answers grounded in uploaded content
- Provide **citations** pointing to source chunks/sections

**Minimum expectation:** working ingestion + retrieval + grounded response + citations.

Suggested test data: arXiv PDFs/HTML (open access).

Extra points:
- Hybrid retrieval (BM25 + embeddings), reranking, metadata filters
- Smart chunking (section-aware, semantic boundaries)
- Knowledge-graph flavored RAG

---

### Feature B — Persistent Memory (Core-ish)
Add a memory subsystem that writes selective, high-signal knowledge to:

- `USER_MEMORY.md`  
  Store user-specific facts worth remembering.  
  Example: “User is a Project Finance Analyst”, “Prefers weekly summaries on Mondays”.

- `COMPANY_MEMORY.md`  
  Store org-wide learnings useful to colleagues.  
  Example: “Recurring workflow bottleneck is X”.

Rules:
- **Selective** (no transcript dumping)
- **High-signal and reusable**
- **Avoid storing secrets or sensitive information**

Implementation hint (optional):
Use an internal decision structure like:
`{should_write, target, summary, confidence}` and only append when confident.

---

### Feature C — Safe Python Sandbox + Open-Meteo (Optional)
Create a safe tool interface to:
- Call Open-Meteo for a location/time range
- Retrieve time series data
- Compute basic analytics (rolling averages, volatility, missingness checks, anomaly flags, etc.)
- Return a clear explanation of findings

We care about **safe execution boundaries + clean tool interface**, not perfect data science.

---

## Deliverables (Required)
Your repo must include:
- `README.md` with **setup + run instructions**
- A brief architecture overview in `ARCHITECTURE.md` (or in this README)
- A working demo flow (based on what you implemented):
  - Upload → index → ask questions with citations
  - Memory written into `USER_MEMORY.md` and `COMPANY_MEMORY.md`
  - (Optional) Sandbox + Open-Meteo time series analysis
- Basic tests or at least a small sanity-check script (preferred)
- A short video walkthrough (5–10 minutes) demonstrating:
  - The working product end-to-end
  - Key design choices and tradeoffs
  - What you would improve next with more time

---

## Submission Rules (Important)

### 1) Any language / any stack
You may use any language, framework, model, and any vector DB (FAISS/Chroma/pgvector/etc.).

### 2) One universal judge command (Required)
Judges must be able to run:

```bash
make sanity
````

Your `make sanity` must:

* Run a minimal end-to-end flow (based on what you implemented)
* Produce this file:

```text
artifacts/sanity_output.json
```

Judges may also run:

```bash
bash scripts/sanity_check.sh
```

(This script runs `make sanity` and validates the output format.)

### 3) Video Walkthrough Link (Required)

Add your video link here:

## Video Walkthrough

PASTE YOUR LINK HERE

---

## What We Evaluate

We evaluate holistically:

### Correctness & UX

* RAG answers are grounded and cite sources
* Graceful behavior when retrieval fails (no hallucinations)

### Engineering Quality

* Clean structure and modular design
* Readable code and thoughtful naming
* Error handling and reproducibility

### Product Thinking

* Sensible retrieval design
* Thoughtful memory criteria
* Clear tradeoffs explained in README/architecture

### Security Mindset (Bonus)

* Prompt-injection awareness in RAG
* Sandbox isolation (if implementing Feature C)
* Safe handling of external API calls

---

## Quick Start (YOU MUST FILL THIS IN)

Provide exact commands a judge can run.

Example (replace with your real commands):

```text
# install dependencies
# run the app
# open UI or run CLI
```

---

## Suggested Evaluation Prompts

See: `EVAL_QUESTIONS.md`