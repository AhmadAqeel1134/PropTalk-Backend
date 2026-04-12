import re
from typing import List, Dict


def parse_transcript_to_messages(transcript: str, direction: str) -> List[Dict]:
    """
    Parse plain text transcript into structured messages (heuristic).
    """
    messages = []
    sentences = re.split(r"[.!?]\s+|\n+", transcript.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    is_agent_turn = direction == "outbound"

    for sentence in sentences:
        if not sentence or len(sentence) < 3:
            continue
        role = "assistant" if is_agent_turn else "user"
        messages.append(
            {
                "role": role,
                "content": sentence,
                "timestamp": None,
            }
        )
        is_agent_turn = not is_agent_turn

    return messages
