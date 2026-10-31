import csv
import io
import zipfile
from collections.abc import Iterable
from pathlib import Path
from xml.etree import ElementTree

from folio.ingest.parsers.base import ParseError, Section, read_text

# agrupamos filas y repetimos el header para que cada chunk conserve el nombre de las columnas
GROUP_CHARS = 2400


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip().replace("\n", " ")


def table_sections(rows: Iterable[list[str]], name: str | None) -> list[Section]:
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    header_line = " | ".join(header)
    if not body:
        return [Section(header_line, heading=name)]

    sections: list[Section] = []
    group: list[str] = []
    first = 2
    size = 0

    def emit(last: int) -> None:
        label = f"rows {first}-{last}"
        heading = f"{name} ({label})" if name else label
        sections.append(Section("\n".join([header_line, *group]), heading=heading))

    for index, row in enumerate(body, start=2):
        line = " | ".join(
            f"{header[i]}: {cell}" if i < len(header) and header[i] else cell
            for i, cell in enumerate(row)
            if cell
        )
        if group and size + len(line) > GROUP_CHARS:
            emit(index - 1)
            group, size, first = [], 0, index
        group.append(line)
        size += len(line) + 1
    emit(first + len(group) - 1)
    return sections


def parse_csv(path: Path) -> list[Section]:
    text = read_text(path)
    if path.suffix.lower() == ".tsv":
        dialect: type[csv.Dialect] | csv.Dialect = csv.excel_tab
    else:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
    rows = [[_fmt(cell) for cell in row] for row in csv.reader(io.StringIO(text), dialect)]
    return table_sections(rows, None)


def parse_xlsx(path: Path) -> list[Section]:
    import openpyxl

    try:
        workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        raise ParseError(f"cannot open workbook: {exc}") from exc
    sections: list[Section] = []
    try:
        for sheet in workbook.worksheets:
            rows = ([_fmt(cell) for cell in row] for row in sheet.iter_rows(values_only=True))
            sections.extend(table_sections(rows, sheet.title))
    finally:
        workbook.close()
    return sections


_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"


def parse_ods(path: Path) -> list[Section]:
    try:
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("content.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise ParseError(f"invalid spreadsheet: {exc}") from exc
    repeat_attr = f"{{{_TABLE}}}number-columns-repeated"
    sections: list[Section] = []
    for table in root.iter(f"{{{_TABLE}}}table"):
        rows = []
        for row in table.iter(f"{{{_TABLE}}}table-row"):
            cells: list[str] = []
            for cell in row.iter(f"{{{_TABLE}}}table-cell"):
                value = " ".join("".join(cell.itertext()).split())
                # las celdas vacías del final vienen como una sola repetida miles de veces
                repeat = int(cell.get(repeat_attr, "1")) if value else 1
                cells.extend([value] * min(repeat, 100))
            while cells and not cells[-1]:
                cells.pop()
            rows.append(cells)
        sections.extend(table_sections(rows, table.get(f"{{{_TABLE}}}name")))
    return sections
