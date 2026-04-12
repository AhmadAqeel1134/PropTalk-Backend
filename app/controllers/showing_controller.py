"""
Showing Controller — REST API for showings / appointments.
Scoped to the authenticated real estate agent.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from datetime import datetime

from app.utils.dependencies import get_current_real_estate_agent_id
from app.schemas.showing import (
    ShowingCreateRequest,
    ShowingUpdateRequest,
    ShowingResponse,
    PaginatedShowingsResponse,
)
from app.services import showing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/showings", tags=["Showings"])


@router.get("", response_model=PaginatedShowingsResponse)
async def list_showings(
    agent_id: str = Depends(get_current_real_estate_agent_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    visit_type: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    contact_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
):
    """List showings for the current agent with optional filters."""
    try:
        items, total = await showing_service.get_showings(
            real_estate_agent_id=agent_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            visit_type_filter=visit_type,
            property_id=property_id,
            contact_id=contact_id,
            from_date=from_date,
            to_date=to_date,
        )
        return PaginatedShowingsResponse(
            items=[ShowingResponse(**s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error(f"Error listing showings: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{showing_id}", response_model=ShowingResponse)
async def get_showing(
    showing_id: str,
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    """Get a single showing by id."""
    result = await showing_service.get_showing_by_id(showing_id, agent_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Showing not found")
    return ShowingResponse(**result)


@router.post("", response_model=ShowingResponse, status_code=status.HTTP_201_CREATED)
async def create_showing(
    body: ShowingCreateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    """Create a new showing / appointment."""
    try:
        result = await showing_service.create_showing(
            real_estate_agent_id=agent_id,
            scheduled_start=body.scheduled_start,
            property_id=body.property_id,
            contact_id=body.contact_id,
            caller_phone=body.caller_phone,
            caller_name=body.caller_name,
            visit_type=body.visit_type,
            source=body.source,
            notes=body.notes,
            scheduled_end=body.scheduled_end,
        )
        return ShowingResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating showing: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create showing")


@router.patch("/{showing_id}", response_model=ShowingResponse)
async def update_showing(
    showing_id: str,
    body: ShowingUpdateRequest,
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    """Update an existing showing (partial)."""
    try:
        payload = body.model_dump(exclude_unset=True)
        result = await showing_service.update_showing(
            showing_id=showing_id,
            real_estate_agent_id=agent_id,
            **payload,
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Showing not found")
        return ShowingResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating showing: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update showing")
