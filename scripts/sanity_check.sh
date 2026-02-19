#!/bin/bash
set -e

OUTPUT="artifacts/sanity_output.json"
MOCK="${SANITY_MOCK:-false}"

echo ""
echo "================================================"
echo "  RAG Chatbot — Sanity Check"
echo "  SANITY_MOCK=$MOCK"
echo "================================================"
echo ""

# Run Python sanity check (MOCK mode needs no server)
if [ "$MOCK" = "true" ]; then
    echo "Running sanity check (MOCK mode, no server needed)..."
    SANITY_MOCK=true python scripts/sanity_check.py
else
    echo "Starting server..."
    uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
    PID=$!
    sleep 8
    echo "Running sanity check..."
    python scripts/sanity_check.py
    EXIT=$?
    kill $PID 2>/dev/null || true
    [ $EXIT -eq 0 ] || exit $EXIT
fi

echo ""
echo "================================================"
echo "  Validating $OUTPUT"
echo "================================================"
echo ""

[ -f "$OUTPUT" ] || { echo "[FAIL] $OUTPUT not found. Run 'make sanity' first."; exit 1; }
echo "[PASS] Output file exists"

python3 -c "import json,sys; json.load(open('$OUTPUT'))" \
  && echo "[PASS] Valid JSON" \
  || { echo "[FAIL] Invalid JSON"; exit 1; }

python3 - <<'EOF'
import json, sys

with open("artifacts/sanity_output.json") as f:
    data = json.load(f)

errors = []

if data.get("status") != "ok":
    errors.append(f"status is '{data.get('status')}', expected 'ok'")

chunks = data.get("ingestion", {}).get("chunks_indexed", 0)
if not isinstance(chunks, int) or chunks < 1:
    errors.append(f"chunks_indexed must be int >= 1, got {chunks!r}")

answer = data.get("retrieval", {}).get("answer", "")
if not isinstance(answer, str) or len(answer) == 0:
    errors.append("retrieval.answer must be a non-empty string")

citations = data.get("retrieval", {}).get("citations", [])
if not isinstance(citations, list) or len(citations) == 0:
    errors.append("retrieval.citations must be a non-empty list")
else:
    for i, c in enumerate(citations):
        if "source" not in c:
            errors.append(f"citations[{i}] missing field 'source'")
        if "chunk_index" not in c and "excerpt" not in c:
            errors.append(f"citations[{i}] missing field 'chunk_index' or 'excerpt'")

memory = data.get("memory", {})
for field in ("user_memory_written", "company_memory_written"):
    if not isinstance(memory.get(field), bool):
        errors.append(f"memory.{field} must be a boolean")

if not isinstance(data.get("latency_ms"), int):
    errors.append("latency_ms must be an integer")

if errors:
    for e in errors:
        print(f"[FAIL] {e}")
    sys.exit(1)

print("[PASS] status == ok")
print(f"[PASS] chunks_indexed = {chunks}")
print(f"[PASS] answer length  = {len(answer)} chars")
print(f"[PASS] citations      = {len(citations)}")
print("[PASS] memory fields are booleans")
print(f"[PASS] latency_ms     = {data['latency_ms']}")
EOF

echo ""
echo "================================================"
echo "  ALL VALIDATION CHECKS PASSED"
echo "================================================"
echo ""
