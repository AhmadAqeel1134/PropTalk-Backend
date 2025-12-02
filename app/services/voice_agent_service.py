"""
Voice Agent Service - Business logic for voice agent management
Handles requests, approvals, and configuration
"""
from typing import Optional, Dict, List
from datetime import datetime
import uuid
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from app.database.connection import AsyncSessionLocal
from app.models.voice_agent_request import VoiceAgentRequest
from app.models.voice_agent import VoiceAgent
from app.models.real_estate_agent import RealEstateAgent
from app.models.phone_number import PhoneNumber
from app.services.phone_number_service import (
    assign_phone_number_to_agent,
    assign_existing_phone_number_to_agent,
)


# Default system prompts
DEFAULT_SYSTEM_PROMPT_TEMPLATE = """You are a professional real estate assistant for {agent_name} at {company_name}. 
You help potential clients with property inquiries, schedule viewings, and provide 
information about available properties. Be friendly, professional, and helpful. 
Always confirm important details like property addresses and viewing times. 
Keep responses concise and informative."""


async def request_voice_agent(real_estate_agent_id: str) -> Dict:
    """Agent requests a voice agent - creates a pending request"""
    async with AsyncSessionLocal() as session:
        # Check if agent already has a pending request
        existing_pending = await session.execute(
            select(VoiceAgentRequest).where(
                and_(
                    VoiceAgentRequest.real_estate_agent_id == real_estate_agent_id,
                    VoiceAgentRequest.status == "pending"
                )
            )
        )
        if existing_pending.scalar_one_or_none():
            raise ValueError("You already have a pending voice agent request")
        
        # Check if agent already has an approved voice agent
        existing_voice_agent = await session.execute(
            select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == real_estate_agent_id)
        )
        if existing_voice_agent.scalar_one_or_none():
            raise ValueError("You already have a voice agent. Please configure it instead.")
        
        # Create request
        request_id = str(uuid.uuid4())
        new_request = VoiceAgentRequest(
            id=request_id,
            real_estate_agent_id=real_estate_agent_id,
            status="pending"
        )
        
        session.add(new_request)
        await session.commit()
        await session.refresh(new_request)
        
        return {
            "id": new_request.id,
            "real_estate_agent_id": new_request.real_estate_agent_id,
            "status": new_request.status,
            "requested_at": new_request.requested_at.isoformat() if new_request.requested_at else "",
            "reviewed_at": None,
            "reviewed_by": None,
            "rejection_reason": None,
            "created_at": new_request.created_at.isoformat() if new_request.created_at else "",
            "updated_at": new_request.updated_at.isoformat() if new_request.updated_at else "",
        }


async def get_voice_agent_request(real_estate_agent_id: str) -> Optional[Dict]:
    """Get the latest voice agent request for an agent"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(VoiceAgentRequest)
            .where(VoiceAgentRequest.real_estate_agent_id == real_estate_agent_id)
            .order_by(VoiceAgentRequest.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            return None
        
        return {
            "id": request.id,
            "real_estate_agent_id": request.real_estate_agent_id,
            "status": request.status,
            "requested_at": request.requested_at.isoformat() if request.requested_at else "",
            "reviewed_at": request.reviewed_at.isoformat() if request.reviewed_at else None,
            "reviewed_by": request.reviewed_by,
            "rejection_reason": request.rejection_reason,
            "created_at": request.created_at.isoformat() if request.created_at else "",
            "updated_at": request.updated_at.isoformat() if request.updated_at else "",
        }


async def approve_voice_agent_request(request_id: str, admin_id: str, phone_number: Optional[str] = None) -> Dict:
    """Admin approves voice agent request - creates voice agent and assigns phone number.

    If phone_number is provided, we attach an existing Twilio number from the admin's
    Twilio account. Otherwise, we auto-purchase a new number.
    """
    async with AsyncSessionLocal() as session:
        # Get request
        stmt = select(VoiceAgentRequest).where(VoiceAgentRequest.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            raise ValueError("Voice agent request not found")
        
        if request.status != "pending":
            raise ValueError(f"Request is already {request.status}")
        
        # Get agent details for default prompt
        agent_stmt = select(RealEstateAgent).where(RealEstateAgent.id == request.real_estate_agent_id)
        agent_result = await session.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()
        
        if not agent:
            raise ValueError("Real estate agent not found")
        
        # Check if agent already has a voice agent
        existing_voice_agent = await session.execute(
            select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == request.real_estate_agent_id)
        )
        if existing_voice_agent.scalar_one_or_none():
            raise ValueError("Agent already has a voice agent")
        
        # Assign phone number
        try:
            if phone_number:
                # Use an existing Twilio number (already purchased in console)
                phone_data = await assign_existing_phone_number_to_agent(
                    request.real_estate_agent_id, phone_number
                )
            else:
                # Auto-purchase a new number from Twilio
                phone_data = await assign_phone_number_to_agent(request.real_estate_agent_id)
        except Exception as e:
            raise ValueError(f"Failed to assign phone number: {str(e)}")
        
        # Create voice agent
        voice_agent_id = str(uuid.uuid4())
        default_prompt = get_default_system_prompt(agent.full_name, agent.company_name or "Independent Agent")
        
        new_voice_agent = VoiceAgent(
            id=voice_agent_id,
            real_estate_agent_id=request.real_estate_agent_id,
            phone_number_id=phone_data["id"],
            name="Property Assistant",  # Default name
            system_prompt=default_prompt,
            use_default_prompt=True,
            status="active",
            settings={
                "voice_gender": "female",
                "voice_speed": "normal",
                "language": "en-US",
                "greeting_message": "Hello! How can I help you today?",
                "custom_commands": [],
                "recording_enabled": True
            }
        )
        
        session.add(new_voice_agent)
        
        # Update request
        request.status = "approved"
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = admin_id
        
        await session.commit()
        await session.refresh(new_voice_agent)
        
        return {
            "voice_agent_id": new_voice_agent.id,
            "phone_number": phone_data["twilio_phone_number"],
            "phone_number_id": phone_data["id"],
        }


async def reject_voice_agent_request(request_id: str, admin_id: str, reason: str) -> Dict:
    """Admin rejects voice agent request"""
    async with AsyncSessionLocal() as session:
        stmt = select(VoiceAgentRequest).where(VoiceAgentRequest.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            raise ValueError("Voice agent request not found")
        
        if request.status != "pending":
            raise ValueError(f"Request is already {request.status}")
        
        request.status = "rejected"
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = admin_id
        request.rejection_reason = reason
        
        await session.commit()
        await session.refresh(request)
        
        return {
            "id": request.id,
            "status": request.status,
            "rejection_reason": request.rejection_reason,
        }


async def get_voice_agent(real_estate_agent_id: str) -> Optional[Dict]:
    """Get voice agent for an agent"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(VoiceAgent)
            .options(selectinload(VoiceAgent.phone_number))
            .where(VoiceAgent.real_estate_agent_id == real_estate_agent_id)
        )
        result = await session.execute(stmt)
        voice_agent = result.scalar_one_or_none()
        
        if not voice_agent:
            return None
        
        phone_number = voice_agent.phone_number.twilio_phone_number if voice_agent.phone_number else None
        
        return {
            "id": voice_agent.id,
            "real_estate_agent_id": voice_agent.real_estate_agent_id,
            "phone_number_id": voice_agent.phone_number_id,
            "phone_number": phone_number,
            "name": voice_agent.name,
            "system_prompt": voice_agent.system_prompt,
            "use_default_prompt": voice_agent.use_default_prompt,
            "status": voice_agent.status,
            "settings": voice_agent.settings or {},
            "created_at": voice_agent.created_at.isoformat() if voice_agent.created_at else "",
            "updated_at": voice_agent.updated_at.isoformat() if voice_agent.updated_at else "",
        }


async def update_voice_agent(real_estate_agent_id: str, update_data: Dict) -> Dict:
    """Update voice agent configuration"""
    async with AsyncSessionLocal() as session:
        stmt = select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == real_estate_agent_id)
        result = await session.execute(stmt)
        voice_agent = result.scalar_one_or_none()
        
        if not voice_agent:
            raise ValueError("Voice agent not found")
        
        # Update fields
        if "name" in update_data and update_data["name"]:
            voice_agent.name = update_data["name"]
        
        if "use_default_prompt" in update_data:
            voice_agent.use_default_prompt = update_data["use_default_prompt"]
            # If switching to default, get agent info for prompt
            if update_data["use_default_prompt"]:
                agent_stmt = select(RealEstateAgent).where(RealEstateAgent.id == real_estate_agent_id)
                agent_result = await session.execute(agent_stmt)
                agent = agent_result.scalar_one_or_none()
                if agent:
                    voice_agent.system_prompt = get_default_system_prompt(
                        agent.full_name, 
                        agent.company_name or "Independent Agent"
                    )
        
        if "system_prompt" in update_data and update_data["system_prompt"]:
            voice_agent.system_prompt = update_data["system_prompt"]
        
        if "settings" in update_data and update_data["settings"]:
            # Merge settings
            current_settings = voice_agent.settings or {}
            current_settings.update(update_data["settings"])
            voice_agent.settings = current_settings
        
        await session.commit()
        await session.refresh(voice_agent)
        
        # Get phone number
        phone_stmt = select(PhoneNumber).where(PhoneNumber.id == voice_agent.phone_number_id)
        phone_result = await session.execute(phone_stmt)
        phone = phone_result.scalar_one_or_none()
        phone_number = phone.twilio_phone_number if phone else None
        
        return {
            "id": voice_agent.id,
            "real_estate_agent_id": voice_agent.real_estate_agent_id,
            "phone_number_id": voice_agent.phone_number_id,
            "phone_number": phone_number,
            "name": voice_agent.name,
            "system_prompt": voice_agent.system_prompt,
            "use_default_prompt": voice_agent.use_default_prompt,
            "status": voice_agent.status,
            "settings": voice_agent.settings or {},
            "created_at": voice_agent.created_at.isoformat() if voice_agent.created_at else "",
            "updated_at": voice_agent.updated_at.isoformat() if voice_agent.updated_at else "",
        }


async def toggle_voice_agent_status(real_estate_agent_id: str, status: str) -> Dict:
    """Toggle voice agent status (active/inactive)"""
    if status not in ["active", "inactive"]:
        raise ValueError("Status must be 'active' or 'inactive'")
    
    async with AsyncSessionLocal() as session:
        stmt = select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == real_estate_agent_id)
        result = await session.execute(stmt)
        voice_agent = result.scalar_one_or_none()
        
        if not voice_agent:
            raise ValueError("Voice agent not found")
        
        voice_agent.status = status
        await session.commit()
        await session.refresh(voice_agent)
        
        return {
            "id": voice_agent.id,
            "status": voice_agent.status,
        }


def get_default_system_prompt(agent_name: str, company_name: str) -> str:
    """Generate default system prompt for voice agent"""
    return DEFAULT_SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        company_name=company_name
    )


async def get_all_voice_agent_requests(status: Optional[str] = None) -> List[Dict]:
    """Get all voice agent requests (admin)"""
    async with AsyncSessionLocal() as session:
        stmt = select(VoiceAgentRequest).options(selectinload(VoiceAgentRequest.real_estate_agent))
        if status:
            stmt = stmt.where(VoiceAgentRequest.status == status)
        stmt = stmt.order_by(VoiceAgentRequest.created_at.desc())
        
        result = await session.execute(stmt)
        requests = result.scalars().all()
        
        return [
            {
                "id": req.id,
                "real_estate_agent_id": req.real_estate_agent_id,
                "status": req.status,
                "requested_at": req.requested_at.isoformat() if req.requested_at else "",
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "reviewed_by": req.reviewed_by,
                "rejection_reason": req.rejection_reason,
                "created_at": req.created_at.isoformat() if req.created_at else "",
                "updated_at": req.updated_at.isoformat() if req.updated_at else "",
                "agent_name": req.real_estate_agent.full_name if req.real_estate_agent else None,
                "agent_email": req.real_estate_agent.email if req.real_estate_agent else None,
            }
            for req in requests
        ]


async def get_all_voice_agents() -> List[Dict]:
    """Get all voice agents (admin)"""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(VoiceAgent)
            .options(selectinload(VoiceAgent.phone_number))
            .order_by(VoiceAgent.created_at.desc())
        )
        result = await session.execute(stmt)
        voice_agents = result.scalars().all()
        
        return [
            {
                "id": va.id,
                "real_estate_agent_id": va.real_estate_agent_id,
                "phone_number_id": va.phone_number_id,
                "phone_number": va.phone_number.twilio_phone_number if va.phone_number else None,
                "name": va.name,
                "system_prompt": va.system_prompt,
                "use_default_prompt": va.use_default_prompt,
                "status": va.status,
                "settings": va.settings or {},
                "created_at": va.created_at.isoformat() if va.created_at else "",
                "updated_at": va.updated_at.isoformat() if va.updated_at else "",
            }
            for va in voice_agents
        ]

