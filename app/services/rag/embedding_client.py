"""
Text embeddings for RAG: Gemini (preferred) or OpenAI, matched at index and query time.
"""
from __future__ import annotations

import logging
from typing import List, Literal, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_shared_client: Optional[httpx.AsyncClient] = None


def _client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )
    return _shared_client


def resolve_embedding_backend() -> Optional[Literal["gemini", "openai"]]:
    if settings.GEMINI_API_KEY:
        return "gemini"
    if settings.OPENAI_API_KEY:
        return "openai"
    return None


def embedding_model_id() -> Tuple[str, str]:
    """Returns (backend, model_label_for_storage)."""
    b = resolve_embedding_backend()
    if b == "gemini":
        m = getattr(settings, "GEMINI_EMBEDDING_MODEL", None) or "gemini-embedding-001"
        return "gemini", f"gemini:{m}"
    if b == "openai":
        m = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "text-embedding-3-small"
        return "openai", f"openai:{m}"
    raise ValueError("No embedding API key configured (GEMINI_API_KEY or OPENAI_API_KEY)")


async def embed_text(text: str) -> List[float]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Cannot embed empty text")
    backend, _ = embedding_model_id()
    if backend == "gemini":
        return await _embed_gemini(text)
    return await _embed_openai(text)


async def _embed_gemini(text: str) -> List[float]:
    configured = getattr(settings, "GEMINI_EMBEDDING_MODEL", None) or "gemini-embedding-001"
    # Some keys/projects expose different embedding model aliases.
    candidates = []
    for m in [configured, "gemini-embedding-001", "text-embedding-004"]:
        if m and m not in candidates:
            candidates.append(m)

    client = _client()
    errors: List[str] = []
    for model in candidates:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"
            f"?key={settings.GEMINI_API_KEY}"
        )
        payload = {
            "model": f"models/{model}",
            "content": {"parts": [{"text": text}]},
        }
        r = await client.post(url, json=payload)
        if r.status_code == 200:
            data = r.json()
            values = data.get("embedding", {}).get("values")
            if not isinstance(values, list) or not values:
                raise ValueError("Unexpected Gemini embedding response")
            return [float(x) for x in values]
        errors.append(f"{model}:{r.status_code}")
        # 404 means this model alias is not available; try next alias.
        if r.status_code == 404:
            continue
        logger.error("Gemini embed error model=%s status=%s body=%s", model, r.status_code, r.text)
        raise ValueError(f"Gemini embedding failed with model {model}: {r.text}")

    raise ValueError(
        "Gemini embedding failed for all model aliases. "
        f"Tried {', '.join(candidates)}; statuses={', '.join(errors)}"
    )


async def _embed_openai(text: str) -> List[float]:
    model = getattr(settings, "OPENAI_EMBEDDING_MODEL", None) or "text-embedding-3-small"
    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "input": text}
    client = _client()
    r = await client.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        logger.error("OpenAI embed error %s: %s", r.status_code, r.text)
        raise ValueError(f"OpenAI embedding failed: {r.text}")
    data = r.json()
    arr = data.get("data", [])
    if not arr or "embedding" not in arr[0]:
        raise ValueError("Unexpected OpenAI embedding response")
    return [float(x) for x in arr[0]["embedding"]]
