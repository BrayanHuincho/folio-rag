import re
from dataclasses import dataclass

from folio.ingest.parsers.base import Section

CHARS_PER_TOKEN = 4

_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+|\n")
_FENCE = re.compile(r"^```.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)


@dataclass
class Chunk:
    ord: int
    text: str
    page: int | None
    heading: str | None
    start_char: int
    end_char: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _blocks(text: str) -> list[tuple[int, str]]:
    # los bloques de código no se parten por líneas vacías
    spans: list[tuple[int, int]] = []
    cursor = 0
    for fence in _FENCE.finditer(text):
        spans.extend(_paragraph_spans(text, cursor, fence.start()))
        spans.append((fence.start(), fence.end()))
        cursor = fence.end()
    spans.extend(_paragraph_spans(text, cursor, len(text)))
    return [(start, text[start:end]) for start, end in spans if text[start:end].strip()]


def _paragraph_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n[ \t]*\n|\Z)", text[start:end], re.DOTALL):
        spans.append((start + match.start(), start + match.end()))
    return spans


def _split_long(offset: int, text: str, limit: int) -> list[tuple[int, str]]:
    if len(text) <= limit:
        return [(offset, text)]
    pieces: list[tuple[int, str]] = []
    cursor = 0
    for match in _SENTENCE_END.finditer(text):
        if match.end() - cursor >= limit // 2 or match.end() - cursor > limit:
            pieces.append((offset + cursor, text[cursor : match.end()]))
            cursor = match.end()
    pieces.append((offset + cursor, text[cursor:]))

    out: list[tuple[int, str]] = []
    for start, piece in pieces:
        while len(piece) > limit:
            cut = piece.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            out.append((start, piece[:cut]))
            start, piece = start + cut, piece[cut:]
        if piece.strip():
            out.append((start, piece))
    return out


def _tail(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text if limit > 0 else ""
    tail = text[-limit:]
    boundary = _SENTENCE_END.search(tail)
    if boundary and boundary.end() < len(tail) // 2:
        return tail[boundary.end() :]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) // 2 else tail


def chunk(sections: list[Section], size: int, overlap: int) -> list[Chunk]:
    limit = max(200, size * CHARS_PER_TOKEN)
    overlap_chars = min(max(0, overlap) * CHARS_PER_TOKEN, limit // 2)
    chunks: list[Chunk] = []
    doc_offset = 0

    for section in sections:
        pieces: list[tuple[int, str]] = []
        for start, block in _blocks(section.text):
            pieces.extend(_split_long(start, block, limit))

        current: list[str] = []
        current_start = 0
        current_end = 0
        carry = ""

        def emit() -> None:
            body = "\n\n".join(current).strip()
            if not body:
                return
            text = f"{carry}\n\n{body}".strip() if carry else body
            chunks.append(
                Chunk(
                    ord=len(chunks),
                    text=text,
                    page=section.page,
                    heading=section.heading,
                    start_char=doc_offset + current_start,
                    end_char=doc_offset + current_end,
                )
            )

        for start, piece in pieces:
            length = sum(len(part) + 2 for part in current) + len(carry)
            if current and length + len(piece) > limit:
                emit()
                carry = _tail("\n\n".join(current), overlap_chars)
                current = []
            if not current:
                current_start = start
            current.append(piece.strip())
            current_end = start + len(piece)
        emit()
        doc_offset += len(section.text) + 2

    return chunks
