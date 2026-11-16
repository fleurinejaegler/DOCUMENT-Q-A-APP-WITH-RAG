"""Step 3: semantic search, RAG prompt and answer generation.

- Retriever.search(question) returns the top-3 chunks from the Step 2 ChromaDB index.
- build_messages() builds a prompt that restricts the answer to the retrieved passages
  and asks for bracketed citation labels such as [1] or [2].
- generate() calls the Anthropic API. It needs ANTHROPIC_API_KEY in the environment.
  The model defaults to claude-haiku-5-5 and can be changed with LLM_MODEL.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import chromadb
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LLM = "claude-haiku-5-5"
TOP_K = 3

SYSTEM_PROMPT = (
    "You answer questions about the uv documentation. "
    "Use ONLY the numbered passages given in the user message, and no outside knowledge. "
    "If the passages do not contain the answer, say that the documents do not cover it. "
    "Cite the passage supporting each statement with its bracketed label, for example [1] or [2][3]. "
    "Only use labels that appear in the passages."
)

CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass
class Passage:
    label: int  # 1..k, written as [label] in the answer
    chunk_id: str
    source: str
    section: str
    text: str
    distance: float


class Retriever:
    def __init__(self, db_dir: Path, collection: str = "docs"):
        self.model = SentenceTransformer(EMBED_MODEL)
        client = chromadb.PersistentClient(path=str(db_dir))
        self.collection = client.get_collection(collection)

    def search(self, question: str, k: int = TOP_K) -> list[Passage]:
        query = self.model.encode([question], normalize_embeddings=True).tolist()
        res = self.collection.query(
            query_embeddings=query,
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        passages: list[Passage] = []
        rows = zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])
        for label, (cid, doc, meta, dist) in enumerate(rows, start=1):
            passages.append(
                Passage(
                    label=label,
                    chunk_id=cid,
                    source=meta["source"],
                    section=meta["section"],
                    text=doc,
                    distance=round(dist, 4),
                )
            )
        return passages


def build_messages(question: str, passages: list[Passage]) -> tuple[str, str]:
    """Return (system prompt, user message) for the LLM."""
    context = "\n\n".join(
        f"[{p.label}] Source: {p.source} | Section: {p.section}\n{p.text}" for p in passages
    )
    user = f"Passages:\n\n{context}\n\nQuestion: {question}"
    return SYSTEM_PROMPT, user


def cited_labels(answer: str, passages: list[Passage]) -> set[int]:
    """Labels cited in the answer that match a retrieved passage."""
    valid = {p.label for p in passages}
    return {int(x) for x in CITATION_RE.findall(answer) if int(x) in valid}


def generate(system: str, user: str, model: str | None = None, max_tokens: int = 700) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    import anthropic  # imported here so the rest works without the SDK configured

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model or os.environ.get("LLM_MODEL", DEFAULT_LLM),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")


Generator = Callable[[str, str], str]


def answer(retriever: Retriever, question: str, generator: Generator = generate) -> dict:
    passages = retriever.search(question)
    system, user = build_messages(question, passages)
    text = generator(system, user)
    return {
        "question": question,
        "answer": text,
        "passages": passages,
        "cited": sorted(cited_labels(text, passages)),
    }
