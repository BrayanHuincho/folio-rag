import re
from dataclasses import dataclass

import numpy as np

from folio.db import connect
from folio.embed import get_embedder
from folio.index.store import collection_matrix

CANDIDATES = 50
RRF_K = 60
MMR_LAMBDA = 0.7

_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    rel_path: str
    page: int | None
    heading: str | None
    text: str
    score: float


def fts_query(text: str) -> str:
    # cada término va entre comillas para que el usuario no pueda inyectar sintaxis FTS5
    terms = [term for term in _TOKEN.findall(text.lower()) if len(term) > 1 or term.isdigit()]
    return " OR ".join(f'"{term}"' for term in dict.fromkeys(terms))


def _like_pattern(path_filter: str) -> str:
    escaped = path_filter.replace("\\", "/").replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def _allowed_chunks(conn, collection_id: str, path_filter: str | None) -> set[str] | None:
    if not path_filter:
        return None
    rows = conn.execute(
        "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE c.collection_id = ? AND replace(d.rel_path, '\\', '/') LIKE ? ESCAPE '!'",
        (collection_id, _like_pattern(path_filter)),
    ).fetchall()
    return {row["id"] for row in rows}


def _vector_candidates(conn, collection_id: str, query_vec: np.ndarray, allowed: set[str] | None):
    matrix = collection_matrix(conn, collection_id)
    if not matrix.chunk_ids or matrix.vectors.shape[1] != query_vec.shape[0]:
        return [], matrix
    scores = matrix.vectors @ query_vec
    if allowed is not None:
        mask = np.fromiter((cid in allowed for cid in matrix.chunk_ids), dtype=bool, count=len(matrix.chunk_ids))
        scores = np.where(mask, scores, -np.inf)
    top = np.argsort(-scores)[:CANDIDATES]
    return [matrix.chunk_ids[i] for i in top if np.isfinite(scores[i])], matrix


def _keyword_candidates(conn, collection_id: str, query: str, allowed: set[str] | None) -> list[str]:
    match = fts_query(query)
    if not match:
        return []
    rows = conn.execute(
        "SELECT c.id FROM chunks_fts f JOIN chunks c ON c.rowid = f.rowid"
        " WHERE chunks_fts MATCH ? AND c.collection_id = ? ORDER BY bm25(chunks_fts) LIMIT ?",
        (match, collection_id, CANDIDATES * 4 if allowed is not None else CANDIDATES),
    ).fetchall()
    ids = [row["id"] for row in rows]
    if allowed is not None:
        ids = [cid for cid in ids if cid in allowed]
    return ids[:CANDIDATES]


def rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return scores


def mmr(ids: list[str], relevance: dict[str, float], vectors: dict[str, np.ndarray], k: int,
        lam: float = MMR_LAMBDA) -> list[str]:
    if not ids:
        return []
    top = max(relevance[i] for i in ids)
    norm = {i: relevance[i] / top for i in ids} if top > 0 else dict.fromkeys(ids, 0.0)
    selected: list[str] = []
    remaining = list(ids)
    while remaining and len(selected) < k:
        def value(candidate: str) -> float:
            vec = vectors.get(candidate)
            if vec is None or not selected:
                return lam * norm[candidate]
            similarity = max(
                (float(vec @ vectors[s]) for s in selected if s in vectors), default=0.0
            )
            return lam * norm[candidate] - (1 - lam) * similarity

        best = max(remaining, key=value)
        selected.append(best)
        remaining.remove(best)
    return selected


def search(
    collection_id: str,
    query: str,
    k: int,
    *,
    path_filter: str | None = None,
    document_ids: list[str] | None = None,
) -> list[Hit]:
    conn = connect()
    row = conn.execute("SELECT embeddings FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if row is None or not query.strip() or k <= 0:
        return []
    allowed = _allowed_chunks(conn, collection_id, path_filter)
    if document_ids:
        placeholders = ",".join("?" * len(document_ids))
        scoped = {
            r["id"]
            for r in conn.execute(
                f"SELECT id FROM chunks WHERE document_id IN ({placeholders})", document_ids
            )
        }
        allowed = scoped if allowed is None else allowed & scoped

    query_vec = get_embedder(row["embeddings"]).embed_query(query)
    vector_ids, matrix = _vector_candidates(conn, collection_id, query_vec, allowed)
    keyword_ids = _keyword_candidates(conn, collection_id, query, allowed)

    fused = rrf([vector_ids, keyword_ids])
    ranked = sorted(fused, key=fused.get, reverse=True)
    index = {cid: i for i, cid in enumerate(matrix.chunk_ids)} if ranked else {}
    vectors = {cid: matrix.vectors[index[cid]] for cid in ranked if cid in index}
    chosen = mmr(ranked, fused, vectors, k)
    if not chosen:
        return []

    placeholders = ",".join("?" * len(chosen))
    rows = conn.execute(
        "SELECT c.id, c.document_id, d.rel_path, c.page, c.heading, c.text FROM chunks c"
        f" JOIN documents d ON d.id = c.document_id WHERE c.id IN ({placeholders})",
        chosen,
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [
        Hit(cid, by_id[cid]["document_id"], by_id[cid]["rel_path"], by_id[cid]["page"],
            by_id[cid]["heading"], by_id[cid]["text"], fused[cid])
        for cid in chosen
        if cid in by_id
    ]
