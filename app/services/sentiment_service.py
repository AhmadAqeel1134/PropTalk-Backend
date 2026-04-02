"""
Sentiment analysis via external PropTalk sentiment service (user-only text).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def extract_user_only_transcript_text(
    transcript_json: Optional[Any],
    transcript_plain: Optional[str],
) -> str:
    """
    Build text for sentiment from **user** turns only.
    - Prefer structured transcript_json: messages with role 'user' (not assistant/system).
    - Do not use plain `transcript` when transcript_json exists (avoids mixing agent lines).
    - If no user lines in JSON, return empty string (caller may fall back to user_pov_summary).
    """
    if transcript_json and isinstance(transcript_json, list):
        parts: List[str] = []
        for msg in transcript_json:
            if not isinstance(msg, dict):
                continue
            role = (msg.get("role") or "").strip().lower()
            if role != "user":
                continue
            content = (msg.get("content") or "").strip()
            if content:
                parts.append(content)
        return "\n".join(parts).strip()

    # No structured JSON: plain transcript may mix agent + user — do not send to model
    return ""


def text_for_sentiment(
    user_pov_summary: Optional[str],
    transcript_json: Optional[Any],
    transcript_plain: Optional[str],
) -> Optional[str]:
    """
    Only when user_pov_summary is present (exchange occurred). User-only text from JSON,
    else fallback to user_pov_summary when JSON has no user lines.
    """
    if not user_pov_summary or not str(user_pov_summary).strip():
        return None

    user_text = extract_user_only_transcript_text(transcript_json, transcript_plain)
    if user_text:
        return user_text

    return str(user_pov_summary).strip() or None


async def analyze_sentiment(text: str) -> Optional[Dict[str, Any]]:
    """POST /analyze-sentiment; returns { sentiment, scores } or None on failure."""
    url = settings.SENTIMENT_SERVICE_URL.rstrip("/") + "/analyze-sentiment"
    payload = {"text": text}
    timeout = settings.SENTIMENT_REQUEST_TIMEOUT_SECONDS
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if r.status_code != 200:
                logger.warning(
                    "Sentiment API error: %s %s",
                    r.status_code,
                    r.text[:500],
                )
                return None
            data = r.json()
            sentiment = data.get("sentiment")
            scores = data.get("scores")
            if not sentiment:
                return None
            return {"sentiment": str(sentiment).lower(), "scores": scores or {}}
    except Exception as e:
        logger.error("Sentiment request failed: %s", e, exc_info=True)
        return None
