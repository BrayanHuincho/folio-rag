from collections.abc import Callable
from pathlib import Path

from folio.ingest.parsers import code, data, documents, images, mail, markup, sheets, slides
from folio.ingest.parsers.base import ParseError, Section, UnsupportedFile
from folio.ingest.parsers.images import describe_image, set_image_describer

Parser = Callable[[Path], list[Section]]

PARSERS: dict[str, Parser] = {
    ".pdf": documents.parse_pdf,
    ".docx": documents.parse_docx,
    ".docm": documents.parse_docx,
    ".odt": documents.parse_odt,
    ".rtf": documents.parse_rtf,
    ".epub": documents.parse_epub,
    ".xlsx": sheets.parse_xlsx,
    ".xlsm": sheets.parse_xlsx,
    ".ods": sheets.parse_ods,
    ".csv": sheets.parse_csv,
    ".tsv": sheets.parse_csv,
    ".pptx": slides.parse_pptx,
    ".html": markup.parse_html,
    ".htm": markup.parse_html,
    ".xhtml": markup.parse_html,
    ".md": markup.parse_markdown,
    ".markdown": markup.parse_markdown,
    ".mdx": markup.parse_markdown,
    ".rst": markup.parse_markdown,
    ".txt": markup.parse_plain,
    ".text": markup.parse_plain,
    ".log": markup.parse_plain,
    ".tex": markup.parse_plain,
    ".org": markup.parse_plain,
    ".adoc": markup.parse_plain,
    ".srt": markup.parse_plain,
    ".vtt": markup.parse_plain,
    ".env": markup.parse_plain,
    ".xml": markup.parse_xml,
    ".svg": markup.parse_xml,
    ".json": data.parse_json,
    ".jsonl": data.parse_jsonl,
    ".ndjson": data.parse_jsonl,
    ".yaml": data.parse_yaml,
    ".yml": data.parse_yaml,
    ".toml": data.parse_toml,
    ".ini": data.parse_ini,
    ".cfg": data.parse_ini,
    ".conf": data.parse_ini,
    ".ipynb": data.parse_ipynb,
    ".eml": mail.parse_eml,
    ".msg": mail.parse_msg,
    ".png": images.parse_image,
    ".jpg": images.parse_image,
    ".jpeg": images.parse_image,
    ".webp": images.parse_image,
}
PARSERS.update({ext: code.parse_code for ext in code.LANGUAGES if ext not in PARSERS})

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parser_for(path: Path) -> Parser | None:
    parser = PARSERS.get(path.suffix.lower())
    if parser is None and code.language_for(path):
        parser = code.parse_code
    return parser


def supported(path: Path) -> bool:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        from folio.config import get_settings

        return get_settings().ocr
    return parser_for(path) is not None


def parse(path: Path) -> list[Section]:
    parser = parser_for(path)
    if parser is None:
        raise UnsupportedFile(f"no parser for {path.suffix or path.name}")
    try:
        sections = parser(path)
    except (UnsupportedFile, ParseError):
        raise
    except Exception as exc:
        raise ParseError(f"{type(exc).__name__}: {exc}") from exc
    return [section for section in sections if section.text.strip()]


__all__ = [
    "ParseError",
    "Section",
    "UnsupportedFile",
    "describe_image",
    "parse",
    "set_image_describer",
    "supported",
]
