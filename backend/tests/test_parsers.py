import json
import zipfile
from pathlib import Path

import pytest

from folio.ingest import UnsupportedFile, parse, supported


def text_of(path: Path) -> str:
    return "\n".join(section.text for section in parse(path))


def test_plain_text_with_latin1(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_bytes("Canción de cuna para el niño pequeño, otra vez más.".encode("latin-1"))
    assert "Canción" in text_of(path)


def test_markdown_headings(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# Intro\nhello\n\n## Setup\n```\n# not a heading\n```\nrun it\n", encoding="utf-8")
    sections = parse(path)
    assert [s.heading for s in sections] == ["Intro", "Setup"]
    assert "# not a heading" in sections[1].text


def test_html_strips_chrome(tmp_path):
    path = tmp_path / "page.html"
    path.write_text(
        "<html><head><title>T</title><script>evil()</script></head><body><nav>menu</nav>"
        "<h1>Title</h1><p>Body text</p></body></html>",
        encoding="utf-8",
    )
    text = text_of(path)
    assert "Body text" in text and "evil" not in text and "menu" not in text


def test_csv_repeats_header(tmp_path):
    path = tmp_path / "data.csv"
    rows = ["name,city"] + [f"person{i},{'x' * 50}" for i in range(200)]
    path.write_text("\n".join(rows), encoding="utf-8")
    sections = parse(path)
    assert len(sections) > 1
    assert all(section.text.startswith("name | city") for section in sections)
    assert "name: person0" in sections[0].text


def test_json_and_jsonl(tmp_path):
    path = tmp_path / "a.json"
    path.write_text(json.dumps({"user": {"name": "Ada", "tags": ["x", "y"]}}), encoding="utf-8")
    assert "user.name: Ada" in text_of(path)
    lines = tmp_path / "b.jsonl"
    lines.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")
    assert "[2] a: 2" in text_of(lines)


def test_yaml_toml_ini(tmp_path):
    (tmp_path / "c.yaml").write_text("db:\n  host: localhost\n", encoding="utf-8")
    (tmp_path / "c.toml").write_text('[server]\nport = 8080\n', encoding="utf-8")
    (tmp_path / "c.ini").write_text("[main]\nkey = value\n", encoding="utf-8")
    assert "db.host: localhost" in text_of(tmp_path / "c.yaml")
    assert "server.port: 8080" in text_of(tmp_path / "c.toml")
    assert "key = value" in text_of(tmp_path / "c.ini")


def test_ipynb_cells(tmp_path):
    path = tmp_path / "n.ipynb"
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["# Analysis\n", "text"]},
        {"cell_type": "code", "source": "print(42)"},
    ]}
    path.write_text(json.dumps(notebook), encoding="utf-8")
    sections = parse(path)
    assert sections[1].heading == "Analysis" and "print(42)" in sections[1].text


def test_source_code_split_on_definitions(tmp_path):
    path = tmp_path / "mod.py"
    path.write_text("import os\n\ndef alpha():\n    return 1\n\nclass Beta:\n    pass\n", encoding="utf-8")
    headings = [s.heading for s in parse(path)]
    assert "mod.py: alpha" in headings and "mod.py: Beta" in headings


def test_rtf(tmp_path):
    path = tmp_path / "r.rtf"
    path.write_text(r"{\rtf1\ansi{\fonttbl\f0 Arial;}\f0 Hello \b world\b0\par Caf\'e9}", encoding="ascii")
    text = text_of(path)
    assert "Hello world" in text and "Café" in text and "Arial" not in text


def test_eml(tmp_path):
    path = tmp_path / "m.eml"
    path.write_text("From: a@b.c\nTo: d@e.f\nSubject: Budget\n\nThe budget is 42k.\n", encoding="utf-8")
    sections = parse(path)
    assert sections[0].heading == "Budget" and "42k" in sections[0].text


def test_docx(tmp_path):
    import docx

    document = docx.Document()
    document.add_heading("Chapter One", level=1)
    document.add_paragraph("It was a dark night.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "k", "v"
    path = tmp_path / "d.docx"
    document.save(path)
    sections = parse(path)
    assert sections[0].heading == "Chapter One"
    assert "dark night" in sections[0].text and "k | v" in sections[0].text


def test_xlsx(tmp_path):
    import openpyxl

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sales"
    sheet.append(["region", "total"])
    sheet.append(["north", 10])
    path = tmp_path / "s.xlsx"
    workbook.save(path)
    sections = parse(path)
    assert sections[0].heading.startswith("Sales") and "region: north" in sections[0].text


def test_pptx_with_notes(tmp_path):
    from pptx import Presentation

    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Roadmap"
    slide.placeholders[1].text = "Ship v1"
    slide.notes_slide.notes_text_frame.text = "Mention the date"
    path = tmp_path / "p.pptx"
    deck.save(path)
    section = parse(path)[0]
    assert section.page == 1 and section.heading == "Roadmap" and "Mention the date" in section.text


def test_pdf_pages(tmp_path):
    path = tmp_path / "x.pdf"
    path.write_bytes(_tiny_pdf(["First page text", "Second page text"]))
    sections = parse(path)
    assert [s.page for s in sections] == [1, 2] and "Second" in sections[1].text


def test_odt(tmp_path):
    ns = 'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" ' \
         'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
    content = f'<office:document-content {ns}><office:body><office:text>' \
              '<text:h>Heading</text:h><text:p>Paragraph body</text:p></office:text></office:body>' \
              '</office:document-content>'
    path = tmp_path / "o.odt"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("content.xml", content)
    section = parse(path)[0]
    assert section.heading == "Heading" and "Paragraph body" in section.text


def test_unsupported_and_binary(tmp_path):
    exe = tmp_path / "x.exe"
    exe.write_bytes(b"MZ\x00\x00")
    assert not supported(exe)
    fake = tmp_path / "bin.txt"
    fake.write_bytes(b"\x00\x01\x02" * 100)
    with pytest.raises(UnsupportedFile):
        parse(fake)


def test_images_skipped_without_ocr(tmp_path, settings):
    image = tmp_path / "i.png"
    image.write_bytes(b"\x89PNG\r\n")
    assert not supported(image)


def _tiny_pdf(pages: list[str]) -> bytes:
    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    font_id = 3 + len(pages) * 2
    for i, text in enumerate(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + i * 2} 0 R "
                       f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out
