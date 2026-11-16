#!/usr/bin/env python3
"""Retrieval check for the Step 2 index.

Each test query has one expected source file (a document known to answer it).
Reports hit@1 and hit@3 over the set. Small hand-made set: a sanity check, not a benchmark.

Usage: python3 eval_retrieval.py --db chroma_db --collection docs --chunks chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index_chunks import query_index  # noqa: E402

TESTS = [
    ("how do I pin the Python version for a project", "concepts/python-versions.md"),
    ("export the lockfile to requirements.txt format", "concepts/projects/export.md"),
    ("use custom CA certificates for TLS connections", "concepts/authentication/certificates.md"),
    ("where is the uv cache directory stored", "concepts/cache.md"),
    ("configure a private package index", "concepts/indexes.md"),
    ("what does uv run do", "concepts/projects/run.md"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--collection", default="docs")
    ap.add_argument("--chunks", required=True, type=Path)
    args = ap.parse_args()

    sources = {json.loads(line)["source"] for line in args.chunks.open(encoding="utf-8")}
    missing = [src for _, src in TESTS if src not in sources]
    if missing:
        print(f"expected sources not in corpus: {missing}")
        return 1

    hit1 = hit3 = 0
    for question, expected in TESTS:
        hits = query_index(args.db, args.collection, question, 3)
        ranked = [h["source"] for h in hits]
        ok1 = ranked[0] == expected
        ok3 = expected in ranked
        hit1 += ok1
        hit3 += ok3
        status = "HIT@1" if ok1 else ("HIT@3" if ok3 else "MISS")
        print(f"{status:6} {question!r} -> expected {expected}")
        print(f"       top3: {ranked}")
    print(f"hit@1 {hit1}/{len(TESTS)}   hit@3 {hit3}/{len(TESTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
