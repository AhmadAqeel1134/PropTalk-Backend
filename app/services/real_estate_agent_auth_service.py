from typing import Optional
import uuid
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.utils.security import verify_password, get_password_hash
from app.services.phone_number_service import assign_phone_number_to_agent


async def register_real_estate_agent(
    email: str,
    password: str,
    full_name: str,
    company_name: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None
) -> dict:
    """Register a new real estate agent"""
    async with AsyncSessionLocal() as session:
        # Check if agent already exists
        stmt = select(RealEstateAgent).where(RealEstateAgent.email == email.lower())
        result = await session.execute(stmt)
        existing_agent = result.scalar_one_or_none()
        
        if existing_agent:
            raise ValueError("Real estate agent with this email already exists")
        
        # Create new agent
        agent_id = str(uuid.uuid4())
        hashed_password = get_password_hash(password)
        
        new_agent = RealEstateAgent(
            id=agent_id,
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            company_name=company_name,
            phone=phone,
            address=address,
            is_active=True,
            is_verified=False,
        )
        
        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)
        
        # Automatically assign a phone number to the agent
        try:
            await assign_phone_number_to_agent(agent_id)
        except Exception as e:
            # Log error but don't fail registration if phone assignment fails
            print(f"Warning: Failed to assign phone number during registration: {str(e)}")
        
        return {
            "id": agent_id,
            "email": email.lower(),
            "full_name": full_name,
            "company_name": company_name,
            "phone": phone,
            "address": address,
            "is_active": True,
            "is_verified": False,
            "created_at": new_agent.created_at.isoformat() if new_agent.created_at else "",
        }


async def authenticate_real_estate_agent(email: str, password: str) -> Optional[dict]:
    """Authenticate real estate agent and return agent data if valid"""
    async with AsyncSessionLocal() as session:
        # Find agent by email
        stmt = select(RealEstateAgent).where(RealEstateAgent.email == email.lower())
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return None
        
        # Check if agent is active
        if not agent.is_active:
            return None
        
        # Verify password
        if not verify_password(password, agent.hashed_password):
            return None
        
        return {
            "id": agent.id,
            "email": agent.email,
            "full_name": agent.full_name,
            "company_name": agent.company_name,
            "phone": agent.phone,
            "address": agent.address,
            "is_active": agent.is_active,
            "is_verified": agent.is_verified,
        }


async def get_real_estate_agent_by_id(agent_id: str) -> Optional[dict]:
    """Get real estate agent by ID"""
    async with AsyncSessionLocal() as session:
        stmt = select(RealEstateAgent).where(RealEstateAgent.id == agent_id)
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if not agent:
            return None
        
        return {
            "id": agent.id,
            "email": agent.email,
            "full_name": agent.full_name,
            "company_name": agent.company_name,
            "phone": agent.phone,
            "address": agent.address,
            "is_active": agent.is_active,
            "is_verified": agent.is_verified,
        }


async def get_or_create_agent_from_google(google_info: dict) -> dict:
    """Get existing agent or create new one from Google OAuth"""
    import uuid
    
    async with AsyncSessionLocal() as session:
        # Check if agent exists by email
        stmt = select(RealEstateAgent).where(RealEstateAgent.email == google_info["email"].lower())
        result = await session.execute(stmt)
        agent = result.scalar_one_or_none()
        
        if agent:
            # Agent exists, return it
            if not agent.is_active:
                raise ValueError("Agent account is inactive")
            return {
                "id": agent.id,
                "email": agent.email,
                "full_name": agent.full_name,
                "company_name": agent.company_name,
                "phone": agent.phone,
                "address": agent.address,
                "is_active": agent.is_active,
                "is_verified": agent.is_verified,
            }
        
        # Create new agent from Google
        agent_id = str(uuid.uuid4())
        new_agent = RealEstateAgent(
            id=agent_id,
            email=google_info["email"].lower(),
            hashed_password="",  # No password for Google auth
            full_name=google_info.get("name", ""),
            company_name=None,
            phone=None,
            address=None,
            is_active=True,
            is_verified=False,
        )
        
        session.add(new_agent)
        await session.commit()
        await session.refresh(new_agent)
        
        # Automatically assign a phone number to the agent
        try:
            await assign_phone_number_to_agent(agent_id)
        except Exception as e:
            print(f"Warning: Failed to assign phone number during Google registration: {str(e)}")
        
        return {
            "id": agent_id,
            "email": google_info["email"].lower(),
            "full_name": google_info.get("name", ""),
            "company_name": None,
            "phone": None,
            "address": None,
            "is_active": True,
            "is_verified": False,
        }
