"""Checks that the deploy folder works on its own (no step2/ folder, no API key needed).

Run from this folder: python3 test_deploy.py
"""
from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def test_index_is_inside_the_deploy_folder():
    assert (HERE / "chroma_db" / "chroma.sqlite3").exists()


def test_app_runs_and_answers_without_key():
    from streamlit.testing.v1 import AppTest

    os.environ.pop("ANTHROPIC_API_KEY", None)
    at = AppTest.from_file(str(HERE / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception
    question = next(t for t in at.text_input if t.label == "Votre question")
    question.set_value("how do I pin the Python version for a project")
    at.button[0].click().run()
    assert not at.exception
    passage_expanders = [e for e in at.expander if e.label.startswith("[")]
    assert len(passage_expanders) == 3  # the sidebar "Paramètres avancés" expander is not counted


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
