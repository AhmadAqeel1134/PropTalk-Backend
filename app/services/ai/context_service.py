"""
Context Service - Build rich context for LLM responses
Reads database to provide context, but performs NO writes
"""
from typing import Dict, List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.database.connection import AsyncSessionLocal
from app.models.contact import Contact
from app.models.property import Property
from app.models.voice_agent import VoiceAgent
from app.models.real_estate_agent import RealEstateAgent
import logging

logger = logging.getLogger(__name__)


async def build_outbound_context(
    contact_id: str,
    real_estate_agent_id: str,
    voice_agent_id: str
) -> Dict:
    """
    Build rich context for outbound calls
    Returns: Contact info, their properties, voice agent info, real estate agent info
    NO DATABASE WRITES - READ ONLY
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get contact with properties
            contact_stmt = (
                select(Contact)
                .where(
                    and_(
                        Contact.id == contact_id,
                        Contact.real_estate_agent_id == real_estate_agent_id
                    )
                )
            )
            contact_result = await session.execute(contact_stmt)
            contact = contact_result.scalar_one_or_none()
            
            if not contact:
                logger.warning(f"⚠️ Contact not found: {contact_id}")
                return {"error": "Contact not found"}
            
            # Get contact's properties
            properties_stmt = select(Property).where(
                and_(
                    Property.contact_id == contact_id,
                    Property.real_estate_agent_id == real_estate_agent_id
                )
            )
            properties_result = await session.execute(properties_stmt)
            properties = properties_result.scalars().all()
            
            # Get voice agent
            voice_agent_stmt = (
                select(VoiceAgent)
                .where(VoiceAgent.id == voice_agent_id)
            )
            voice_agent_result = await session.execute(voice_agent_stmt)
            voice_agent = voice_agent_result.scalar_one_or_none()
            
            # Get real estate agent
            agent_stmt = select(RealEstateAgent).where(
                RealEstateAgent.id == real_estate_agent_id
            )
            agent_result = await session.execute(agent_stmt)
            agent = agent_result.scalar_one_or_none()
            
            # Format properties for context
            properties_list = []
            for prop in properties:
                prop_info = {
                    "address": prop.address,
                    "city": prop.city or "",
                    "state": prop.state or "",
                    "property_type": prop.property_type or "Property",
                    "price": f"${prop.price:,.0f}" if prop.price else "Price not set",
                    "bedrooms": prop.bedrooms,
                    "bathrooms": prop.bathrooms,
                    "square_feet": prop.square_feet,
                    "is_available": prop.is_available == "true",
                    "description": prop.description or "",
                    "amenities": prop.amenities or ""
                }
                properties_list.append(prop_info)
            
            # Format properties text for prompt
            properties_text = ""
            if properties_list:
                for i, prop in enumerate(properties_list, 1):
                    properties_text += f"\nProperty {i}:"
                    properties_text += f"\n  Address: {prop['address']}"
                    if prop['city']:
                        properties_text += f", {prop['city']}"
                    if prop['state']:
                        properties_text += f", {prop['state']}"
                    properties_text += f"\n  Type: {prop['property_type']}"
                    properties_text += f"\n  Price: {prop['price']}"
                    if prop['bedrooms']:
                        properties_text += f"\n  Bedrooms: {prop['bedrooms']}"
                    if prop['bathrooms']:
                        properties_text += f"\n  Bathrooms: {prop['bathrooms']}"
                    if prop['square_feet']:
                        properties_text += f"\n  Square Feet: {prop['square_feet']}"
                    properties_text += f"\n  Available: {'Yes' if prop['is_available'] else 'No'}"
                    if prop['description']:
                        properties_text += f"\n  Description: {prop['description']}"
                    if prop['amenities']:
                        properties_text += f"\n  Amenities: {prop['amenities']}"
            else:
                properties_text = "No properties linked to this contact."
            
            context = {
                "contact": {
                    "name": contact.name,
                    "phone_number": contact.phone_number,
                    "email": contact.email or "",
                    "notes": contact.notes or ""
                },
                "properties": properties_list,
                "properties_text": properties_text,
                "property_count": len(properties_list),
                "voice_agent": {
                    "name": voice_agent.name if voice_agent else "Property Assistant",
                    "system_prompt": voice_agent.system_prompt if voice_agent else ""
                },
                "real_estate_agent": {
                    "name": agent.full_name if agent else "",
                    "company_name": agent.company_name or "Independent Agent" if agent else "",
                    "address": agent.address or "" if agent else ""
                }
            }
            
            logger.info(f"✅ Built outbound context for contact {contact_id} - {len(properties_list)} properties")
            return context
            
    except Exception as e:
        logger.error(f"❌ Error building outbound context: {str(e)}", exc_info=True)
        return {"error": f"Failed to build context: {str(e)}"}


async def build_inbound_context(
    real_estate_agent_id: str,
    voice_agent_id: str,
    caller_phone: Optional[str] = None
) -> Dict:
    """
    Build rich context for inbound calls
    Returns: Voice agent info, real estate agent info, all available properties
    Optionally: Check if caller is an existing contact
    NO DATABASE WRITES - READ ONLY
    """
    try:
        async with AsyncSessionLocal() as session:
            # Get voice agent
            voice_agent_stmt = (
                select(VoiceAgent)
                .where(VoiceAgent.id == voice_agent_id)
            )
            voice_agent_result = await session.execute(voice_agent_stmt)
            voice_agent = voice_agent_result.scalar_one_or_none()
            
            # Get real estate agent
            agent_stmt = select(RealEstateAgent).where(
                RealEstateAgent.id == real_estate_agent_id
            )
            agent_result = await session.execute(agent_stmt)
            agent = agent_result.scalar_one_or_none()
            
            # Get all available properties for this agent
            properties_stmt = select(Property).where(
                and_(
                    Property.real_estate_agent_id == real_estate_agent_id,
                    Property.is_available == "true"
                )
            )
            properties_result = await session.execute(properties_stmt)
            properties = properties_result.scalars().all()
            
            # Check if caller is an existing contact
            caller_contact = None
            if caller_phone:
                # Normalize phone number for lookup
                normalized_phone = caller_phone.strip().replace(" ", "").replace("-", "")
                if not normalized_phone.startswith("+"):
                    if normalized_phone.startswith("92"):
                        normalized_phone = "+" + normalized_phone
                    elif normalized_phone.startswith("0"):
                        normalized_phone = "+92" + normalized_phone[1:]
                
                contact_stmt = select(Contact).where(
                    and_(
                        Contact.real_estate_agent_id == real_estate_agent_id,
                        or_(
                            Contact.phone_number == caller_phone,
                            Contact.phone_number == normalized_phone,
                            Contact.phone_number.like(f"%{normalized_phone[-10:]}%")  # Last 10 digits
                        )
                    )
                )
                contact_result = await session.execute(contact_stmt)
                caller_contact = contact_result.scalar_one_or_none()
            
            # Format properties for context
            properties_list = []
            for prop in properties:
                prop_info = {
                    "id": prop.id,
                    "address": prop.address,
                    "city": prop.city or "",
                    "state": prop.state or "",
                    "property_type": prop.property_type or "Property",
                    "price": f"${prop.price:,.0f}" if prop.price else "Price not set",
                    "bedrooms": prop.bedrooms,
                    "bathrooms": prop.bathrooms,
                    "square_feet": prop.square_feet,
                    "description": prop.description or "",
                    "amenities": prop.amenities or ""
                }
                properties_list.append(prop_info)
            
            # Group properties by type and city for easier reference
            properties_by_type = {}
            properties_by_city = {}
            for prop in properties_list:
                prop_type = prop['property_type']
                city = prop['city'] or "Unknown"
                
                if prop_type not in properties_by_type:
                    properties_by_type[prop_type] = []
                properties_by_type[prop_type].append(prop)
                
                if city not in properties_by_city:
                    properties_by_city[city] = []
                properties_by_city[city].append(prop)
            
            # Format properties summary for prompt
            properties_summary = f"Total available properties: {len(properties_list)}\n\n"
            
            if properties_list:
                properties_summary += "PROPERTIES:\n"
                for i, prop in enumerate(properties_list[:20], 1):  # Limit to 20 for prompt size
                    properties_summary += f"\n{i}. {prop['address']}"
                    if prop['city']:
                        properties_summary += f", {prop['city']}"
                    properties_summary += f" - {prop['property_type']} - {prop['price']}"
                    if prop['bedrooms']:
                        properties_summary += f" ({prop['bedrooms']} bed"
                        if prop['bathrooms']:
                            properties_summary += f", {prop['bathrooms']} bath"
                        properties_summary += ")"
                if len(properties_list) > 20:
                    properties_summary += f"\n... and {len(properties_list) - 20} more properties"
            else:
                properties_summary = "No available properties at this time."
            
            context = {
                "voice_agent": {
                    "name": voice_agent.name if voice_agent else "Property Assistant",
                    "system_prompt": voice_agent.system_prompt if voice_agent else ""
                },
                "real_estate_agent": {
                    "name": agent.full_name if agent else "",
                    "company_name": agent.company_name or "Independent Agent" if agent else ""
                },
                "properties": properties_list,
                "properties_summary": properties_summary,
                "properties_by_type": properties_by_type,
                "properties_by_city": properties_by_city,
                "total_properties": len(properties_list),
                "caller_contact": {
                    "name": caller_contact.name,
                    "phone_number": caller_contact.phone_number,
                    "has_properties": len([p for p in properties_list if p.get('contact_id') == caller_contact.id]) > 0
                } if caller_contact else None
            }
            
            logger.info(f"✅ Built inbound context for agent {real_estate_agent_id} - {len(properties_list)} properties")
            return context
            
    except Exception as e:
        logger.error(f"❌ Error building inbound context: {str(e)}", exc_info=True)
        return {"error": f"Failed to build context: {str(e)}"}
