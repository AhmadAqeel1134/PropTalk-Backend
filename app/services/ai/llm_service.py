"""
LLM Service - Handle Google Gemini API interactions
Optimized for fast responses with conversation history support.
Shared httpx.AsyncClient for persistent keep-alive connections.
"""
from typing import Dict, List, Optional
import json
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Default LLM settings (Gemini)
DEFAULT_MODEL = "gemini-2.5-flash-lite"  # Balanced model optimized for low latency
DEFAULT_MAX_TOKENS = 150
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TIMEOUT = 10.0

# Shared httpx client — reused across requests to keep TCP + TLS alive
_shared_client: Optional[httpx.AsyncClient] = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_client


async def process_with_llm(
    user_input: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout: float = DEFAULT_TIMEOUT
) -> str:
    """
    Process user input with Google Gemini API
    Supports conversation history for context-aware responses
    
    Args:
        user_input: The user's message/query
        system_prompt: System prompt with context
        conversation_history: Previous conversation messages
        max_tokens: Maximum response length
        temperature: Creativity (0.0-1.0)
        timeout: Request timeout in seconds
    
    Returns:
        LLM response text
    """
    if not settings.GEMINI_API_KEY:
        logger.error("❌ Gemini API key not configured")
        raise ValueError("Gemini API key not configured")
    
    # Get model from settings or use default
    model = getattr(settings, "GEMINI_MODEL", None) or DEFAULT_MODEL
    
    # Build contents array for Gemini (different format than OpenAI)
    contents = []
    
    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role")
            content = msg.get("content", "")
            # Skip system messages (we'll use systemInstruction instead)
            if role == "system":
                continue
            if role in ["user", "assistant"] and content:
                contents.append({
                    "role": "user" if role == "user" else "model",
                    "parts": [{"text": content}]
                })
    
    # Add current user input
    contents.append({
        "role": "user",
        "parts": [{"text": user_input}]
    })
    
    try:
        client = _get_shared_client()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"

        payload = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }

        logger.debug(f"🤖 Calling Gemini API - Model: {model}, Messages: {len(contents)}")

        response = await client.post(url, json=payload, timeout=timeout)

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"❌ Gemini API error ({response.status_code}): {error_text}")
            raise ValueError(f"Gemini API error: {error_text}")

        result = response.json()

        if "candidates" in result and len(result["candidates"]) > 0:
            candidate = result["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                llm_response = candidate["content"]["parts"][0].get("text", "").strip()
                if llm_response:
                    logger.debug(f"✅ LLM response received ({len(llm_response)} chars)")
                    return llm_response

        logger.warning(f"⚠️ Unexpected Gemini response structure: {result}")
        raise ValueError("Unexpected response format from Gemini API")

    except httpx.TimeoutException:
        logger.error(f"⏱️ Gemini API timeout after {timeout}s")
        raise ValueError(f"LLM request timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"❌ Error calling Gemini API: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to get LLM response: {str(e)}")


async def generate_initial_greeting(
    greeting_prompt: str,
    timeout: float = 8.0
) -> str:
    """
    Generate initial greeting for a call.
    Raises on failure so the caller can use its own direction-aware fallback.
    """
    # Add extra emphasis to use contact name if mentioned in prompt
    if "contacting" in greeting_prompt.lower() and "property owner" not in greeting_prompt.lower():
        enhanced_prompt = greeting_prompt + "\n\nREMEMBER: You MUST use the contact's actual name in your response. DO NOT say 'property owner'."
    else:
        enhanced_prompt = greeting_prompt

    response = await process_with_llm(
        user_input="Generate the greeting now. Use the contact's name if provided.",
        system_prompt=enhanced_prompt,
        conversation_history=None,
        max_tokens=100,
        temperature=0.7,
        timeout=timeout
    )

    logger.info(f"🤖 LLM greeting response: {response[:100]}...")
    return response


def format_conversation_history_for_llm(history: List[Dict]) -> List[Dict]:
    """
    Format conversation history for LLM API
    Filters and validates history entries
    """
    formatted = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        
        if role in ["system", "user", "assistant"] and content:
            formatted.append({
                "role": role,
                "content": content
            })
    
    return formatted


async def process_with_structured_output(
    user_input: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    max_tokens: int = 300,
    temperature: float = 0.4,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict:
    """
    Single LLM call that returns BOTH a spoken reply and an optional tool payload.
    The LLM is instructed to reply in JSON with keys:
      - assistant_speech: str  (what to say to the user)
      - action: str | null     (e.g. "create_showing", "update_slots", null)
      - slots: dict | null     (extracted / confirmed fields)

    If the model returns plain text (non-JSON), we wrap it as speech-only.
    """
    raw = await process_with_llm(
        user_input=user_input,
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )

    # Try to parse JSON from the response
    cleaned = raw.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Direct parse attempt
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "assistant_speech" in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: extract first JSON object from the raw text
    brace_start = cleaned.find("{")
    if brace_start != -1:
        depth = 0
        for i in range(brace_start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(cleaned[brace_start:i+1])
                        if isinstance(parsed, dict) and "assistant_speech" in parsed:
                            return parsed
                    except (json.JSONDecodeError, TypeError):
                        pass
                    break

    return {"assistant_speech": raw, "action": None, "slots": None}
