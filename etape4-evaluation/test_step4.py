"""Offline checks for Step 4: logging format, app logging, evaluation summary.

Run: python3 test_step4.py   (needs the Step 2 index at ../step2/chroma_db)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import rag

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "step2" / "chroma_db"
REQUIRED_KEYS = {"timestamp", "question", "retrieved", "answer", "cited_labels", "model", "error"}


def _passages():
    return rag.Retriever(DB).search("how do I install uv on my machine")


def test_record_has_required_fields_and_scores():
    passages = _passages()
    record = rag.make_record("q", passages, "Réponse [1].", {1}, None)
    assert REQUIRED_KEYS <= set(record)
    assert len(record["retrieved"]) == 3
    for item, p in zip(record["retrieved"], passages):
        assert item["chunk_id"] == p.chunk_id and item["source"] == p.source
        assert abs(item["score"] - (1 - item["distance"])) < 1e-3
    assert record["cited_labels"] == [1]


def test_log_is_jsonl_and_appends():
    passages = _passages()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "logs" / "interactions.jsonl"
        rag.log_interaction(rag.make_record("a", passages, None, None, "boom"), path)
        rag.log_interaction(rag.make_record("b", passages, "ok [2]", {2}), path)
        lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["question"] == "a" and first["error"] == "boom" and first["answer"] is None
    assert second["question"] == "b" and second["cited_labels"] == [2]


def test_app_writes_one_log_line_per_question():
    from streamlit.testing.v1 import AppTest

    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "app.jsonl"
        os.environ["RAG_LOG_PATH"] = str(log)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            at = AppTest.from_file(str(HERE / "app.py"), default_timeout=300)
            at.run()
            question = next(t for t in at.text_input if t.label == "Votre question")
            question.set_value("what is a uv workspace")
            at.button[0].click().run()
            assert not at.exception
            records = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
        finally:
            os.environ.pop("RAG_LOG_PATH", None)
    assert len(records) == 1
    assert records[0]["question"] == "what is a uv workspace"
    assert records[0]["answer"] is None and len(records[0]["retrieved"]) == 3


def test_evaluate_script_summary_matches_dataset():
    import subprocess
    import sys

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "res"
        subprocess.run(
            [sys.executable, str(HERE / "evaluate.py"), "--db", str(DB),
             "--dataset", str(HERE / "eval_dataset.jsonl"), "--out", str(out)],
            check=True, capture_output=True,
        )
        data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        review = (out / "review.csv").read_text(encoding="utf-8").splitlines()
    summary = data["summary"]
    assert summary["questions_total"] == 20
    assert summary["answerable"] == 18 and summary["out_of_scope"] == 2
    assert summary["hits"] == 16 and abs(summary["source_hit_rate_at_k"] - 16 / 18) < 1e-4
    assert len(review) == 21  # header + 20 rows


if __name__ == "__main__":
    import sys

    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print("FAIL", name, repr(exc))
    sys.exit(1 if failed else 0)
