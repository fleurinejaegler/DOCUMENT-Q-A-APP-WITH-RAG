#!/usr/bin/env python3
"""Ingestion pipeline for a document collection (markdown, text, HTML).

Steps:
  1. Load every supported file under --input (recursively).
  2. Extract plain text (markdown syntax / HTML tags removed, headings kept).
  3. Skip files whose extracted content is empty.
  4. Split by headings (header-based splitting). Sections longer than
     --max-chars fall back to fixed-size windows with --overlap characters.
  5. Attach metadata to each chunk: source, doc_title, section (heading path),
     chunk_index (position within the document), split strategy, char_count.
  6. Write chunks to --output/chunks.jsonl and statistics to --output/stats.json.

Standard library only. Run with `python3 -I` because it reads untrusted files.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".html", ".htm"}
HTML_SUFFIXES = {".html", ".htm"}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\([^)]*\)")  # one level of nested brackets
SNIPPET_RE = re.compile(r"^\s*--8<--")  # MkDocs snippet include directive
HTML_TAG_RE = re.compile(
    r"</?(?:details|summary|kbd|br|img|span|div|p|a|b|i|em|strong|sup|sub|"
    r"table|tr|td|th|figure|figcaption)\b[^>]*>",
    re.I,
)


@dataclass
class Chunk:
    chunk_id: str
    source: str
    doc_title: str
    section: str
    chunk_index: int
    split: str  # "header" (whole section) or "fixed" (fallback window)
    char_count: int
    text: str


# ---------------------------------------------------------------- extraction

class _HTMLToMarkdown(HTMLParser):
    """Turn HTML into markdown-like text so headings survive for splitting."""

    SKIP = {"script", "style", "noscript", "nav", "footer"}
    BLOCK = {"p", "div", "li", "tr", "section", "article", "pre", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n" + "#" * int(tag[1]) + " ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def extract_text(path: Path) -> str:
    """Return the document as markdown-like plain text (headings preserved)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in HTML_SUFFIXES:
        parser = _HTMLToMarkdown()
        parser.feed(raw)
        return "".join(parser.parts)
    if path.suffix.lower() in {".md", ".markdown"}:
        return FRONT_MATTER_RE.sub("", raw, count=1)
    return raw  # .txt: no structure, handled by fixed-size fallback


def clean_inline(line: str) -> str:
    """Remove markdown/HTML markup from one line of prose, keep the words."""
    line = line.replace("**", "").replace("`", "")  # first, so links like [`x`](u) match
    line = IMAGE_RE.sub(r"\1", line)
    line = LINK_RE.sub(r"\1", line)
    line = HTML_TAG_RE.sub("", line)
    line = re.sub(r"^\s*>\s?", "", line)  # blockquote marker
    return line.rstrip()


# ---------------------------------------------------------------- splitting

def split_by_headers(text: str) -> list[tuple[str, str]]:
    """Return (heading_path, body) pairs. Headings inside code fences are ignored."""
    sections: list[tuple[str, str]] = []
    path: list[tuple[int, str]] = []  # stack of (level, title)
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            heading = " > ".join(title for _, title in path) or "(intro)"
            sections.append((heading, body))
        buf.clear()

    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue  # fence markers carry no content
        if in_fence:
            buf.append(line)  # keep code verbatim
            continue
        match = HEADING_RE.match(line)
        if match:
            flush()
            level, title = len(match.group(1)), clean_inline(match.group(2))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, title))
            buf.append(title)  # heading text stays in the body so chunks read alone
        elif SNIPPET_RE.match(line):
            continue  # include directive, not content
        else:
            buf.append(clean_inline(line))
    flush()
    return sections


def merge_small_sections(sections: list[tuple[str, str]], min_chars: int) -> list[tuple[str, str]]:
    """Fold sections shorter than min_chars into a neighbour so no chunk is a bare heading.

    A short section waits and is joined to the following section (its heading
    describes the content that follows). A trailing short section is appended
    to the previous one.
    """
    merged: list[tuple[str, str]] = []
    pending: tuple[str, str] | None = None
    for heading, body in sections:
        if pending is not None:
            body = f"{pending[1]}\n\n{body}"
        if len(body) < min_chars:
            pending = (heading, body)
            continue
        merged.append((heading, body))
        pending = None
    if pending is not None:
        if merged:
            heading, body = merged[-1]
            merged[-1] = (heading, f"{body}\n\n{pending[1]}")
        else:
            merged.append(pending)
    return merged


def fixed_windows(text: str, max_chars: int, overlap: int) -> list[str]:
    """Fallback splitter: fixed-size windows, cut at a space when one is nearby."""
    if len(text) <= max_chars:
        return [text]
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + max_chars // 2, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            windows.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)  # always make progress
    return windows


def doc_title_of(sections: list[tuple[str, str]], fallback: str) -> str:
    for heading, _ in sections:
        first = heading.split(" > ")[0]
        if first and first != "(intro)":
            return first
    return fallback


def chunk_document(
    rel_source: str, text: str, max_chars: int, overlap: int, min_chars: int
) -> list[Chunk]:
    sections = split_by_headers(text)
    title = doc_title_of(sections, Path(rel_source).stem)
    sections = merge_small_sections(sections, min_chars)
    pieces: list[tuple[str, str, str]] = []  # (section, text, split)
    for heading, body in sections:
        if len(body) <= max_chars:
            pieces.append((heading, body, "header"))
        else:
            for window in fixed_windows(body, max_chars, overlap):
                pieces.append((heading, window, "fixed"))

    chunks: list[Chunk] = []
    for index, (heading, body, split) in enumerate(pieces):
        if not body.strip():
            continue  # skip empty content
        chunks.append(
            Chunk(
                chunk_id=f"{rel_source}#{index}",
                source=rel_source,
                doc_title=title,
                section=heading,
                chunk_index=index,
                split=split,
                char_count=len(body),
                text=body,
            )
        )
    return chunks


# ---------------------------------------------------------------- pipeline

def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


def run(input_dir: Path, output_dir: Path, max_chars: int, overlap: int, min_chars: int) -> dict:
    if overlap >= max_chars:
        raise SystemExit("--overlap must be smaller than --max-chars")
    output_dir.mkdir(parents=True, exist_ok=True)

    files_seen = 0
    files_skipped_empty: list[str] = []
    chunks: list[Chunk] = []

    for path in iter_files(input_dir):
        files_seen += 1
        rel = path.relative_to(input_dir).as_posix()
        text = extract_text(path)
        if not text.strip():
            files_skipped_empty.append(rel)
            continue
        doc_chunks = chunk_document(rel, text, max_chars, overlap, min_chars)
        if not doc_chunks:
            files_skipped_empty.append(rel)
            continue
        chunks.extend(doc_chunks)

    sizes = [c.char_count for c in chunks]
    stats = {
        "input_dir": str(input_dir),
        "files_seen": files_seen,
        "files_loaded": files_seen - len(files_skipped_empty),
        "files_skipped_empty": files_skipped_empty,
        "total_chunks": len(chunks),
        "chunks_from_header_split": sum(c.split == "header" for c in chunks),
        "chunks_from_fixed_fallback": sum(c.split == "fixed" for c in chunks),
        "avg_chunk_chars": round(statistics.fmean(sizes), 1) if sizes else 0,
        "median_chunk_chars": statistics.median(sizes) if sizes else 0,
        "min_chunk_chars": min(sizes) if sizes else 0,
        "max_chunk_chars": max(sizes) if sizes else 0,
        "max_chunk_setting": max_chars,
        "overlap_setting": overlap,
        "min_section_setting": min_chars,
    }

    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")
    (output_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--min-chars", type=int, default=200,
                        help="sections shorter than this are merged into a neighbour")
    args = parser.parse_args()
    if not args.input.is_dir():
        sys.exit(f"input directory not found: {args.input}")
    stats = run(args.input, args.output, args.max_chars, args.overlap, args.min_chars)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
