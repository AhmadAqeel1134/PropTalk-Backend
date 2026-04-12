"""
ElevenLabs TTS Service — synthesize speech and serve audio to Twilio <Play>.

Used by:
  - webhook_service.py  (live calls)
  - voice_agent_controller.py  (browser preview)

Falls back gracefully when ELEVENLABS_API_KEY is unset or the API errors.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, NamedTuple, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# In-memory audio cache: token → (bytes, created_at)
_audio_cache: Dict[str, Tuple[bytes, datetime]] = {}
# Long enough for Twilio to fetch <Play> (including retries) after slow webhooks
_CACHE_TTL = timedelta(minutes=30)

# Dedup cache to avoid billing identical requests: content_hash → token
_dedup: Dict[str, str] = {}

# Shared async client (created lazily)
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
    return _client


def _prune_cache() -> None:
    """Remove expired entries (called before each insert)."""
    cutoff = datetime.utcnow() - _CACHE_TTL
    expired = [k for k, (_, ts) in _audio_cache.items() if ts < cutoff]
    for k in expired:
        _audio_cache.pop(k, None)
    expired_dedup = [h for h, tok in _dedup.items() if tok not in _audio_cache]
    for h in expired_dedup:
        _dedup.pop(h, None)


def is_enabled() -> bool:
    return bool(settings.ELEVENLABS_API_KEY)


def get_tts_cache_ttl_seconds() -> int:
    return int(_CACHE_TTL.total_seconds())


class TTSResult(NamedTuple):
    """Result of a TTS request. ``token`` set on success; otherwise check ``error_*``."""

    token: Optional[str] = None
    error_http_status: Optional[int] = None
    error_message: Optional[str] = None


def _elevenlabs_error_message(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        detail = data.get("detail")
        if isinstance(detail, dict):
            return (
                detail.get("message")
                or detail.get("code")
                or str(detail)[:240]
            )
        if isinstance(detail, str):
            return detail[:300]
    except Exception:
        pass
    body = (resp.text or "").strip()
    return body[:300] if body else f"HTTP {resp.status_code}"


async def synthesize_speech(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    speed: float = 1.0,
    *,
    allow_env_default_voice: bool = True,
) -> TTSResult:
    """
    Call ElevenLabs TTS and cache the MP3 bytes.

    On success, ``result.token`` is set (use with ``/tts/{token}``).
    On failure, ``result.token`` is None; Twilio callers should fall back to ``<Say>``.

    ``allow_env_default_voice``: when False (live calls), a missing ``voice_id`` does not
    fall back to ``ELEVENLABS_DEFAULT_VOICE_ID`` — callers must supply the agent's voice.
    """
    if not is_enabled():
        return TTSResult()

    vid = (voice_id or "").strip()
    if not vid:
        if allow_env_default_voice:
            vid = settings.ELEVENLABS_DEFAULT_VOICE_ID
        else:
            return TTSResult(error_message="elevenlabs_voice_id is required for this call")
    voice_id = vid
    model_id = model_id or settings.ELEVENLABS_MODEL_ID

    content_hash = hashlib.sha256(
        f"{text}|{voice_id}|{model_id}|{speed}".encode()
    ).hexdigest()[:24]

    if content_hash in _dedup:
        tok = _dedup[content_hash]
        if tok in _audio_cache:
            return TTSResult(token=tok)

    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id)

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": speed,
        },
    }

    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    try:
        client = _get_client()
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            msg = _elevenlabs_error_message(resp)
            logger.warning(
                f"ElevenLabs TTS returned {resp.status_code}: {msg[:200]}"
            )
            return TTSResult(
                error_http_status=resp.status_code,
                error_message=msg,
            )

        audio_bytes = resp.content
        if len(audio_bytes) < 512:
            logger.warning("ElevenLabs returned suspiciously small audio payload")
            return TTSResult(error_message="Invalid audio response from ElevenLabs")

        _prune_cache()
        token = uuid.uuid4().hex[:16]
        _audio_cache[token] = (audio_bytes, datetime.utcnow())
        _dedup[content_hash] = token
        logger.info(
            f"TTS OK — {len(audio_bytes):,} bytes, voice={voice_id}, token={token}"
        )
        return TTSResult(token=token)

    except httpx.TimeoutException:
        logger.warning("ElevenLabs TTS timed out")
        return TTSResult(error_message="ElevenLabs request timed out")
    except Exception as exc:
        logger.error(f"ElevenLabs TTS error: {exc}", exc_info=True)
        return TTSResult(error_message=str(exc)[:240])


def pop_audio(token: str) -> Optional[bytes]:
    """
    Retrieve (and remove) cached audio by token.
    Called by the ``GET /tts/{token}`` route.
    """
    entry = _audio_cache.pop(token, None)
    if entry is None:
        return None
    audio_bytes, _ = entry
    return audio_bytes


def peek_audio(token: str) -> Optional[bytes]:
    """
    Retrieve cached audio without removing it (for browser preview replay).
    """
    entry = _audio_cache.get(token)
    if entry is None:
        return None
    audio_bytes, _ = entry
    return audio_bytes
