import hashlib
import re

import numpy as np
import pytest

from folio import config, db, embed
from folio.index import store

DIM = 64


class FakeEmbedder:
    spec = "fake:hash"
    dim = DIM

    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM
                matrix[row, bucket] += 1.0
        return embed.normalize(matrix)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("FOLIO_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FOLIO_EMBEDDINGS", FakeEmbedder.spec)
    config.get_settings.cache_clear()
    embed._cache[FakeEmbedder.spec] = FakeEmbedder()
    db.init_db()
    yield config.get_settings()
    store._matrices.clear()
    config.get_settings.cache_clear()
