import threading

import numpy as np

from folio.config import get_settings
from folio.embed import normalize

BATCH_SIZE = 64


class LocalEmbedder:
    def __init__(self, spec: str, model: str):
        from fastembed import TextEmbedding

        self.spec = spec
        self.model = model
        cache_dir = get_settings().data_dir / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._model = TextEmbedding(model_name=model, cache_dir=str(cache_dir))
        # onnxruntime no garantiza ser thread-safe con llamadas concurrentes
        self._lock = threading.Lock()
        self.dim = int(self.embed(["dimension probe"]).shape[1])

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, getattr(self, "dim", 0)), dtype=np.float32)
        with self._lock:
            vectors = list(self._model.embed(texts, batch_size=BATCH_SIZE))
        return normalize(np.vstack(vectors))

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
