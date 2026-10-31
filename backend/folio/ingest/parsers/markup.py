import re
from pathlib import Path

from folio.ingest.parsers.base import Section, clean, read_text

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_RST_UNDERLINE = re.compile(r"^([=\-~^\"'`#*+])\1{2,}\s*$")


def parse_plain(path: Path) -> list[Section]:
    text = clean(read_text(path))
    return [Section(text)] if text else []


def parse_markdown(path: Path) -> list[Section]:
    lines = read_text(path).splitlines()
    sections: list[Section] = []
    heading: str | None = None
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        text = clean("\n".join(buffer))
        if text:
            sections.append(Section(text, heading=heading))
        buffer.clear()

    for index, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        title = None
        if not in_fence:
            match = _MD_HEADING.match(line)
            if match:
                title = match.group(2)
            elif (
                path.suffix.lower() == ".rst"
                and index + 1 < len(lines)
                and line.strip()
                and _RST_UNDERLINE.match(lines[index + 1])
            ):
                title = line.strip()
        if title:
            flush()
            heading = title
        buffer.append(line)
    flush()
    return sections


def parse_html(path: Path) -> list[Section]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(read_text(path), "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe"]):
        tag.decompose()
    page_title = soup.title.get_text(strip=True) if soup.title else None
    body = soup.body or soup

    sections: list[Section] = []
    heading = page_title
    buffer: list[str] = []
    headings = {"h1", "h2", "h3", "h4"}
    blocks = headings | {"p", "li", "pre", "blockquote", "td", "th", "dt", "dd", "figcaption"}

    for element in body.find_all(blocks):
        if element.find_parent(blocks - headings - {"pre"}) is not None and element.name not in headings:
            continue
        text = element.get_text(" " if element.name != "pre" else "", strip=element.name != "pre")
        if not text.strip():
            continue
        if element.name in headings:
            if buffer:
                sections.append(Section(clean("\n\n".join(buffer)), heading=heading))
                buffer = []
            heading = text.strip()
        buffer.append(text)
    if buffer:
        sections.append(Section(clean("\n\n".join(buffer)), heading=heading))
    if not sections:
        text = clean(body.get_text("\n"))
        if text:
            sections.append(Section(text, heading=page_title))
    return sections


def parse_xml(path: Path) -> list[Section]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(read_text(path), "lxml-xml")
    text = clean(soup.get_text("\n"))
    return [Section(text)] if text else []
