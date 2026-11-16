#!/usr/bin/env bash
# Rebuild the 55-file corpus used by ingest.py.
# Source: astral-sh/uv at a pinned commit, docs/ directory minus docs/guides/.
set -euo pipefail

REPO_URL="https://github.com/astral-sh/uv.git"
COMMIT="d5c3f174417418c24ec3c276e01b0f62b961b13c"
OUT="${1:-corpus}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git init -q "$TMP/uv"
git -C "$TMP/uv" remote add origin "$REPO_URL"
git -C "$TMP/uv" fetch -q --depth 1 origin "$COMMIT"
git -C "$TMP/uv" checkout -q FETCH_HEAD

rm -rf "$OUT"
mkdir -p "$OUT"
(cd "$TMP/uv/docs" && find . -type f -name '*.md' ! -path './guides/*' -print0) |
  while IFS= read -r -d '' f; do
    mkdir -p "$OUT/$(dirname "$f")"
    cp "$TMP/uv/docs/$f" "$OUT/$f"
  done

echo "Corpus written to $OUT: $(find "$OUT" -name '*.md' | wc -l) files (expected 55)"
