"""Streamlit app for the uv documentation RAG, ready for deployment (Step 5).

Self-contained folder: app.py, rag.py, requirements.txt and chroma_db/ (the Step 2 index).
Secrets: ANTHROPIC_API_KEY (and optionally LLM_MODEL) can come from the environment
or from Streamlit secrets (st.secrets) on Streamlit Community Cloud.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import rag

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "chroma_db"
LOG_PATH = Path(os.environ.get("RAG_LOG_PATH", HERE / "logs" / "interactions.jsonl"))


def _load_secrets_into_env() -> None:
    """Copy secrets from Streamlit's secrets store into the environment, if set there."""
    try:
        for key in ("ANTHROPIC_API_KEY", "LLM_MODEL"):
            if key in st.secrets and not os.environ.get(key):
                os.environ[key] = str(st.secrets[key])
    except Exception:  # no secrets file (local run): the environment variables are used
        pass


_load_secrets_into_env()

st.set_page_config(page_title="Questions on the UV Document", page_icon="📚")
st.title("Questions on the UV Document")


@st.cache_resource(show_spinner="Chargement de l'index…")
def get_retriever(db_dir: str) -> rag.Retriever:
    return rag.Retriever(Path(db_dir))


with st.sidebar:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        st.warning("API key missing : only the context will be displayed.")
    with st.expander("Advanced parameters"):
        db_dir = st.text_input("Dossier ChromaDB", str(DEFAULT_DB))

retriever = get_retriever(db_dir)

with st.form("question_form"):
    question = st.text_input("Your question")
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    passages = retriever.search(question)
    system, user = rag.build_messages(question, passages)

    answer_text = None
    error = None
    if has_key:
        with st.spinner("Génération de la réponse…"):
            try:
                answer_text = rag.generate(system, user)
            except Exception as exc:  # show the API error instead of crashing the page
                error = str(exc)
                st.error(f"Échec de la génération : {error}")
    cited = rag.cited_labels(answer_text, passages) if answer_text else set()

    try:
        rag.log_interaction(rag.make_record(question, passages, answer_text, cited, error), LOG_PATH)
    except OSError:
        pass  # some hosts make the app folder read-only; logging is best-effort there

    st.subheader("Réponse")
    if answer_text:
        st.markdown(answer_text)
    else:
        st.info("Pas de réponse générée. Les passages récupérés sont listés ci-dessous.")

    st.subheader("Sources")
    for p in passages:
        marker = " ✓ cité" if p.label in cited else ""
        st.markdown(f"[{p.label}] `{p.source}` — {p.section}{marker}")

    st.subheader("Contexte récupéré")
    for p in passages:
        with st.expander(f"[{p.label}] {p.source} (score {p.score})"):
            st.text(p.text)
