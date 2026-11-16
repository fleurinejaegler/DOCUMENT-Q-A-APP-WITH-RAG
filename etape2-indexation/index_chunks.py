#!/usr/bin/env python3
"""Step 2: embed chunks with all-MiniLM-L6-v2 and index them in ChromaDB.

Usage:
    python3 index_chunks.py --chunks chunks.jsonl --db chroma_db --collection docs
    python3 index_chunks.py --chunks chunks.jsonl --db chroma_db --query "how to pin the python version"

Behaviour:
  - Always rebuilds from scratch: the Chroma directory and the collection are
    wiped before indexing, so re-running gives the same index (full re-run).
  - Chunk IDs are the chunk_id values from step 1 (source#chunk_index), checked unique.
  - Each chunk is stored with its text, its embedding and its metadata.
  - Reports chunks longer than the model's token limit (they are truncated when embedded).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH = 128
METADATA_KEYS = ("source", "doc_title", "section", "chunk_index", "split", "char_count")


def load_chunks(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    ids = [r["chunk_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate chunk_id values in the input")
    return rows


def build_index(chunks_path: Path, db_dir: Path, collection_name: str) -> dict:
    rows = load_chunks(chunks_path)

    model = SentenceTransformer(MODEL_NAME)
    max_tokens = model.max_seq_length
    too_long = sum(
        len(model.tokenizer(r["text"], add_special_tokens=True)["input_ids"]) > max_tokens
        for r in rows
    )

    embeddings = model.encode(
        [r["text"] for r in rows],
        batch_size=BATCH,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    if db_dir.exists():
        shutil.rmtree(db_dir)  # full rebuild from scratch
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine", "embedding_model": MODEL_NAME},
    )

    for start in range(0, len(rows), BATCH):
        batch = rows[start : start + BATCH]
        collection.add(
            ids=[r["chunk_id"] for r in batch],
            documents=[r["text"] for r in batch],
            embeddings=embeddings[start : start + BATCH].tolist(),
            metadatas=[{k: r[k] for k in METADATA_KEYS} for r in batch],
        )

    return {
        "model": MODEL_NAME,
        "max_seq_length_tokens": max_tokens,
        "chunks_in": len(rows),
        "chunks_indexed": collection.count(),
        "chunks_over_token_limit": too_long,
        "embedding_dim": int(embeddings.shape[1]),
        "db_dir": str(db_dir),
        "collection": collection_name,
    }


def query_index(db_dir: Path, collection_name: str, question: str, k: int) -> list[dict]:
    model = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_collection(collection_name)
    q = model.encode([question], normalize_embeddings=True).tolist()
    res = collection.query(query_embeddings=q, n_results=k, include=["documents", "metadatas", "distances"])
    out = []
    for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"id": cid, "distance": round(dist, 4), "source": meta["source"],
                    "section": meta["section"], "preview": doc[:120]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True, type=Path)
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--collection", default="docs")
    ap.add_argument("--query", help="run a retrieval query after indexing (or alone, without rebuilding)")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--skip-build", action="store_true", help="only query the existing index")
    args = ap.parse_args()

    if not args.skip_build:
        report = build_index(args.chunks, args.db, args.collection)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.query:
        for hit in query_index(args.db, args.collection, args.query, args.k):
            print(json.dumps(hit, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
