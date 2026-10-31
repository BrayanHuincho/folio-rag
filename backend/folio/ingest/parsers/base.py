from dataclasses import dataclass
from pathlib import Path

import chardet


@dataclass
class Section:
    text: str
    page: int | None = None
    heading: str | None = None


class UnsupportedFile(Exception):
    pass


class ParseError(Exception):
    pass


def decode_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    if b"\x00" in raw[:8192]:
        raise UnsupportedFile("binary content")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    guess = chardet.detect(raw[:200_000])
    return raw.decode(guess.get("encoding") or "latin-1", errors="replace")


def read_text(path: Path) -> str:
    return decode_bytes(path.read_bytes())


def clean(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    out: list[str] = []
    blank = 0
    for line in lines:
        blank = blank + 1 if not line.strip() else 0
        if blank <= 1:
            out.append(line)
    return "\n".join(out).strip()
