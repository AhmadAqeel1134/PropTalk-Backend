"""
Contact Upsert Service — auto-register unknown callers so future calls are personalized.
Called in the background; never blocks the voice response.
"""
import uuid
import logging
from typing import Optional, Dict

from sqlalchemy import select, and_, or_
from app.database.connection import AsyncSessionLocal
from app.models.contact import Contact

logger = logging.getLogger(__name__)


async def upsert_caller_contact(
    real_estate_agent_id: str,
    caller_phone: str,
    caller_name: Optional[str] = None,
    caller_email: Optional[str] = None,
) -> Optional[Dict]:
    """
    Find or create a contact for `caller_phone` under the given agent.
    If the contact already exists, update the name/email only if they were previously empty.
    Returns a dict with id/name/phone/email, or None on error.
    """
    try:
        async with AsyncSessionLocal() as session:
            normalized = _normalize_phone(caller_phone)

            stmt = select(Contact).where(
                and_(
                    Contact.real_estate_agent_id == real_estate_agent_id,
                    or_(
                        Contact.phone_number == caller_phone,
                        Contact.phone_number == normalized,
                        Contact.phone_number.like(f"%{normalized[-10:]}%"),
                    ),
                )
            )
            result = await session.execute(stmt)
            contact = result.scalar_one_or_none()

            if contact:
                changed = False
                if caller_name and (not contact.name or contact.name.strip().lower() in ("unknown", "")):
                    contact.name = caller_name
                    changed = True
                if caller_email and not contact.email:
                    contact.email = caller_email
                    changed = True
                if changed:
                    await session.commit()
                    await session.refresh(contact)
                    logger.info(f"✏️ Updated contact {contact.id} with new info")
            else:
                contact = Contact(
                    id=str(uuid.uuid4()),
                    real_estate_agent_id=real_estate_agent_id,
                    name=caller_name or "Unknown Caller",
                    phone_number=normalized,
                    email=caller_email,
                    notes="Auto-created from voice call",
                )
                session.add(contact)
                await session.commit()
                await session.refresh(contact)
                logger.info(f"✅ Auto-created contact {contact.id} for {normalized}")

            return {
                "id": contact.id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email,
            }
    except Exception as e:
        logger.error(f"❌ Contact upsert failed for {caller_phone}: {e}", exc_info=True)
        return None


def _normalize_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if not cleaned.startswith("+"):
        if cleaned.startswith("92"):
            cleaned = "+" + cleaned
        elif cleaned.startswith("0"):
            cleaned = "+92" + cleaned[1:]
        else:
            cleaned = "+" + cleaned
    return cleaned
