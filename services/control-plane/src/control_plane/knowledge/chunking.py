"""Structure-aware Markdown chunking for the J.5 knowledge pipeline.

A parsed document (Markdown text) is sliced into retrieval chunks that:

* respect Markdown block structure — a chunk never cuts mid-paragraph
  or mid-table (markdown-it parses the block grammar);
* are bounded by a **token** budget (tiktoken-counted — char counts
  mislead badly for CJK);
* never straddle two document sections — a heading change flushes the
  current chunk;
* carry a **heading-path prefix** — each chunk is prefixed with the
  breadcrumb of the section it came from, so a short factual chunk is
  still findable ("免赔额是 500 元" → prefixed "[Section: 健康保险 > 免赔额]");
* **overlap** within a section so content near a chunk boundary is not
  lost;
* keep tables whole, splitting an oversized table by rows (header
  retained) and an oversized paragraph on sentence boundaries.

Semantic-similarity refinement (splitting a long heading-less section
at topic shifts) is a separate pass — see ``chunking_semantic`` (J.5
PR5b). See ``docs/streams/STREAM-J-DESIGN.md`` § 12.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import tiktoken
from markdown_it import MarkdownIt

#: tiktoken encoding for the token budget. An approximation of the
#: embedding model's tokenizer — exact enough for *sizing* chunks.
_ENCODING_NAME = "cl100k_base"
_encoding = tiktoken.get_encoding(_ENCODING_NAME)

#: markdown-it block tokens (at nesting level 0) that open a content block.
_CONTENT_OPENERS = frozenset(
    {"paragraph_open", "bullet_list_open", "ordered_list_open", "blockquote_open"}
)
#: markdown-it standalone block tokens that are content.
_CONTENT_STANDALONE = frozenset({"fence", "code_block", "html_block"})

#: Sentence-ish boundary for hard-splitting an oversized paragraph —
#: after an ASCII or CJK sentence-ending punctuation mark, or a newline.
#: The CJK marks in the class are intentional (noqa: ambiguous-unicode).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？\n])\s+")  # noqa: RUF001


def count_tokens(text: str) -> int:
    """Token count of ``text`` under the chunking tokenizer."""
    return len(_encoding.encode(text))


@dataclass(frozen=True)
class _Block:
    """One top-level Markdown block, tagged with its section path."""

    kind: Literal["content", "table"]
    text: str
    heading_trail: tuple[str, ...]


def chunk_markdown(markdown: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Slice ``markdown`` into heading-prefixed retrieval chunks.

    ``max_tokens`` bounds a chunk's body; ``overlap_tokens`` of the
    previous chunk's tail is carried into the next chunk *within the
    same section*. Returns chunk texts in document order; empty input
    yields an empty list.
    """
    blocks = _parse_blocks(markdown)
    chunks: list[str] = []
    trail: tuple[str, ...] = ()
    buffer: list[str] = []
    buffer_tokens = 0

    def flush(*, carry_overlap: bool) -> None:
        nonlocal buffer, buffer_tokens
        if not buffer:
            return
        body = "\n\n".join(buffer)
        chunks.append(_with_prefix(trail, body))
        tail = _tail_text(body, overlap_tokens) if carry_overlap else ""
        buffer = [tail] if tail.strip() else []
        buffer_tokens = count_tokens(tail) if buffer else 0

    for block in blocks:
        if block.heading_trail != trail:
            flush(carry_overlap=False)
            trail = block.heading_trail
        for piece in _prepare_block(block, max_tokens):
            piece_tokens = count_tokens(piece)
            if buffer and buffer_tokens + piece_tokens > max_tokens:
                flush(carry_overlap=True)
            buffer.append(piece)
            buffer_tokens += piece_tokens
    flush(carry_overlap=False)
    return chunks


def _parse_blocks(markdown: str) -> list[_Block]:
    """Parse ``markdown`` into top-level content / table blocks, each
    tagged with the heading breadcrumb of the section it sits in."""
    tokens = MarkdownIt().enable("table").parse(markdown)
    lines = markdown.splitlines()
    blocks: list[_Block] = []
    trail_stack: list[tuple[int, str]] = []
    for index, token in enumerate(tokens):
        if token.level != 0 or token.map is None:
            continue
        if token.type == "heading_open":
            level = int(token.tag[1:])
            text = tokens[index + 1].content.strip() if index + 1 < len(tokens) else ""
            while trail_stack and trail_stack[-1][0] >= level:
                trail_stack.pop()
            trail_stack.append((level, text))
            continue
        start, end = token.map
        block_text = "\n".join(lines[start:end]).strip()
        if not block_text:
            continue
        trail = tuple(text for _, text in trail_stack)
        if token.type == "table_open":
            blocks.append(_Block("table", block_text, trail))
        elif token.type in _CONTENT_OPENERS or token.type in _CONTENT_STANDALONE:
            blocks.append(_Block("content", block_text, trail))
    return blocks


def _prepare_block(block: _Block, max_tokens: int) -> list[str]:
    """Return ``block`` as one or more pieces, each within ``max_tokens``."""
    if count_tokens(block.text) <= max_tokens:
        return [block.text]
    if block.kind == "table":
        return _split_table(block.text, max_tokens)
    return _hard_split(block.text, max_tokens)


def _split_table(table: str, max_tokens: int) -> list[str]:
    """Split an oversized Markdown table by rows, repeating the header +
    separator rows in every part so each part is a valid table."""
    lines = table.splitlines()
    if len(lines) <= 2:  # header + separator only — nothing to split
        return [table]
    header = "\n".join(lines[:2])
    parts: list[str] = []
    current: list[str] = []
    for row in lines[2:]:
        candidate = "\n".join([header, *current, row])
        if current and count_tokens(candidate) > max_tokens:
            parts.append("\n".join([header, *current]))
            current = [row]
        else:
            current.append(row)
    if current:
        parts.append("\n".join([header, *current]))
    return parts


def _hard_split(text: str, max_tokens: int) -> list[str]:
    """Split oversized prose on sentence boundaries, packing to the cap;
    a single sentence still over the cap is split by raw tokens."""
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for unit in _SENTENCE_BOUNDARY.split(text):
        if not unit:
            continue
        unit_tokens = count_tokens(unit)
        if unit_tokens > max_tokens:
            if current:
                parts.append(" ".join(current))
                current, current_tokens = [], 0
            parts.extend(_split_by_tokens(unit, max_tokens))
            continue
        if current and current_tokens + unit_tokens > max_tokens:
            parts.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(unit)
        current_tokens += unit_tokens
    if current:
        parts.append(" ".join(current))
    return parts


def _split_by_tokens(text: str, max_tokens: int) -> list[str]:
    """Last-resort split of an unbreakable run on raw token windows."""
    token_ids = _encoding.encode(text)
    return [
        _encoding.decode(token_ids[i : i + max_tokens])
        for i in range(0, len(token_ids), max_tokens)
    ]


def _tail_text(text: str, overlap_tokens: int) -> str:
    """The last ``overlap_tokens`` tokens of ``text`` as text."""
    if overlap_tokens <= 0:
        return ""
    token_ids = _encoding.encode(text)
    if len(token_ids) <= overlap_tokens:
        return text
    return _encoding.decode(token_ids[-overlap_tokens:])


def _with_prefix(trail: tuple[str, ...], body: str) -> str:
    """Prefix ``body`` with its section breadcrumb for retrieval context."""
    if not trail:
        return body
    return f"[Section: {' > '.join(trail)}]\n\n{body}"
