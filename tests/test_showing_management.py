"""
Tests for Showing (appointment / visit) management.
Covers creation, validation, overlap detection, status updates, and API endpoints.
"""
import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta, timezone

from app.models.property import Property
from app.models.contact import Contact
from app.services.showing_service import create_showing, get_showings, get_showing_by_id, update_showing


# ─── helpers ───────────────────────────────────────────────────────────

def _future(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ─── service-level tests ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_showing_basic(db_session, authenticated_agent):
    """Creating a showing with minimal fields succeeds."""
    client, agent = authenticated_agent
    result = await create_showing(
        real_estate_agent_id=agent.id,
        scheduled_start=_future(24),
        visit_type="showing",
        source="manual",
        caller_name="John Doe",
    )
    assert result["id"]
    assert result["status"] == "requested"
    assert result["caller_name"] == "John Doe"
    assert result["visit_type"] == "showing"


@pytest.mark.asyncio
async def test_create_showing_past_time_rejected(db_session, authenticated_agent):
    """Scheduling in the past raises ValueError."""
    _, agent = authenticated_agent
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    with pytest.raises(ValueError, match="past"):
        await create_showing(
            real_estate_agent_id=agent.id,
            scheduled_start=past,
        )


@pytest.mark.asyncio
async def test_create_showing_invalid_visit_type(db_session, authenticated_agent):
    _, agent = authenticated_agent
    with pytest.raises(ValueError, match="visit_type"):
        await create_showing(
            real_estate_agent_id=agent.id,
            scheduled_start=_future(),
            visit_type="pool_party",
        )


@pytest.mark.asyncio
async def test_create_showing_with_property(db_session, authenticated_agent):
    """Can link a showing to a property that belongs to the same agent."""
    _, agent = authenticated_agent
    prop = Property(
        id=str(uuid.uuid4()),
        real_estate_agent_id=agent.id,
        address="123 Main St",
        owner_phone="+10000000000",
        is_available="true",
    )
    db_session.add(prop)
    await db_session.commit()

    result = await create_showing(
        real_estate_agent_id=agent.id,
        scheduled_start=_future(48),
        property_id=prop.id,
    )
    assert result["property_id"] == prop.id
    assert result["property_address"] == "123 Main St"


@pytest.mark.asyncio
async def test_create_showing_wrong_property_rejected(db_session, authenticated_agent):
    """Property belonging to a different agent is rejected."""
    _, agent = authenticated_agent
    with pytest.raises(ValueError, match="Property not found"):
        await create_showing(
            real_estate_agent_id=agent.id,
            scheduled_start=_future(),
            property_id=str(uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_overlap_detection(db_session, authenticated_agent):
    """Two showings at the same time for the same property should conflict."""
    _, agent = authenticated_agent
    prop = Property(
        id=str(uuid.uuid4()),
        real_estate_agent_id=agent.id,
        address="456 Elm St",
        owner_phone="+10000000001",
    )
    db_session.add(prop)
    await db_session.commit()

    start = _future(72)
    await create_showing(
        real_estate_agent_id=agent.id,
        scheduled_start=start,
        property_id=prop.id,
    )

    with pytest.raises(ValueError, match="conflict"):
        await create_showing(
            real_estate_agent_id=agent.id,
            scheduled_start=start + timedelta(minutes=30),
            property_id=prop.id,
        )


@pytest.mark.asyncio
async def test_update_showing_status(db_session, authenticated_agent):
    _, agent = authenticated_agent
    created = await create_showing(
        real_estate_agent_id=agent.id,
        scheduled_start=_future(),
    )
    updated = await update_showing(
        showing_id=created["id"],
        real_estate_agent_id=agent.id,
        status="confirmed",
    )
    assert updated["status"] == "confirmed"


@pytest.mark.asyncio
async def test_update_showing_invalid_status(db_session, authenticated_agent):
    _, agent = authenticated_agent
    created = await create_showing(
        real_estate_agent_id=agent.id,
        scheduled_start=_future(),
    )
    with pytest.raises(ValueError, match="status"):
        await update_showing(
            showing_id=created["id"],
            real_estate_agent_id=agent.id,
            status="dancing",
        )


@pytest.mark.asyncio
async def test_list_showings_with_filter(db_session, authenticated_agent):
    _, agent = authenticated_agent
    s1 = await create_showing(real_estate_agent_id=agent.id, scheduled_start=_future(24))
    s2 = await create_showing(real_estate_agent_id=agent.id, scheduled_start=_future(48))

    await update_showing(showing_id=s2["id"], real_estate_agent_id=agent.id, status="confirmed")

    items, total = await get_showings(real_estate_agent_id=agent.id)
    assert total == 2

    items_confirmed, total_confirmed = await get_showings(
        real_estate_agent_id=agent.id, status_filter="confirmed"
    )
    assert total_confirmed == 1
    assert items_confirmed[0]["status"] == "confirmed"


# ─── API endpoint tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_create_and_list_showings(authenticated_agent):
    client, agent = authenticated_agent
    start = _future(24).isoformat()

    resp = await client.post("/agent/showings", json={
        "scheduled_start": start,
        "visit_type": "showing",
        "caller_name": "API Tester",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["caller_name"] == "API Tester"

    resp_list = await client.get("/agent/showings")
    assert resp_list.status_code == 200
    data = resp_list.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_api_update_showing(authenticated_agent):
    client, agent = authenticated_agent
    resp = await client.post("/agent/showings", json={
        "scheduled_start": _future().isoformat(),
        "caller_name": "Updater",
    })
    showing_id = resp.json()["id"]

    resp_patch = await client.patch(f"/agent/showings/{showing_id}", json={
        "status": "confirmed",
    })
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_api_get_nonexistent_showing(authenticated_agent):
    client, _ = authenticated_agent
    resp = await client.get(f"/agent/showings/{uuid.uuid4()}")
    assert resp.status_code == 404


# ─── slot parser unit tests ───────────────────────────────────────────

from app.services.conversation.slot_parser import (
    detect_scheduling_intent,
    extract_slots_from_text,
    resolve_datetime,
)


def test_detect_scheduling_intent():
    assert detect_scheduling_intent("I want to schedule a visit")
    assert detect_scheduling_intent("Can I book a showing?")
    assert not detect_scheduling_intent("What is the price of this house?")


def test_extract_time_from_text():
    slots = extract_slots_from_text("tomorrow at 3 pm")
    assert slots.get("time_hint") == "3 pm"
    assert slots.get("date_hint")  # should resolve to tomorrow


def test_resolve_datetime_basic():
    today = datetime.now(timezone.utc).date()
    tomorrow = (today + timedelta(days=1)).isoformat()
    result = resolve_datetime(tomorrow, "2:30 pm")
    assert result is not None
    assert result.hour == 14
    assert result.minute == 30


def test_resolve_datetime_no_date():
    assert resolve_datetime(None, "3 pm") is None


def test_property_match_ordinal():
    props = [{"address": "123 Main St"}, {"address": "456 Elm St"}]
    slots = extract_slots_from_text("the second one", props)
    assert slots.get("property_index") == 1
