from __future__ import annotations

import time

import httpx

from folio.config import get_settings

from .anthropic import API_URL as ANTHROPIC_URL
from .anthropic import API_VERSION as ANTHROPIC_VERSION
from .anthropic import AnthropicClient
from .base import ChatMessage, LLMClient, LLMError
from .openai_compat import OpenAICompatClient

__all__ = [
    "ChatMessage",
    "LLMClient",
    "LLMError",
    "configured_providers",
    "get_client",
    "list_models",
    "parse_spec",
]

PROVIDERS = [
    "openrouter",
    "openai",
    "anthropic",
    "gemini",
    "groq",
    "mistral",
    "deepseek",
    "ollama",
    "lmstudio",
]
LOCAL_PROVIDERS = {"ollama", "lmstudio"}

BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

OPENROUTER_HEADERS = {"HTTP-Referer": "https://github.com/folio-rag/folio", "X-Title": "Folio"}

MODELS_TTL = 600
_models_cache: dict[str, tuple[float, list[dict]]] = {}


def parse_spec(spec: str) -> tuple[str, str]:
    provider, sep, model = spec.partition(":")
    provider = provider.strip().lower()
    if not sep or not model or provider not in PROVIDERS:
        raise LLMError(
            f"Invalid model spec {spec!r}; expected 'provider:model' with provider in "
            + ", ".join(PROVIDERS)
        )
    return provider, model.strip()


def _api_key(provider: str) -> str | None:
    return getattr(get_settings(), f"{provider}_api_key", None) or None


def _base_url(provider: str) -> str:
    settings = get_settings()
    if provider in LOCAL_PROVIDERS:
        root = getattr(settings, f"{provider}_base_url")
        return f"{str(root).rstrip('/')}/v1"
    return BASE_URLS[provider]


def configured_providers() -> list[str]:
    return [p for p in PROVIDERS if p in LOCAL_PROVIDERS or _api_key(p)]


def get_client(spec: str | None = None) -> LLMClient:
    spec = spec or get_settings().llm
    provider, model = parse_spec(spec)
    key = _api_key(provider)
    if provider not in LOCAL_PROVIDERS and not key:
        raise LLMError(
            f"Falta la API key de {provider}. Agrega {provider.upper()}_API_KEY en .env "
            f"y reinicia el servidor para usar {spec}."
        )
    if provider == "anthropic":
        return AnthropicClient(spec, model, key)
    headers = OPENROUTER_HEADERS if provider == "openrouter" else None
    return OpenAICompatClient(spec, model, _base_url(provider), key, headers)


async def list_models(provider: str) -> list[dict]:
    cached = _models_cache.get(provider)
    if cached and time.monotonic() - cached[0] < MODELS_TTL:
        return cached[1]
    try:
        models = await _fetch_models(provider)
    except (httpx.HTTPError, ValueError, KeyError):
        models = []
    _models_cache[provider] = (time.monotonic(), models)
    return models


async def _fetch_models(provider: str) -> list[dict]:
    key = _api_key(provider)
    async with httpx.AsyncClient(timeout=10.0) as client:
        if provider == "ollama":
            root = str(get_settings().ollama_base_url).rstrip("/")
            response = await client.get(f"{root}/api/tags")
            response.raise_for_status()
            return [
                _model(provider, m["name"], m["name"], None)
                for m in response.json().get("models", [])
            ]

        if provider == "anthropic":
            response = await client.get(
                f"{ANTHROPIC_URL}/models",
                params={"limit": 100},
                headers={"x-api-key": key or "", "anthropic-version": ANTHROPIC_VERSION},
            )
            response.raise_for_status()
            return [
                _model(provider, m["id"], m.get("display_name") or m["id"], None)
                for m in response.json().get("data", [])
            ]

        headers = {"Authorization": f"Bearer {key}"} if key else {}
        response = await client.get(f"{_base_url(provider)}/models", headers=headers)
        response.raise_for_status()
        models = []
        for m in response.json().get("data", []):
            if not _is_chat_model(m):
                continue
            model_id = m["id"].removeprefix("models/")  # gemini antepone "models/" a los ids
            entry = _model(provider, model_id, m.get("name") or model_id, m.get("context_length"))
            entry.update(_pricing(m.get("pricing")))
            models.append(entry)
        return sorted(models, key=lambda m: m["id"])


NON_CHAT_HINTS = (
    "embed", "tts", "whisper", "dall-e", "moderation", "transcribe", "realtime",
    "image", "audio", "rerank", "search", "computer-use", "batch",
)


def _is_chat_model(model: dict) -> bool:
    model_id = model["id"].lower()
    # las listas traen embeddings, voz e imagen mezclados con los de chat
    if any(hint in model_id for hint in NON_CHAT_HINTS):
        return False
    outputs = (model.get("architecture") or {}).get("output_modalities")
    return outputs is None or outputs == ["text"]


def _pricing(pricing: dict | None) -> dict:
    # openrouter da el precio por token como texto; lo pasamos a dólares por millón
    if not pricing:
        return {}
    try:
        prompt = float(pricing.get("prompt") or 0) * 1_000_000
        completion = float(pricing.get("completion") or 0) * 1_000_000
    except (TypeError, ValueError):
        return {}
    if prompt < 0 or completion < 0:
        return {}
    return {
        "free": prompt == 0 and completion == 0,
        "price_in": round(prompt, 4),
        "price_out": round(completion, 4),
    }


def _model(provider: str, model_id: str, name: str, context: int | None) -> dict:
    return {"id": f"{provider}:{model_id}", "name": name, "context": context}
