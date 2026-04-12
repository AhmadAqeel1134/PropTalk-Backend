"""
Slot Parser — lightweight regex/heuristic extraction for booking slots.
Runs server-side BEFORE the LLM to reduce LLM burden and save latency.
Falls back gracefully; LLM handles disambiguation for ambiguous cases.
"""
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

_SCHEDULING_KEYWORDS = [
    "schedule", "book", "appointment", "visit", "showing",
    "tour", "viewing", "see the property", "come see",
    "want to visit", "set up a visit", "arrange a visit",
    "open house", "inspection", "consultation",
    "meet physically", "meet in person", "in-person",
    "come over", "come by", "drop by", "stop by",
    "want to meet", "set up a meeting", "arrange a meeting",
    "see the place", "visit the place", "look at it",
    "can we meet", "let's meet",
]

_VISIT_TYPE_MAP = {
    "showing": "property_visit",
    "tour": "property_visit",
    "viewing": "property_visit",
    "visit the property": "property_visit",
    "visit the place": "property_visit",
    "see the property": "property_visit",
    "see the place": "property_visit",
    "come over": "property_visit",
    "come by": "property_visit",
    "visit": "property_visit",
    "consultation": "consultation",
    "consult": "consultation",
    "inspection": "inspection",
    "inspect": "inspection",
    "open house": "open_house",
    "meet at your office": "office_visit",
    "come to your office": "office_visit",
    "visit your office": "office_visit",
    "office": "office_visit",
    "meet at my place": "custom_meeting",
    "come to my place": "custom_meeting",
    "come to me": "custom_meeting",
}

_DAY_KEYWORDS = {
    "today": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
}

_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def detect_scheduling_intent(text: str) -> bool:
    """Fast keyword check — does the user want to schedule something?"""
    lower = text.lower()
    return any(kw in lower for kw in _SCHEDULING_KEYWORDS)


def extract_slots_from_text(text: str, properties: Optional[List[Dict]] = None) -> Dict:
    """
    Best-effort extraction. Returns only keys that were found.
    Keys: visit_type, date_hint, time_hint, property_index, caller_name
    """
    lower = text.lower()
    slots: Dict = {}

    for keyword, vtype in _VISIT_TYPE_MAP.items():
        if keyword in lower:
            slots["visit_type"] = vtype
            break

    date_hint = _extract_date_hint(lower)
    if date_hint:
        slots["date_hint"] = date_hint

    time_hint = _extract_time_hint(lower)
    if time_hint:
        slots["time_hint"] = time_hint

    if properties:
        prop_idx = _match_property(lower, properties)
        if prop_idx is not None:
            slots["property_index"] = prop_idx

    return slots


PKT = timezone(timedelta(hours=5))


def resolve_datetime(date_hint: Optional[str], time_hint: Optional[str]) -> Optional[datetime]:
    """
    Combine date_hint and time_hint into a timezone-aware datetime.
    Interprets the user's local time as PKT (UTC+5) and stores it as-is
    so display/notification layers show the correct local time.
    """
    if not date_hint:
        return None

    try:
        base_date = datetime.strptime(date_hint, "%Y-%m-%d").date()
    except ValueError:
        return None

    hour, minute = 10, 0  # default morning
    if time_hint:
        match = re.match(r"(\d{1,2}):?(\d{2})?\s*(am|pm)?", time_hint, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = (match.group(3) or "").lower()
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

    return datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=PKT)


def get_current_week_dates() -> str:
    """
    Return a human-readable string of today + the next 7 days so the LLM
    can resolve day-of-week names ("Monday") to exact calendar dates.
    """
    today = datetime.now(PKT).date()
    lines = [f"Today is {today.strftime('%A, %B %d, %Y')}."]
    upcoming = []
    for delta in range(1, 8):
        d = today + timedelta(days=delta)
        upcoming.append(d.strftime("%a %b %d"))
    lines.append("Upcoming: " + ", ".join(upcoming) + ".")
    return " ".join(lines)


# --------------- internal helpers ---------------

def _extract_date_hint(text: str) -> Optional[str]:
    """Return an ISO date string or None."""
    today = datetime.now(timezone.utc).date()

    for keyword, delta in _DAY_KEYWORDS.items():
        if keyword in text:
            return (today + timedelta(days=delta)).isoformat()

    for name, wd in _WEEKDAY_MAP.items():
        if name in text:
            current_wd = today.weekday()
            delta = (wd - current_wd) % 7
            if delta == 0:
                delta = 7
            return (today + timedelta(days=delta)).isoformat()

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if iso_match:
        return iso_match.group(0)

    # "April 15" / "April 15th" / "15th April"
    for month_name, month_num in _MONTH_MAP.items():
        m = re.search(rf"{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?", text)
        if m:
            day = int(m.group(1))
            year = today.year
            try:
                candidate = datetime(year, month_num, day).date()
                if candidate < today:
                    candidate = datetime(year + 1, month_num, day).date()
                return candidate.isoformat()
            except ValueError:
                pass
        m2 = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{month_name}", text)
        if m2:
            day = int(m2.group(1))
            year = today.year
            try:
                candidate = datetime(year, month_num, day).date()
                if candidate < today:
                    candidate = datetime(year + 1, month_num, day).date()
                return candidate.isoformat()
            except ValueError:
                pass

    slash_match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", text)
    if slash_match:
        month = int(slash_match.group(1))
        day = int(slash_match.group(2))
        year = int(slash_match.group(3)) if slash_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            pass

    return None


def _extract_time_hint(text: str) -> Optional[str]:
    """Return a string like '14:00' or '2:30 pm' or None."""
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", text, re.IGNORECASE)
    if match:
        return match.group(0).strip()

    match24 = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if match24:
        h = int(match24.group(1))
        if 0 <= h <= 23:
            return match24.group(0)

    for keyword, hour in [("morning", "10:00"), ("afternoon", "14:00"), ("evening", "17:00"), ("noon", "12:00")]:
        if keyword in text:
            return hour

    return None


def _match_property(text: str, properties: List[Dict]) -> Optional[int]:
    """Return 0-based index into the properties list, or None."""
    ordinals = {
        "first": 0, "1st": 0, "second": 1, "2nd": 1,
        "third": 2, "3rd": 2, "fourth": 3, "4th": 3, "fifth": 4, "5th": 4,
    }
    for word, idx in ordinals.items():
        if word in text and idx < len(properties):
            return idx

    num_match = re.search(r"(?:property|number|#)\s*(\d+)", text)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(properties):
            return idx

    for i, prop in enumerate(properties):
        addr = (prop.get("address") or "").lower()
        if addr and len(addr) > 5 and addr in text:
            return i

    return None


def extract_caller_name(text: str) -> Optional[str]:
    """
    Lightweight name detection from phrases like "my name is Ahmad",
    "I'm Sarah", "this is Ali", "it's Fatima", "call me John".
    Returns the capitalised name or None.
    """
    patterns = [
        r"(?:my name is|i'm|i am|this is|it'?s|call me|they call me)\s+([A-Za-z]{2,})",
    ]
    lower = text.lower()
    for pat in patterns:
        m = re.search(pat, lower, re.IGNORECASE)
        if m:
            name = m.group(1).strip().title()
            if name.lower() not in ("the", "your", "this", "that", "here", "there", "not"):
                return name
    return None


def extract_caller_email(text: str) -> Optional[str]:
    """
    Lightweight email extraction from spoken text.
    People say things like "my email is ahmad@gmail.com" or spell it out
    "ahmad at gmail dot com".  We handle both forms.
    """
    # Standard email pattern
    m = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)
    if m:
        return m.group(0).lower()

    # Spoken form: "ahmad at gmail dot com"
    spoken = re.search(
        r"([A-Za-z0-9._%+\-]+)\s+at\s+([A-Za-z0-9.\-]+)\s+dot\s+([A-Za-z]{2,})",
        text,
        re.IGNORECASE,
    )
    if spoken:
        return f"{spoken.group(1)}@{spoken.group(2)}.{spoken.group(3)}".lower()

    return None
