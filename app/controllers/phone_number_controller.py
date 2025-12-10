from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from app.schemas.phone_number import PhoneNumberResponse, PhoneNumberUpdateRequest
from app.services.phone_number_service import (
    # assign_phone_number_to_agent,  # DISABLED - Auto-purchase removed
    get_phone_number_by_agent_id,
    get_phone_number_by_id,
    update_phone_number,
    get_all_phone_numbers
)
from app.utils.dependencies import get_current_real_estate_agent_id, get_current_admin_id

router = APIRouter(prefix="/phone-numbers", tags=["Phone Numbers"])


# AUTO-PURCHASE DISABLED - Admin must manually purchase numbers in Twilio Console
# @router.post("/assign/{real_estate_agent_id}", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
# async def assign_phone_number_endpoint(
#     real_estate_agent_id: str,
#     area_code: Optional[str] = None,
#     admin_id: str = Depends(get_current_admin_id)
# ):
#     """Assign a phone number to a real estate agent (Admin only)"""
#     try:
#         phone = await assign_phone_number_to_agent(real_estate_agent_id, area_code)
#         return PhoneNumberResponse(**phone)
#     except ValueError as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(e)
#         )


@router.get("/my-phone-number", response_model=PhoneNumberResponse)
async def get_my_phone_number(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """Get current agent's phone number"""
    phone = await get_phone_number_by_agent_id(agent_id)
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No phone number assigned"
        )
    
    return PhoneNumberResponse(**phone)


@router.get("/agent/{real_estate_agent_id}", response_model=PhoneNumberResponse)
async def get_agent_phone_number(
    real_estate_agent_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get phone number for a specific agent (Admin only)"""
    phone = await get_phone_number_by_agent_id(real_estate_agent_id)
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No phone number assigned to this agent"
        )
    
    return PhoneNumberResponse(**phone)


@router.get("/", response_model=List[PhoneNumberResponse])
async def get_all_phone_numbers_endpoint(admin_id: str = Depends(get_current_admin_id)):
    """Get all phone numbers (Admin only)"""
    phones = await get_all_phone_numbers()
    return [PhoneNumberResponse(**phone) for phone in phones]


@router.get("/{phone_id}", response_model=PhoneNumberResponse)
async def get_phone_number_endpoint(
    phone_id: str,
    admin_id: str = Depends(get_current_admin_id)
):
    """Get phone number by ID (Admin only)"""
    phone = await get_phone_number_by_id(phone_id)
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    return PhoneNumberResponse(**phone)


@router.patch("/{phone_id}", response_model=PhoneNumberResponse)
async def update_phone_number_endpoint(
    phone_id: str,
    request: PhoneNumberUpdateRequest,
    admin_id: str = Depends(get_current_admin_id)
):
    """Update phone number (Admin only)"""
    update_data = request.dict(exclude_unset=True)
    
    updated_phone = await update_phone_number(phone_id, update_data)
    
    if not updated_phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found"
        )
    
    return PhoneNumberResponse(**updated_phone)

