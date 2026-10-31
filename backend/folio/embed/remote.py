import httpx
import numpy as np

from folio.config import Settings, get_settings
from folio.embed import normalize

BATCH_SIZE = 64


def _endpoint(provider: str, settings: Settings) -> tuple[str, str]:
    presets = {
        "openai": ("https://api.openai.com/v1", settings.openai_api_key),
        "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            settings.gemini_api_key,
        ),
        "mistral": ("https://api.mistral.ai/v1", settings.mistral_api_key),
        "ollama": (f"{settings.ollama_base_url.rstrip('/')}/v1", ""),
        "lmstudio": (f"{settings.lmstudio_base_url.rstrip('/')}/v1", ""),
    }
    if provider not in presets:
        raise ValueError(f"Provider {provider!r} does not offer embeddings")
    return presets[provider]


class RemoteEmbedder:
    def __init__(self, spec: str, provider: str, model: str):
        self.spec = spec
        self.model = model
        base_url, api_key = _endpoint(provider, get_settings())
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=120)
        self.dim = 0

    def _request(self, texts: list[str]) -> np.ndarray:
        response = self._client.post("/embeddings", json={"model": self.model, "input": texts})
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item.get("index", 0))
        return np.array([item["embedding"] for item in data], dtype=np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        parts = [self._request(texts[i : i + BATCH_SIZE]) for i in range(0, len(texts), BATCH_SIZE)]
        matrix = normalize(np.vstack(parts))
        self.dim = matrix.shape[1]
        return matrix

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
