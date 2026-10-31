import sqlite3
import threading
import uuid
from dataclasses import dataclass

import numpy as np

from folio.ingest.chunker import Chunk


@dataclass
class Matrix:
    chunk_ids: list[str]
    vectors: np.ndarray


_matrices: dict[str, Matrix] = {}
_lock = threading.Lock()


def invalidate(collection_id: str) -> None:
    with _lock:
        _matrices.pop(collection_id, None)


def collection_matrix(conn: sqlite3.Connection, collection_id: str) -> Matrix:
    with _lock:
        cached = _matrices.get(collection_id)
    if cached is not None:
        return cached
    rows = conn.execute(
        "SELECT chunk_id, dim, vec FROM vectors WHERE collection_id = ?", (collection_id,)
    ).fetchall()
    if rows:
        # si cambió el modelo de embeddings puede haber dims mezcladas; nos quedamos con la mayoritaria
        dims = [row["dim"] for row in rows]
        dim = max(set(dims), key=dims.count)
        rows = [row for row in rows if row["dim"] == dim]
        vectors = np.frombuffer(b"".join(row["vec"] for row in rows), dtype=np.float32).reshape(len(rows), dim)
        matrix = Matrix([row["chunk_id"] for row in rows], vectors)
    else:
        matrix = Matrix([], np.zeros((0, 0), dtype=np.float32))
    with _lock:
        _matrices[collection_id] = matrix
    return matrix


def replace_document_chunks(
    conn: sqlite3.Connection,
    collection_id: str,
    document_id: str,
    chunks: list[Chunk],
    vectors: np.ndarray,
) -> None:
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    with conn:
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        for item, vector in zip(chunks, vectors):
            chunk_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO chunks (id, document_id, collection_id, ord, text, page, heading, start_char, end_char)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (chunk_id, document_id, collection_id, item.ord, item.text, item.page, item.heading,
                 item.start_char, item.end_char),
            )
            conn.execute(
                "INSERT INTO vectors (chunk_id, collection_id, dim, vec) VALUES (?, ?, ?, ?)",
                (chunk_id, collection_id, int(vector.shape[0]), vector.tobytes()),
            )
    invalidate(collection_id)


def delete_document(conn: sqlite3.Connection, collection_id: str, document_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    invalidate(collection_id)


def clear_document_chunks(conn: sqlite3.Connection, collection_id: str, document_id: str) -> None:
    with conn:
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    invalidate(collection_id)
