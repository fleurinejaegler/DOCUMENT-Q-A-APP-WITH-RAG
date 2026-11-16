#!/usr/bin/env python3
"""Checks on ingest.py output.

Usage (from the livrable folder):
    python3 -I verify.py --corpus corpus --chunks out/chunks.jsonl

Checks:
  1. chunk_index is 0..n-1 in every document.
  2. No empty chunk; no code-fence line left in chunk text.
  3. Splitting loses no content: every word produced by extract_text +
     split_by_headers (the pipeline's own cleaned sections) appears in the chunks.
     Cleaning itself (removing markup) is not checked here by design.
  4. Information only: chunks still containing Markdown link syntax.

Exit code 0 when checks 1-3 pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # import ingest.py from this folder
import ingest  # noqa: E402

WORD = re.compile(r"[A-Za-z][A-Za-z0-9_-]{3,}")
FENCE_LINE = re.compile(r"^\s*(```|~~~)", re.M)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, type=Path)
    ap.add_argument("--chunks", required=True, type=Path)
    args = ap.parse_args()

    rows = [json.loads(line) for line in args.chunks.open(encoding="utf-8")]
    by_doc: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        by_doc[row["source"]].append(row)

    failures: list[str] = []

    for src, items in by_doc.items():
        if sorted(x["chunk_index"] for x in items) != list(range(len(items))):
            failures.append(f"chunk_index not contiguous: {src}")

    if any(not r["text"].strip() for r in rows):
        failures.append("empty chunk(s) found")
    if any(FENCE_LINE.search(r["text"]) for r in rows):
        failures.append("code-fence line left inside chunk text")

    total_words = missing_words = 0
    for src, items in by_doc.items():
        path = args.corpus / src
        sections = ingest.split_by_headers(ingest.extract_text(path))
        expected = set(WORD.findall("\n".join(body for _, body in sections)))
        got = set(WORD.findall(" ".join(x["text"] for x in items)))
        missing = expected - got
        total_words += len(expected)
        missing_words += len(missing)
        if missing:
            failures.append(f"words lost in splitting: {src}: {sorted(missing)[:5]}")

    link_left = sum("](" in r["text"] for r in rows)

    print(f"documents: {len(by_doc)}  chunks: {len(rows)}")
    print(f"word coverage after splitting: {total_words - missing_words}/{total_words}")
    print(f"info: chunks still containing link syntax: {link_left} (known limitation)")
    if failures:
        print("FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
