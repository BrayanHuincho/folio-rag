import threading
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    spec: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[None, :]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def split_spec(spec: str) -> tuple[str, str]:
    provider, sep, model = spec.partition(":")
    if not sep or not model:
        raise ValueError(f"Invalid model spec {spec!r}, expected provider:model")
    return provider.strip().lower(), model.strip()


_cache: dict[str, Embedder] = {}
_lock = threading.Lock()


def get_embedder(spec: str) -> Embedder:
    with _lock:
        if spec in _cache:
            return _cache[spec]
        provider, model = split_spec(spec)
        if provider == "local":
            from folio.embed.local import LocalEmbedder

            embedder: Embedder = LocalEmbedder(spec, model)
        else:
            from folio.embed.remote import RemoteEmbedder

            embedder = RemoteEmbedder(spec, provider, model)
        _cache[spec] = embedder
        return embedder
