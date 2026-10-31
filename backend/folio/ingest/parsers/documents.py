import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from folio.ingest.parsers.base import ParseError, Section, clean, read_text


def parse_pdf(path: Path) -> list[Section]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
    except Exception as exc:
        raise ParseError(f"cannot open PDF: {exc}") from exc
    sections = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            text = clean(page.extract_text() or "")
        except Exception:
            continue
        if text:
            sections.append(Section(text, page=number))
    return sections


def parse_docx(path: Path) -> list[Section]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = docx.Document(str(path))
    sections: list[Section] = []
    heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        text = clean("\n\n".join(buffer))
        if text:
            sections.append(Section(text, heading=heading))
        buffer.clear()

    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
            if style.startswith("heading") or style == "title":
                flush()
                heading = text
            buffer.append(text)
        elif tag == "tbl":
            rows = []
            for row in Table(element, document).rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                buffer.append("\n".join(rows))
    flush()
    return sections


_ODF_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def _odf_root(path: Path) -> ElementTree.Element:
    try:
        with zipfile.ZipFile(path) as archive:
            return ElementTree.fromstring(archive.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ParseError(f"invalid OpenDocument file: {exc}") from exc


def parse_odt(path: Path) -> list[Section]:
    root = _odf_root(path)
    sections: list[Section] = []
    heading: str | None = None
    buffer: list[str] = []
    for element in root.iter():
        if element.tag == f"{{{_ODF_TEXT}}}h":
            text = "".join(element.itertext()).strip()
            if buffer:
                sections.append(Section(clean("\n\n".join(buffer)), heading=heading))
                buffer = []
            heading = text or heading
            if text:
                buffer.append(text)
        elif element.tag == f"{{{_ODF_TEXT}}}p":
            text = "".join(element.itertext()).strip()
            if text:
                buffer.append(text)
    if buffer:
        sections.append(Section(clean("\n\n".join(buffer)), heading=heading))
    return sections


_RTF_DESTINATIONS = re.compile(
    r"\{(?:\\\*)?\\(?:fonttbl|colortbl|stylesheet|info|pict|header|footer|generator)[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
)


def rtf_to_text(raw: str) -> str:
    text = _RTF_DESTINATIONS.sub("", raw)
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes.fromhex(m.group(1)).decode("cp1252"), text)
    text = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), text)
    text = re.sub(r"\\(par|line)\b ?", "\n", text)
    text = re.sub(r"\\tab\b ?", "\t", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
    text = re.sub(r"\\([{}\\])", r"\1", text)
    return text.replace("{", "").replace("}", "")


def parse_rtf(path: Path) -> list[Section]:
    text = clean(rtf_to_text(read_text(path)))
    return [Section(text)] if text else []


def parse_epub(path: Path) -> list[Section]:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
    except Exception as exc:
        raise ParseError(f"cannot open EPUB: {exc}") from exc
    sections = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        title = soup.find(["h1", "h2", "h3", "title"])
        text = clean(soup.get_text("\n"))
        if text:
            sections.append(Section(text, heading=title.get_text(strip=True) if title else None))
    return sections
