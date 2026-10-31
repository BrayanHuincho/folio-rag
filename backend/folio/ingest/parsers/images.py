from collections.abc import Callable
from pathlib import Path

from folio.config import get_settings
from folio.ingest.parsers.base import Section, UnsupportedFile

ImageDescriber = Callable[[Path], str | None]

_describer: ImageDescriber | None = None


def set_image_describer(describer: ImageDescriber | None) -> None:
    global _describer
    _describer = describer


def describe_image(path: Path) -> str | None:
    return _describer(path) if _describer else None


def parse_image(path: Path) -> list[Section]:
    if not get_settings().ocr or _describer is None:
        raise UnsupportedFile("image description is disabled")
    text = (describe_image(path) or "").strip()
    return [Section(text, heading=path.name)] if text else []
