from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx

from folio.config import get_settings

from . import OPENROUTER_HEADERS, _api_key, _base_url, parse_spec

PROMPT = (
    "Transcribe todo el texto visible en la imagen tal cual. "
    "Después describe en pocas líneas lo que muestra (gráficos, tablas, diagramas). "
    "Responde en el idioma del texto de la imagen."
)


def describe_image(path: Path) -> str | None:
    settings = get_settings()
    provider, model = parse_spec(settings.fast_llm or settings.llm)
    # anthropic usa otro formato de imagen; con los demás basta el esquema de openai
    if provider == "anthropic":
        return None

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    headers = {"Content-Type": "application/json"}
    if key := _api_key(provider):
        headers["Authorization"] = f"Bearer {key}"
    if provider == "openrouter":
        headers.update(OPENROUTER_HEADERS)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ],
            }
        ],
        "temperature": 0,
    }
    response = httpx.post(
        f"{_base_url(provider)}/chat/completions", json=payload, headers=headers, timeout=120
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
