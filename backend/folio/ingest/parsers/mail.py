from email import policy
from email.parser import BytesParser
from pathlib import Path

from folio.ingest.parsers.base import ParseError, Section, clean, decode_bytes


def _body(message) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, UnicodeDecodeError):
        content = decode_bytes(part.get_payload(decode=True) or b"")
    if part.get_content_subtype() == "html":
        from bs4 import BeautifulSoup

        content = BeautifulSoup(content, "lxml").get_text("\n")
    return content


def parse_eml(path: Path) -> list[Section]:
    try:
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    except Exception as exc:
        raise ParseError(f"invalid email: {exc}") from exc
    subject = str(message.get("subject", "")).strip() or None
    header = "\n".join(
        f"{name}: {message[name]}" for name in ("From", "To", "Cc", "Date", "Subject") if message[name]
    )
    attachments = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
    text = clean(f"{header}\n\n{_body(message)}")
    if attachments:
        text += "\n\nAttachments: " + ", ".join(attachments)
    return [Section(text, heading=subject)] if text else []


def parse_msg(path: Path) -> list[Section]:
    # sin dependencias extra para OLE: rescatamos los strings UTF-16 del binario
    raw = path.read_bytes()
    chunks: list[str] = []
    current = bytearray()
    for i in range(0, len(raw) - 1, 2):
        pair = raw[i : i + 2]
        if pair[1] == 0 and (32 <= pair[0] < 127 or pair[0] in (9, 10, 13)):
            current.extend(pair)
            continue
        if len(current) >= 40:
            chunks.append(current.decode("utf-16-le"))
        current.clear()
    text = clean("\n".join(dict.fromkeys(chunks)))
    return [Section(text)] if text else []
