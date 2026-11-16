#!/usr/bin/env python3
"""Step 4: evaluate retrieval (SourceHitRate@k) and prepare the manual answer review.

Usage:
    python3 evaluate.py --db ../step2/chroma_db --dataset eval_dataset.jsonl --out results
    python3 evaluate.py ... --generate        # also generate answers (needs ANTHROPIC_API_KEY)

Outputs in --out:
    eval_interactions.jsonl  one JSON line per question (same format as the app log)
    summary.json             SourceHitRate@k over answerable questions, plus out-of-scope results
    review.csv               one row per question for the manual label:
                             Accurate / Partially Accurate / Incorrect / Not Answerable

SourceHitRate@k: an answerable question is a hit when at least one of the top-k retrieved
chunks comes from one of its gold source files. Out-of-scope questions (empty gold list)
are excluded from the rate and reported separately.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rag  # noqa: E402

LABELS = ["Accurate", "Partially Accurate", "Incorrect", "Not Answerable"]


def load_dataset(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate question ids in dataset")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--collection", default="docs")
    ap.add_argument("--dataset", type=Path, default=HERE / "eval_dataset.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("-k", type=int, default=rag.TOP_K)
    ap.add_argument("--generate", action="store_true", help="also generate answers with the LLM")
    args = ap.parse_args()

    dataset = load_dataset(args.dataset)
    args.out.mkdir(parents=True, exist_ok=True)
    log_path = args.out / "eval_interactions.jsonl"
    if log_path.exists():
        log_path.unlink()  # each evaluation run starts a fresh log

    retriever = rag.Retriever(args.db, args.collection)
    use_llm = args.generate and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if args.generate and not use_llm:
        print("warning: --generate ignored, ANTHROPIC_API_KEY is not set", file=sys.stderr)

    answerable_hits = 0
    answerable_total = 0
    per_question = []
    review_rows = []

    for item in dataset:
        question = item["question"]
        gold = set(item["gold_sources"])
        passages = retriever.search(question, args.k)
        retrieved_sources = [p.source for p in passages]

        hit = bool(gold & set(retrieved_sources)) if gold else None
        if gold:
            answerable_total += 1
            answerable_hits += int(bool(hit))

        answer_text, error = None, None
        if use_llm:
            system, user = rag.build_messages(question, passages)
            try:
                answer_text = rag.generate(system, user)
            except Exception as exc:  # keep evaluating the other questions
                error = str(exc)
        cited = rag.cited_labels(answer_text, passages) if answer_text else set()

        rag.log_interaction(
            {**rag.make_record(question, passages, answer_text, cited, error), "id": item["id"]},
            log_path,
        )

        per_question.append({
            "id": item["id"],
            "question": question,
            "gold_sources": sorted(gold),
            "retrieved_sources": retrieved_sources,
            "hit_at_k": hit,
        })
        review_rows.append({
            "id": item["id"],
            "question": question,
            "gold_hit": "" if hit is None else ("yes" if hit else "no"),
            "retrieved_sources": " | ".join(retrieved_sources),
            "answer": answer_text or "",
            "label": "",
        })

    rate = answerable_hits / answerable_total if answerable_total else 0.0
    summary = {
        "k": args.k,
        "questions_total": len(dataset),
        "answerable": answerable_total,
        "out_of_scope": len(dataset) - answerable_total,
        "source_hit_rate_at_k": round(rate, 4),
        "hits": answerable_hits,
        "answers_generated": use_llm,
        "dataset": str(args.dataset),
        "db": str(args.db),
        "misses": [q["id"] for q in per_question if q["hit_at_k"] is False],
    }
    (args.out / "summary.json").write_text(
        json.dumps({"summary": summary, "per_question": per_question}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.out / "review.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "question", "gold_hit", "retrieved_sources", "answer", "label"])
        writer.writeheader()
        writer.writerows(review_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"labels for review.csv: {' / '.join(LABELS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
