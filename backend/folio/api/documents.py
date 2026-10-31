from __future__ import annotations

import csv
import io
import mimetypes
from pathlib import Path

import chardet
import openpyxl
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from folio.db import connect

router = APIRouter(tags=["documents"])

MAX_ROWS = 1000
MAX_COLS = 60

DOCUMENT_FIELDS = "id, rel_path, ext, size, status, error, chunk_count, indexed_at"


@router.get("/collections/{collection_id}/documents")
def list_documents(collection_id: str, q: str | None = None) -> list[dict]:
    sql = f"SELECT {DOCUMENT_FIELDS} FROM documents WHERE collection_id = ?"
    params: list = [collection_id]
    if q:
        sql += " AND rel_path LIKE ? ESCAPE '\\'"
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    rows = connect().execute(sql + " ORDER BY rel_path", params).fetchall()
    return [dict(row) for row in rows]


@router.get("/documents/{document_id}")
def get_document(document_id: str) -> dict:
    conn = connect()
    row = conn.execute(
        f"SELECT {DOCUMENT_FIELDS} FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Documento no encontrado")
    chunks = conn.execute(
        "SELECT id, ord, page, heading, text FROM chunks WHERE document_id = ? ORDER BY ord",
        (document_id,),
    ).fetchall()
    return {**dict(row), "chunks": [dict(c) for c in chunks]}


def _document_path(document_id: str) -> tuple[Path, str | None]:
    row = connect().execute(
        "SELECT path, mime FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Documento no encontrado")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(404, "El archivo ya no existe en el disco")
    return path, row["mime"]


@router.get("/documents/{document_id}/table")
def table_document(document_id: str) -> dict:
    path, _ = _document_path(document_id)
    ext = path.suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        sheets = _excel_sheets(path)
    elif ext in (".csv", ".tsv"):
        sheets = [{"name": path.stem, **_csv_rows(path, "\t" if ext == ".tsv" else ",")}]
    else:
        raise HTTPException(415, "Este archivo no se puede mostrar como tabla")
    return {"sheets": sheets, "max_rows": MAX_ROWS}


def _excel_sheets(path: Path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = []
        for sheet in workbook.worksheets:
            rows, truncated = [], False
            for i, values in enumerate(sheet.iter_rows(values_only=True)):
                if i >= MAX_ROWS:
                    truncated = True
                    break
                rows.append(["" if v is None else str(v) for v in values[:MAX_COLS]])
            sheets.append({"name": sheet.title, "rows": _trim(rows), "truncated": truncated})
        return sheets
    finally:
        workbook.close()


def _csv_rows(path: Path, delimiter: str) -> dict:
    raw = path.read_bytes()
    encoding = chardet.detect(raw[:65536])["encoding"] or "utf-8"
    reader = csv.reader(io.StringIO(raw.decode(encoding, errors="replace")), delimiter=delimiter)
    rows = []
    for i, values in enumerate(reader):
        if i >= MAX_ROWS:
            return {"rows": _trim(rows), "truncated": True}
        rows.append(values[:MAX_COLS])
    return {"rows": _trim(rows), "truncated": False}


def _trim(rows: list[list[str]]) -> list[list[str]]:
    # openpyxl suele reportar columnas y filas vacías al final de la hoja
    while rows and not any(rows[-1]):
        rows.pop()
    width = max((i + 1 for row in rows for i, v in enumerate(row) if v), default=0)
    return [row[:width] + [""] * (width - len(row)) for row in rows]


@router.get("/documents/{document_id}/raw")
def raw_document(document_id: str) -> FileResponse:
    path, mime = _document_path(document_id)
    media_type = mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, content_disposition_type="inline",
                        filename=path.name)
