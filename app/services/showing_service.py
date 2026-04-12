"""
Showing Service — CRUD, overlap detection, validation.
Follows the same session/query patterns as call_service.
"""
import uuid
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, func, desc, or_
from sqlalchemy.orm import selectinload

from app.database.connection import AsyncSessionLocal
from app.models.showing import Showing
from app.models.contact import Contact
from app.models.property import Property
from app.schemas.showing import VALID_STATUSES, VALID_VISIT_TYPES, VALID_SOURCES

logger = logging.getLogger(__name__)

DEFAULT_SHOWING_DURATION_MINUTES = 60


async def create_showing(
    real_estate_agent_id: str,
    scheduled_start: datetime,
    property_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    caller_phone: Optional[str] = None,
    caller_name: Optional[str] = None,
    visit_type: str = "property_visit",
    source: str = "manual",
    notes: Optional[str] = None,
    scheduled_end: Optional[datetime] = None,
    voice_agent_id: Optional[str] = None,
    call_id: Optional[str] = None,
    twilio_call_sid: Optional[str] = None,
) -> Dict:
    """Create a new showing with overlap and past-time validation."""

    if visit_type not in VALID_VISIT_TYPES:
        raise ValueError(f"Invalid visit_type '{visit_type}'. Must be one of: {', '.join(VALID_VISIT_TYPES)}")
    if source not in VALID_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of: {', '.join(VALID_SOURCES)}")

    now = datetime.now(timezone.utc)
    if scheduled_start.tzinfo is None:
        scheduled_start = scheduled_start.replace(tzinfo=timezone.utc)
    if scheduled_start < now - timedelta(minutes=5):
        raise ValueError("Cannot schedule a showing in the past")

    if scheduled_end is None:
        scheduled_end = scheduled_start + timedelta(minutes=DEFAULT_SHOWING_DURATION_MINUTES)
    elif scheduled_end.tzinfo is None:
        scheduled_end = scheduled_end.replace(tzinfo=timezone.utc)

    if scheduled_end <= scheduled_start:
        raise ValueError("scheduled_end must be after scheduled_start")

    async with AsyncSessionLocal() as session:
        if property_id:
            prop_stmt = select(Property).where(
                and_(
                    Property.id == property_id,
                    Property.real_estate_agent_id == real_estate_agent_id,
                )
            )
            prop_result = await session.execute(prop_stmt)
            if not prop_result.scalar_one_or_none():
                raise ValueError("Property not found or does not belong to this agent")

        if contact_id:
            contact_stmt = select(Contact).where(
                and_(
                    Contact.id == contact_id,
                    Contact.real_estate_agent_id == real_estate_agent_id,
                )
            )
            contact_result = await session.execute(contact_stmt)
            if not contact_result.scalar_one_or_none():
                raise ValueError("Contact not found or does not belong to this agent")

        overlap = await _check_overlap(
            session, real_estate_agent_id, property_id, scheduled_start, scheduled_end
        )
        if overlap:
            raise ValueError(
                f"Time conflict: an existing showing overlaps with the requested slot "
                f"({overlap['scheduled_start']} – {overlap['scheduled_end']})"
            )

        showing_id = str(uuid.uuid4())
        showing = Showing(
            id=showing_id,
            real_estate_agent_id=real_estate_agent_id,
            voice_agent_id=voice_agent_id,
            contact_id=contact_id,
            property_id=property_id,
            call_id=call_id,
            caller_phone=caller_phone,
            caller_name=caller_name,
            visit_type=visit_type,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            status="requested",
            source=source,
            twilio_call_sid=twilio_call_sid,
            notes=notes,
        )
        session.add(showing)
        await session.commit()
        logger.info(f"Created showing {showing_id} for agent {real_estate_agent_id}")

        # Re-fetch with eager-loaded relationships to avoid async lazy-load errors
        stmt = (
            select(Showing)
            .options(selectinload(Showing.contact), selectinload(Showing.property))
            .where(Showing.id == showing_id)
        )
        result = await session.execute(stmt)
        showing = result.scalar_one()

        return await _showing_to_dict(session, showing)


async def get_showings(
    real_estate_agent_id: str,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    visit_type_filter: Optional[str] = None,
    property_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> Tuple[List[Dict], int]:
    """List showings with filters and pagination."""

    async with AsyncSessionLocal() as session:
        conditions = [Showing.real_estate_agent_id == real_estate_agent_id]

        if status_filter:
            conditions.append(Showing.status == status_filter)
        if visit_type_filter:
            conditions.append(Showing.visit_type == visit_type_filter)
        if property_id:
            conditions.append(Showing.property_id == property_id)
        if contact_id:
            conditions.append(Showing.contact_id == contact_id)
        if from_date:
            conditions.append(Showing.scheduled_start >= from_date)
        if to_date:
            conditions.append(Showing.scheduled_start <= to_date)

        count_stmt = select(func.count(Showing.id)).where(and_(*conditions))
        total = (await session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Showing)
            .options(
                selectinload(Showing.contact),
                selectinload(Showing.property),
            )
            .where(and_(*conditions))
            .order_by(desc(Showing.scheduled_start))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        showings = result.scalars().all()

        items = [await _showing_to_dict(session, s) for s in showings]
        return items, total


async def get_showing_by_id(
    showing_id: str, real_estate_agent_id: str
) -> Optional[Dict]:
    """Fetch a single showing by id, scoped to the agent."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Showing)
            .options(selectinload(Showing.contact), selectinload(Showing.property))
            .where(
                and_(
                    Showing.id == showing_id,
                    Showing.real_estate_agent_id == real_estate_agent_id,
                )
            )
        )
        result = await session.execute(stmt)
        showing = result.scalar_one_or_none()
        if not showing:
            return None
        return await _showing_to_dict(session, showing)


async def update_showing(
    showing_id: str,
    real_estate_agent_id: str,
    **kwargs,
) -> Optional[Dict]:
    """Partially update a showing."""
    async with AsyncSessionLocal() as session:
        stmt = select(Showing).where(
            and_(
                Showing.id == showing_id,
                Showing.real_estate_agent_id == real_estate_agent_id,
            )
        )
        result = await session.execute(stmt)
        showing = result.scalar_one_or_none()
        if not showing:
            return None

        new_status = kwargs.get("status")
        if new_status and new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_STATUSES)}")

        new_visit_type = kwargs.get("visit_type")
        if new_visit_type and new_visit_type not in VALID_VISIT_TYPES:
            raise ValueError(f"Invalid visit_type '{new_visit_type}'. Must be one of: {', '.join(VALID_VISIT_TYPES)}")

        new_start = kwargs.get("scheduled_start")
        new_end = kwargs.get("scheduled_end")
        if new_start or new_end:
            start = new_start or showing.scheduled_start
            end = new_end or showing.scheduled_end or (start + timedelta(minutes=DEFAULT_SHOWING_DURATION_MINUTES))
            overlap = await _check_overlap(
                session, real_estate_agent_id, showing.property_id, start, end, exclude_id=showing_id
            )
            if overlap:
                raise ValueError("Time conflict with an existing showing")

        updatable = {
            "contact_id", "property_id", "caller_name", "visit_type",
            "scheduled_start", "scheduled_end", "status", "notes",
        }
        for key, value in kwargs.items():
            if key in updatable and value is not None:
                setattr(showing, key, value)

        await session.commit()
        logger.info(f"Updated showing {showing_id}")

        # Re-fetch with eager-loaded relationships
        reload_stmt = (
            select(Showing)
            .options(selectinload(Showing.contact), selectinload(Showing.property))
            .where(Showing.id == showing_id)
        )
        reload_result = await session.execute(reload_stmt)
        showing = reload_result.scalar_one()

        return await _showing_to_dict(session, showing)


# --------------- helpers ---------------

async def _check_overlap(
    session,
    real_estate_agent_id: str,
    property_id: Optional[str],
    start: datetime,
    end: datetime,
    exclude_id: Optional[str] = None,
) -> Optional[Dict]:
    """Return the first conflicting showing (same agent + optionally same property) or None."""
    conditions = [
        Showing.real_estate_agent_id == real_estate_agent_id,
        Showing.status.in_(["requested", "confirmed"]),
        Showing.scheduled_start < end,
        or_(
            Showing.scheduled_end > start,
            Showing.scheduled_end.is_(None),
        ),
    ]
    if property_id:
        conditions.append(Showing.property_id == property_id)
    if exclude_id:
        conditions.append(Showing.id != exclude_id)

    stmt = select(Showing).where(and_(*conditions)).limit(1)
    result = await session.execute(stmt)
    conflict = result.scalar_one_or_none()
    if not conflict:
        return None
    return {
        "id": conflict.id,
        "scheduled_start": conflict.scheduled_start.isoformat() if conflict.scheduled_start else None,
        "scheduled_end": conflict.scheduled_end.isoformat() if conflict.scheduled_end else None,
    }


async def _showing_to_dict(session, showing: Showing) -> Dict:
    """Serialize a Showing ORM object into a plain dict with full property/contact data."""
    contact = showing.contact
    prop = showing.property
    return {
        "id": showing.id,
        "real_estate_agent_id": showing.real_estate_agent_id,
        "voice_agent_id": showing.voice_agent_id,
        "contact_id": showing.contact_id,
        "contact_name": contact.name if contact else showing.caller_name,
        "contact_phone": contact.phone_number if contact else showing.caller_phone,
        "contact_email": contact.email if contact else None,
        "property_id": showing.property_id,
        "property_address": prop.address if prop else None,
        "property_city": prop.city if prop else None,
        "property_state": prop.state if prop else None,
        "property_type": prop.property_type if prop else None,
        "property_price": float(prop.price) if prop and prop.price else None,
        "property_bedrooms": prop.bedrooms if prop else None,
        "property_bathrooms": prop.bathrooms if prop else None,
        "property_sqft": prop.square_feet if prop else None,
        "call_id": showing.call_id,
        "caller_phone": showing.caller_phone,
        "caller_name": showing.caller_name,
        "visit_type": showing.visit_type,
        "scheduled_start": showing.scheduled_start.isoformat() if showing.scheduled_start else None,
        "scheduled_end": showing.scheduled_end.isoformat() if showing.scheduled_end else None,
        "status": showing.status,
        "source": showing.source,
        "twilio_call_sid": showing.twilio_call_sid,
        "notes": showing.notes,
        "created_at": showing.created_at.isoformat() if showing.created_at else None,
        "updated_at": showing.updated_at.isoformat() if showing.updated_at else None,
    }
