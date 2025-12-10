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
    # assign_phone_number_to_agent,  # DISABLED - Auto-purchase removed, admin must manually purchase
    assign_existing_phone_number_to_agent,
    get_phone_number_by_agent_id,
    update_phone_number,
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
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🟢 [APPROVE_SERVICE] Starting approval process")
    logger.info(f"🟢 [APPROVE_SERVICE] request_id={request_id}, admin_id={admin_id}, phone_number={phone_number}")
    
    async with AsyncSessionLocal() as session:
        # Get request
        logger.info(f"🟢 [APPROVE_SERVICE] Step 1: Fetching voice agent request...")
        stmt = select(VoiceAgentRequest).where(VoiceAgentRequest.id == request_id)
        result = await session.execute(stmt)
        request = result.scalar_one_or_none()
        
        if not request:
            logger.error(f"❌ [APPROVE_SERVICE] Voice agent request not found: {request_id}")
            raise ValueError("Voice agent request not found")
        
        logger.info(f"🟢 [APPROVE_SERVICE] Found request: status={request.status}, agent_id={request.real_estate_agent_id}")
        
        if request.status != "pending":
            logger.error(f"❌ [APPROVE_SERVICE] Request is not pending: {request.status}")
            raise ValueError(f"Request is already {request.status}")
        
        # Get agent details for default prompt
        logger.info(f"🟢 [APPROVE_SERVICE] Step 2: Fetching real estate agent...")
        agent_stmt = select(RealEstateAgent).where(RealEstateAgent.id == request.real_estate_agent_id)
        agent_result = await session.execute(agent_stmt)
        agent = agent_result.scalar_one_or_none()
        
        if not agent:
            logger.error(f"❌ [APPROVE_SERVICE] Real estate agent not found: {request.real_estate_agent_id}")
            raise ValueError("Real estate agent not found")
        
        logger.info(f"🟢 [APPROVE_SERVICE] Found agent: {agent.full_name} ({agent.email})")
        
        # Check if agent already has a voice agent
        logger.info(f"🟢 [APPROVE_SERVICE] Step 3: Checking for existing voice agent...")
        existing_voice_agent = await session.execute(
            select(VoiceAgent).where(VoiceAgent.real_estate_agent_id == request.real_estate_agent_id)
        )
        if existing_voice_agent.scalar_one_or_none():
            logger.error(f"❌ [APPROVE_SERVICE] Agent already has a voice agent")
            raise ValueError("Agent already has a voice agent")
        
        logger.info(f"🟢 [APPROVE_SERVICE] No existing voice agent found - proceeding")
        
        # Assign phone number
        logger.info(f"🟢 [APPROVE_SERVICE] Step 4: Assigning phone number...")
        logger.info(f"🟢 [APPROVE_SERVICE] phone_number provided: {phone_number is not None}, value: '{phone_number}'")
        
        # Check if agent already has an active phone number
        existing_phone_data = await get_phone_number_by_agent_id(request.real_estate_agent_id)
        
        if existing_phone_data:
            logger.info(f"🟢 [APPROVE_SERVICE] Agent already has phone number: {existing_phone_data['twilio_phone_number']}")
            
            # If admin provided a new phone number, use that instead of the existing one
            if phone_number:
                # Normalize the provided number for comparison
                normalized_provided = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").strip()
                if not normalized_provided.startswith("+") and normalized_provided.isdigit():
                    normalized_provided = "+" + normalized_provided
                
                existing_normalized = existing_phone_data['twilio_phone_number'].replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "").strip()
                
                if normalized_provided == existing_normalized:
                    logger.info(f"🟢 [APPROVE_SERVICE] Provided number matches existing number. Reusing existing phone number (id: {existing_phone_data['id']})")
                    phone_data = existing_phone_data
                else:
                    logger.info(f"🟢 [APPROVE_SERVICE] Admin provided different number ({phone_number}). Assigning new number...")
                    # Assign the new phone number (this will fail if agent already has one, so we need to handle that)
                    try:
                        phone_data = await assign_existing_phone_number_to_agent(
                            request.real_estate_agent_id, phone_number
                        )
                        logger.info(f"✅ [APPROVE_SERVICE] New phone number assigned successfully: {phone_data}")
                    except ValueError as e:
                        if "Agent already has an active phone number" in str(e):
                            # Deactivate old number and assign new one
                            logger.info(f"🟢 [APPROVE_SERVICE] Deactivating old phone number and assigning new one...")
                            await update_phone_number(existing_phone_data['id'], {"is_active": False})
                            phone_data = await assign_existing_phone_number_to_agent(
                                request.real_estate_agent_id, phone_number
                            )
                            logger.info(f"✅ [APPROVE_SERVICE] New phone number assigned after deactivating old one: {phone_data}")
                        else:
                            raise
            else:
                # No phone number provided, reuse existing
                logger.info(f"🟢 [APPROVE_SERVICE] No phone number provided. Reusing existing phone number (id: {existing_phone_data['id']})")
                phone_data = existing_phone_data
        else:
            logger.info(f"🟢 [APPROVE_SERVICE] No existing phone number found. Assigning new one...")
            try:
                if phone_number:
                    logger.info(f"🟢 [APPROVE_SERVICE] Using provided phone number: {phone_number}")
                    # Use an existing Twilio number (already purchased in console)
                    phone_data = await assign_existing_phone_number_to_agent(
                        request.real_estate_agent_id, phone_number
                    )
                    logger.info(f"✅ [APPROVE_SERVICE] Phone number assigned successfully: {phone_data}")
                else:
                    # AUTO-PURCHASE DISABLED - Admin must manually purchase and enter phone number
                    logger.error(f"❌ [APPROVE_SERVICE] No phone number provided. Admin must purchase number in Twilio Console and enter it.")
                    raise ValueError("Phone number is required. Please purchase a number in Twilio Console and enter it in the approval form.")
                    # COMMENTED OUT: Auto-purchase functionality
                    # logger.info(f"🟢 [APPROVE_SERVICE] Auto-purchasing new phone number...")
                    # phone_data = await assign_phone_number_to_agent(request.real_estate_agent_id)
                    # logger.info(f"✅ [APPROVE_SERVICE] New phone number purchased: {phone_data}")
            except Exception as e:
                logger.error(f"❌ [APPROVE_SERVICE] Failed to assign phone number: {type(e).__name__}: {str(e)}", exc_info=True)
                raise ValueError(f"Failed to assign phone number: {str(e)}")
        
        # Create voice agent
        logger.info(f"🟢 [APPROVE_SERVICE] Step 5: Creating voice agent...")
        voice_agent_id = str(uuid.uuid4())
        default_prompt = get_default_system_prompt(agent.full_name, agent.company_name or "Independent Agent")
        
        logger.info(f"🟢 [APPROVE_SERVICE] Creating voice agent with phone_number_id: {phone_data['id']}")
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
                "greeting_message": "Hi Wajaht, I am from proptalk",
                "custom_commands": [],
                "recording_enabled": True
            }
        )
        
        session.add(new_voice_agent)
        
        # Update request
        logger.info(f"🟢 [APPROVE_SERVICE] Step 6: Updating request status...")
        request.status = "approved"
        request.reviewed_at = datetime.utcnow()
        request.reviewed_by = admin_id
        
        logger.info(f"🟢 [APPROVE_SERVICE] Step 7: Committing to database...")
        await session.commit()
        await session.refresh(new_voice_agent)
        
        logger.info(f"✅ [APPROVE_SERVICE] Approval completed successfully!")
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
    from app.services.real_estate_agent_service import get_agent_summary_stats
    from app.models.voice_agent import VoiceAgent
    from sqlalchemy import func
    from app.models.property import Property
    from app.models.document import Document
    from app.models.contact import Contact
    
    async with AsyncSessionLocal() as session:
        stmt = select(VoiceAgentRequest).options(selectinload(VoiceAgentRequest.real_estate_agent))
        if status:
            stmt = stmt.where(VoiceAgentRequest.status == status)
        stmt = stmt.order_by(VoiceAgentRequest.created_at.desc())
        
        result = await session.execute(stmt)
        requests = result.scalars().all()
        
        # Get voice agent phone numbers for approved requests
        request_ids = [req.id for req in requests]
        # Collect all unique agent IDs - ensure we get all of them
        agent_ids = list(set([req.real_estate_agent_id for req in requests if req.real_estate_agent_id]))
        
        # Batch fetch voice agents to get phone numbers
        voice_agents = {}
        if agent_ids:
            voice_agents_stmt = select(VoiceAgent).options(selectinload(VoiceAgent.phone_number)).where(VoiceAgent.real_estate_agent_id.in_(agent_ids))
            voice_agents_result = await session.execute(voice_agents_stmt)
            voice_agents = {va.real_estate_agent_id: va for va in voice_agents_result.scalars().all()}
        
        # Batch fetch agent stats - always initialize even if empty
        # Use EXACT same query logic as get_all_real_estate_agents
        properties_counts = {}
        documents_counts = {}
        contacts_counts = {}
        agents_with_phones = set()
        
        if agent_ids:
            # Properties counts - EXACT same as get_all_real_estate_agents
            properties_counts_stmt = select(
                Property.real_estate_agent_id,
                func.count(Property.id).label('count')
            ).where(
                Property.real_estate_agent_id.in_(agent_ids)
            ).group_by(Property.real_estate_agent_id)
            properties_result = await session.execute(properties_counts_stmt)
            properties_counts = {row[0]: row[1] for row in properties_result.all()}
            
            # Documents counts - EXACT same as get_all_real_estate_agents
            documents_counts_stmt = select(
                Document.real_estate_agent_id,
                func.count(Document.id).label('count')
            ).where(
                Document.real_estate_agent_id.in_(agent_ids)
            ).group_by(Document.real_estate_agent_id)
            documents_result = await session.execute(documents_counts_stmt)
            documents_counts = {row[0]: row[1] for row in documents_result.all()}
            
            # Contacts counts - EXACT same as get_all_real_estate_agents
            contacts_counts_stmt = select(
                Contact.real_estate_agent_id,
                func.count(Contact.id).label('count')
            ).where(
                Contact.real_estate_agent_id.in_(agent_ids)
            ).group_by(Contact.real_estate_agent_id)
            contacts_result = await session.execute(contacts_counts_stmt)
            contacts_counts = {row[0]: row[1] for row in contacts_result.all()}
            
            # Phone numbers - EXACT same as get_all_real_estate_agents
            from app.models.phone_number import PhoneNumber
            phone_numbers_stmt = select(PhoneNumber.real_estate_agent_id).where(
                PhoneNumber.real_estate_agent_id.in_(agent_ids),
                PhoneNumber.is_active == True
            )
            phone_result = await session.execute(phone_numbers_stmt)
            agents_with_phones = {row[0] for row in phone_result.all()}
        
        requests_list = []
        for req in requests:
            agent_id = req.real_estate_agent_id
            # Ensure we're using the same ID format as the queries
            # Get stats using the agent_id - same logic as get_all_real_estate_agents
            requests_list.append({
                "id": req.id,
                "real_estate_agent_id": agent_id,
                "status": req.status,
                "requested_at": req.requested_at.isoformat() if req.requested_at else "",
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "reviewed_by": req.reviewed_by,
                "rejection_reason": req.rejection_reason,
                "created_at": req.created_at.isoformat() if req.created_at else "",
                "updated_at": req.updated_at.isoformat() if req.updated_at else "",
                "agent_name": req.real_estate_agent.full_name if req.real_estate_agent else None,
                "agent_email": req.real_estate_agent.email if req.real_estate_agent else None,
                "agent_company_name": req.real_estate_agent.company_name if req.real_estate_agent else None,
                "voice_agent_id": voice_agents.get(agent_id).id if agent_id in voice_agents else None,
                "voice_agent_phone_number": voice_agents.get(agent_id).phone_number.twilio_phone_number if agent_id in voice_agents and voice_agents.get(agent_id).phone_number else None,
                "agent_stats": {
                    # Use .get() with default 0 - same as get_all_real_estate_agents
                    "properties_count": properties_counts.get(agent_id, 0),
                    "documents_count": documents_counts.get(agent_id, 0),
                    "contacts_count": contacts_counts.get(agent_id, 0),
                    "has_phone_number": agent_id in agents_with_phones,
                },
            })
        
        return requests_list


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

