"""Streamlit interface for the uv documentation RAG app.

Run from this folder:
    streamlit run app.py
Set ANTHROPIC_API_KEY to get generated answers. Without it, the retrieved context is still shown.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import rag

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE.parent / "step2" / "chroma_db"

st.set_page_config(page_title="Questions sur la documentation uv", page_icon="📚")
st.title("Questions sur la documentation uv")


@st.cache_resource(show_spinner="Chargement de l'index…")
def get_retriever(db_dir: str) -> rag.Retriever:
    return rag.Retriever(Path(db_dir))


with st.sidebar:
    db_dir = st.text_input("Dossier ChromaDB", str(DEFAULT_DB))
    st.caption(f"Modèle : {os.environ.get('LLM_MODEL', rag.DEFAULT_LLM)}")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        st.warning("ANTHROPIC_API_KEY non défini : seul le contexte récupéré sera affiché.")

retriever = get_retriever(db_dir)

with st.form("question_form"):
    question = st.text_input("Votre question")
    submitted = st.form_submit_button("Demander")

if submitted and question.strip():
    passages = retriever.search(question)
    system, user = rag.build_messages(question, passages)

    answer_text = None
    if has_key:
        with st.spinner("Génération de la réponse…"):
            try:
                answer_text = rag.generate(system, user)
            except Exception as exc:  # show the API error instead of crashing the page
                st.error(f"Échec de la génération : {exc}")
    cited = rag.cited_labels(answer_text, passages) if answer_text else set()

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
        with st.expander(f"[{p.label}] {p.source} (distance {p.distance})"):
            st.text(p.text)
