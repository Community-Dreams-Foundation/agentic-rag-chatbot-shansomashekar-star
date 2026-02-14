import json
import sys
from pathlib import Path

def fail(msg: str):
    print(f"VERIFY_FAIL: {msg}")
    sys.exit(1)

def main():
    if len(sys.argv) != 2:
        fail("Usage: verify_output.py <artifacts/sanity_output.json>")

    path = Path(sys.argv[1])
    data = json.loads(path.read_text())

    # Required fields
    for k in ["implemented_features", "demo", "qa"]:
        if k not in data:
            fail(f"Missing key: {k}")

    # Must demonstrate upload->index->ask with citations for Feature A if claimed
    feats = set(data.get("implemented_features", []))
    qa = data.get("qa", [])

    if "A" in feats:
        if not qa:
            fail("Feature A claimed but qa list is empty.")

        # Each QA must include citations
        for i, item in enumerate(qa):
            if "question" not in item or "answer" not in item:
                fail(f"QA[{i}] missing question/answer")
            cites = item.get("citations", [])
            if not isinstance(cites, list) or len(cites) == 0:
                fail(f"QA[{i}] has no citations")
            # Minimal citation structure
            for c in cites:
                if not isinstance(c, dict):
                    fail(f"QA[{i}] citation must be object")
                for req in ["source", "locator", "snippet"]:
                    if req not in c:
                        fail(f"QA[{i}] citation missing {req}")

    # Memory file checks if Feature B claimed
    if "B" in feats:
        # Candidate should append to these paths
        user_mem = Path("USER_MEMORY.md")
        comp_mem = Path("COMPANY_MEMORY.md")
        if not user_mem.exists() or not comp_mem.exists():
            fail("Feature B claimed but memory files missing")

        # must show at least one memory write recorded in sanity output
        demo = data.get("demo", {})
        mem_writes = demo.get("memory_writes", [])
        if not isinstance(mem_writes, list) or len(mem_writes) == 0:
            fail("Feature B claimed but demo.memory_writes empty")

    print("VERIFY_OK")

if __name__ == "__main__":
    main()