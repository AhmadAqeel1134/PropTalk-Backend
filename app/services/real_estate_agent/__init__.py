# Real Estate Agent Services
from app.services.real_estate_agent.contact_service import (
    create_contact,
    find_or_create_contact_by_phone,
    get_contacts_by_agent_id,
    get_contact_by_id,
    update_contact,
    delete_contact,
    get_contact_properties,
    link_property_to_contact,
)

__all__ = [
    "create_contact",
    "find_or_create_contact_by_phone",
    "get_contacts_by_agent_id",
    "get_contact_by_id",
    "update_contact",
    "delete_contact",
    "get_contact_properties",
    "link_property_to_contact",
]

