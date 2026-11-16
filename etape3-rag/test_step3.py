"""Offline checks for Step 3. The LLM is replaced by a fake generator, so no API key is needed.

Run: python3 -m pytest -q test_step3.py   (or: python3 test_step3.py)
"""
from __future__ import annotations

import os
from pathlib import Path

import rag

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "step2" / "chroma_db"


def _retriever() -> rag.Retriever:
    return rag.Retriever(DB)


def test_search_returns_top3_with_labels():
    passages = _retriever().search("how do I pin the Python version for a project")
    assert [p.label for p in passages] == [1, 2, 3]
    assert all(p.source and p.text for p in passages)
    assert all(p.distance >= 0 for p in passages)


def test_prompt_contains_labels_question_and_restriction():
    passages = _retriever().search("where is the uv cache directory stored")
    system, user = rag.build_messages("where is the uv cache directory stored", passages)
    assert "ONLY" in system and "bracketed" in system
    for p in passages:
        assert f"[{p.label}] Source: {p.source}" in user
    assert user.endswith("Question: where is the uv cache directory stored")


def test_cited_labels_ignores_unknown_labels():
    passages = _retriever().search("export the lockfile to requirements.txt")
    assert rag.cited_labels("Use export [1] and sync [2][9].", passages) == {1, 2}
    assert rag.cited_labels("No citation here.", passages) == set()


def test_answer_pipeline_with_fake_generator():
    retriever = _retriever()
    seen = {}

    def fake(system, user):
        seen["user"] = user
        return "Voir [2] pour le détail."

    result = rag.answer(retriever, "what does uv run do", generator=fake)
    assert "Question: what does uv run do" in seen["user"]
    assert result["cited"] == [2]
    assert len(result["passages"]) == 3


def test_generate_without_key_raises():
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        try:
            rag.generate("s", "u")
        except RuntimeError as exc:
            assert "ANTHROPIC_API_KEY" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


def _question_input(at):
    return next(t for t in at.text_input if t.label == "Votre question")


def test_streamlit_app_without_key_shows_sources_and_context():
    from streamlit.testing.v1 import AppTest

    os.environ.pop("ANTHROPIC_API_KEY", None)
    at = AppTest.from_file(str(HERE / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception
    _question_input(at).set_value("how do I pin the Python version for a project")
    at.button[0].click().run()
    assert not at.exception
    assert len(at.expander) == 3
    rendered = " ".join(m.value for m in at.markdown)
    assert "[1]" in rendered and "[2]" in rendered and "[3]" in rendered
    assert any("Pas de réponse générée" in i.value for i in at.info)


def test_streamlit_app_with_key_shows_answer_and_cited_source():
    from streamlit.testing.v1 import AppTest

    os.environ["ANTHROPIC_API_KEY"] = "test-key-not-used"
    original = rag.generate
    rag.generate = lambda system, user, **kw: "La réponse vient du passage [1]."
    try:
        at = AppTest.from_file(str(HERE / "app.py"), default_timeout=300)
        at.run()
        _question_input(at).set_value("what does uv run do")
        at.button[0].click().run()
        assert not at.exception
        rendered = " ".join(m.value for m in at.markdown)
        assert "La réponse vient du passage [1]." in rendered
        assert "✓ cité" in rendered
    finally:
        rag.generate = original
        os.environ.pop("ANTHROPIC_API_KEY", None)


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
