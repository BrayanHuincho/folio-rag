from pathlib import Path

from folio.ingest.parsers.base import ParseError, Section, clean


def parse_pptx(path: Path) -> list[Section]:
    from pptx import Presentation

    try:
        deck = Presentation(str(path))
    except Exception as exc:
        raise ParseError(f"cannot open presentation: {exc}") from exc
    sections = []
    for number, slide in enumerate(deck.slides, start=1):
        title = None
        if slide.shapes.title is not None and slide.shapes.title.has_text_frame:
            title = slide.shapes.title.text_frame.text.strip() or None
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            elif getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if notes:
                parts.append(f"Notes: {notes}")
        text = clean("\n".join(parts))
        if text:
            sections.append(Section(text, page=number, heading=title))
    return sections
