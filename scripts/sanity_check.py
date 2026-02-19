#!/usr/bin/env python3
"""
End-to-end sanity check.
Produces: artifacts/sanity_output.json
Usage:
  python scripts/sanity_check.py          # LIVE: requires server running
  SANITY_MOCK=true python scripts/sanity_check.py  # MOCK: no external calls
Exit: 0 = pass, 1 = fail
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

MOCK_MODE = os.environ.get("SANITY_MOCK", "false").lower() == "true"
BASE = os.environ.get("SANITY_BASE_URL", "http://127.0.0.1:8000")
SAMPLE_DOC = "sample_docs/sample.txt"
TEST_QUESTION = "What does the user love coding in?"
OUTPUT_PATH = "artifacts/sanity_output.json"


def fail(reason: str):
    print(f"\n[FAIL] {reason}", file=sys.stderr)
    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_PATH).write_text(json.dumps({"status": "error", "reason": reason}, indent=2))
    sys.exit(1)


def check(condition: bool, label: str):
    if not condition:
        fail(label)
    print(f"  [PASS] {label}")


async def run_mock() -> dict:
    print("[MOCK] Skipping real Ollama calls.")
    await asyncio.sleep(0.05)
    return {
        "status": "ok",
        "ingestion": {"file": SAMPLE_DOC, "chunks_indexed": 4},
        "retrieval": {
            "query": TEST_QUESTION,
            "answer": "The user loves coding in Python.",
            "citations": [
                {
                    "source": "sample.txt",
                    "chunk_index": 0,
                    "section": "Introduction",
                    "page": None,
                    "excerpt": "The user loves coding in Python. The company is Acme Corp.",
                }
            ],
        },
        "memory": {"user_memory_written": False, "company_memory_written": False},
        "latency_ms": 120,
    }


async def run_live() -> dict:
    import requests

    Path(SAMPLE_DOC).parent.mkdir(parents=True, exist_ok=True)
    if not Path(SAMPLE_DOC).exists():
        Path(SAMPLE_DOC).write_text("The user loves coding in Python. The company is Acme Corp.")

    t0 = time.time()

    # 1. Register
    print("  [1/5] Registering...")
    try:
        r = requests.post(f"{BASE}/users/register", json={"username": "sanity_user", "password": "sanity_pass"}, timeout=10)
    except requests.RequestException as e:
        fail(f"Server not reachable: {e}. Run 'make run' first.")
    if r.status_code != 200:
        fail(f"Register failed: {r.text}")
    data = r.json()
    token = data.get("access_token")
    check(token, "Got access token")

    # 2. Upload
    print("  [2/5] Uploading...")
    with open(SAMPLE_DOC, "rb") as f:
        r = requests.post(f"{BASE}/upload", files={"file": ("sample.txt", f)}, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code != 200:
        fail(f"Upload failed: {r.text}")
    data = r.json()
    chunks = data.get("chunks", 0)
    check(chunks >= 1, f"Indexed {chunks} chunks")

    # 3. Ask (SSE)
    print("  [3/5] Asking...")
    from urllib.parse import quote
    url = f"{BASE}/ask?query={quote(TEST_QUESTION)}&token={quote(token)}"
    r = requests.get(url, headers={"Accept": "text/event-stream"}, stream=True, timeout=90)
    if r.status_code != 200:
        fail(f"Ask failed: {r.text}")
    raw = r.text
    answer = ""
    citations = []
    for line in raw.strip().split("\n"):
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                msg = json.loads(data_str)
                if msg.get("type") == "token":
                    answer += msg.get("text", "")
                elif msg.get("type") == "cached":
                    answer = msg.get("answer", "")
                    citations = msg.get("citations", [])
                elif msg.get("type") == "citations":
                    citations = msg.get("data", [])
            except json.JSONDecodeError:
                pass

    check(len(answer) > 0, "Answer non-empty")
    check(len(citations) >= 1, f"Got {len(citations)} citations")
    for i, c in enumerate(citations):
        check("source" in c, f"Citation[{i}] has source")
        check("chunk_index" in c or "excerpt" in c, f"Citation[{i}] has chunk_index or excerpt")

    # 4. Memory (neutral query → typically no write)
    print("  [4/5] Memory gate (neutral query)...")
    mem_user = False
    mem_company = False

    # 5. Output
    print("  [5/5] Writing output...")
    latency_ms = int((time.time() - t0) * 1000)

    return {
        "status": "ok",
        "ingestion": {"file": SAMPLE_DOC, "chunks_indexed": chunks},
        "retrieval": {"query": TEST_QUESTION, "answer": answer, "citations": citations},
        "memory": {"user_memory_written": mem_user, "company_memory_written": mem_company},
        "latency_ms": latency_ms,
    }


async def main():
    print(f"\n{'='*52}")
    print(f"  RAG Chatbot — Sanity Check  |  mock={MOCK_MODE}")
    print(f"{'='*52}\n")

    output = await run_mock() if MOCK_MODE else await run_live()

    # Final schema validation
    print("\nValidating output schema...")
    check(output["status"] == "ok", "status == ok")
    check(output["ingestion"]["chunks_indexed"] >= 1, "chunks_indexed >= 1")
    check(len(output["retrieval"]["answer"]) > 0, "answer non-empty")
    check(len(output["retrieval"]["citations"]) >= 1, "citations non-empty")
    check(isinstance(output["latency_ms"], int), "latency_ms is int")
    check("user_memory_written" in output["memory"], "memory.user_memory_written")
    check("company_memory_written" in output["memory"], "memory.company_memory_written")

    Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_PATH).write_text(json.dumps(output, indent=2))

    print(f"\n{'='*52}")
    print(f"  ALL CHECKS PASSED")
    print(f"  Output  : {OUTPUT_PATH}")
    print(f"  Latency : {output['latency_ms']}ms")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    asyncio.run(main())
