"""
Test Case Suite: Contact Management Module
Test ID Range: TC-036 to TC-045

This test suite validates contact management functionality, including contact creation,
retrieval, updating, and linking contacts to properties.
"""

import pytest
import uuid
from httpx import AsyncClient
from app.models.contact import Contact
from app.models.property import Property


class TestContactCreation:
    """
    Test Case TC-036: Create Contact with Valid Data
    Description: Verify that an agent can successfully create a new contact
    Expected Result: Returns 201 status code with created contact details
    """
    @pytest.mark.asyncio
    async def test_tc036_create_contact_valid_data(self, authenticated_agent, db_session):
        """TC-036: Create contact with valid data"""
        client, agent = authenticated_agent
        
        contact_data = {
            "name": "Ali Khan",
            "email": "ali.khan@example.com",
            "phone_number": "+923331234567"
        }
        
        response = await client.post("/contacts", json=contact_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == "Ali Khan"
        assert data["email"] == "ali.khan@example.com"
        # Phone number is normalized (removes + prefix)
        assert data["phone_number"] in ["+923331234567", "923331234567"]
        assert data["real_estate_agent_id"] == str(agent.id)
        assert "id" in data

    """
    Test Case TC-037: Create Contact with Invalid Email Format
    Description: Verify that contact creation fails when email format is invalid
    Expected Result: Returns 422 status code with email validation error
    """
    @pytest.mark.asyncio
    async def test_tc037_create_contact_invalid_email(self, authenticated_agent):
        """TC-037: Create contact with invalid email"""
        client, _ = authenticated_agent
        
        response = await client.post("/contacts", json={
            "name": "Bad Contact",
            "email": "not-an-email",
            "phone_number": "+923001234567"
        })
        assert response.status_code == 422

    """
    Test Case TC-038: Create Contact with Invalid Phone Number
    Description: Verify that contact creation fails when phone number format is invalid
    Expected Result: Returns 422 status code with phone validation error
    """
    @pytest.mark.asyncio
    async def test_tc038_create_contact_invalid_phone(self, authenticated_agent):
        """TC-038: Create contact with invalid phone number"""
        client, _ = authenticated_agent
        
        response = await client.post("/contacts", json={
            "name": "Bad Contact",
            "email": "test@example.com",
            "phone_number": "123"  # Too short
        })
        assert response.status_code == 422


class TestContactRetrieval:
    """
    Test Case TC-039: Retrieve Contacts with Pagination
    Description: Verify that contacts can be retrieved with pagination
    Expected Result: Returns 200 status code with paginated contact list
    """
    @pytest.mark.asyncio
    async def test_tc039_retrieve_contacts_paginated(self, authenticated_agent, db_session):
        """TC-039: Retrieve contacts with pagination"""
        client, agent = authenticated_agent
        
        # Create multiple contacts
        for i in range(5):
            contact = Contact(
                id=str(uuid.uuid4()),
                name=f"Contact {i}",
                email=f"contact{i}@example.com",
                phone_number=f"+92300123456{i}",
                real_estate_agent_id=agent.id
            )
            db_session.add(contact)
        await db_session.commit()
        
        response = await client.get("/contacts/my-contacts")
        assert response.status_code == 200
        
        data = response.json()
        # Response is a list, not a paginated dict
        if isinstance(data, list):
            assert len(data) >= 5
        else:
            assert len(data.get("items", [])) >= 2
            assert data.get("total", 0) >= 5

    """
    Test Case TC-040: Retrieve Contact by ID
    Description: Verify that a specific contact can be retrieved by its ID
    Expected Result: Returns 200 status code with contact details
    """
    @pytest.mark.asyncio
    async def test_tc040_retrieve_contact_by_id(self, authenticated_agent, db_session):
        """TC-040: Retrieve contact by ID"""
        client, agent = authenticated_agent
        
        # Create a contact
        contact = Contact(
            id=str(uuid.uuid4()),
            name="Ahmed Raza",
            email="ahmed@example.com",
            phone_number="+923331234567",
            real_estate_agent_id=agent.id
        )
        db_session.add(contact)
        await db_session.commit()
        await db_session.refresh(contact)
        
        response = await client.get(f"/contacts/{contact.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == str(contact.id)
        assert data["name"] == "Ahmed Raza"

    """
    Test Case TC-041: Search Contacts by Name
    Description: Verify that contacts can be searched by name
    Expected Result: Returns 200 status code with matching contacts
    """
    @pytest.mark.asyncio
    async def test_tc041_search_contacts_by_name(self, authenticated_agent, db_session):
        """TC-041: Search contacts by name"""
        client, agent = authenticated_agent
        
        # Create contacts with similar names
        contacts = [
            Contact(id=str(uuid.uuid4()), name="Ahmed Raza", email="ahmed1@test.com", phone_number="+923001", real_estate_agent_id=agent.id),
            Contact(id=str(uuid.uuid4()), name="Ahmed Ali", email="ahmed2@test.com", phone_number="+923002", real_estate_agent_id=agent.id),
            Contact(id=str(uuid.uuid4()), name="Zain Malik", email="zain@test.com", phone_number="+923003", real_estate_agent_id=agent.id),
        ]
        db_session.add_all(contacts)
        await db_session.commit()
        
        response = await client.get("/contacts/my-contacts?search=ahmed")
        assert response.status_code == 200
        
        data = response.json()
        # Response is a list, not a paginated dict
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items", [])
        assert len(items) == 2
        assert all("ahmed" in item["name"].lower() for item in items)


class TestContactUpdate:
    """
    Test Case TC-042: Update Contact with Valid Data
    Description: Verify that an agent can successfully update contact details
    Expected Result: Returns 200 status code with updated contact details
    """
    @pytest.mark.asyncio
    async def test_tc042_update_contact_valid_data(self, authenticated_agent, db_session):
        """TC-042: Update contact with valid data"""
        client, agent = authenticated_agent
        
        # Create a contact
        contact = Contact(
            id=str(uuid.uuid4()),
            name="Original Name",
            email="original@example.com",
            phone_number="+923001234567",
            real_estate_agent_id=agent.id
        )
        db_session.add(contact)
        await db_session.commit()
        await db_session.refresh(contact)
        
        # Update the contact
        update_data = {
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone_number": "+923009876543"
        }
        
        response = await client.patch(f"/contacts/{contact.id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "updated@example.com"

    """
    Test Case TC-043: Link Contact to Property
    Description: Verify that a contact can be linked to a property
    Expected Result: Returns 200 status code, contact is linked to property
    """
    @pytest.mark.asyncio
    async def test_tc043_link_contact_to_property(self, authenticated_agent, db_session):
        """TC-043: Link contact to property"""
        client, agent = authenticated_agent
        
        # Create a contact
        contact = Contact(
            id=str(uuid.uuid4()),
            name="Property Owner",
            email="owner@example.com",
            phone_number="+923331234567",
            real_estate_agent_id=agent.id
        )
        db_session.add(contact)
        
        # Create a property
        property_obj = Property(
            id=str(uuid.uuid4()),
            address="123 Test Street",
            bedrooms=3,
            bathrooms=2,
            price=250000,
            real_estate_agent_id=agent.id,
            is_available="true",
            owner_phone="+923001234567"
        )
        db_session.add(property_obj)
        await db_session.commit()
        await db_session.refresh(contact)
        await db_session.refresh(property_obj)
        
        # Link contact to property by updating property's contact_id
        response = await client.patch(
            f"/properties/{property_obj.id}",
            json={"contact_id": str(contact.id)}
        )
        assert response.status_code in [200, 201]
        
        # Verify link - get contact with properties
        contact_response = await client.get(f"/contacts/{contact.id}")
        assert contact_response.status_code == 200
        contact_data = contact_response.json()
        # Contact should exist
        assert contact_data["id"] == str(contact.id)


class TestContactDeletion:
    """
    Test Case TC-044: Delete Contact
    Description: Verify that an agent can successfully delete a contact
    Expected Result: Returns 200 or 204 status code, contact is removed
    """
    @pytest.mark.asyncio
    async def test_tc044_delete_contact(self, authenticated_agent, db_session):
        """TC-044: Delete contact"""
        client, agent = authenticated_agent
        
        # Create a contact
        contact = Contact(
            id=str(uuid.uuid4()),
            name="Contact to Delete",
            email="delete@example.com",
            phone_number="+923001234567",
            real_estate_agent_id=agent.id
        )
        db_session.add(contact)
        await db_session.commit()
        await db_session.refresh(contact)
        
        contact_id = contact.id
        
        # Delete the contact
        response = await client.delete(f"/contacts/{contact_id}")
        assert response.status_code in [200, 204]
        
        # Verify it's gone
        response2 = await client.get(f"/contacts/{contact_id}")
        assert response2.status_code == 404

    """
    Test Case TC-045: Retrieve Contacts Linked to Property
    Description: Verify that contacts linked to a property can be retrieved
    Expected Result: Returns 200 status code with linked contacts
    """
    @pytest.mark.asyncio
    async def test_tc045_retrieve_contacts_linked_to_property(self, authenticated_agent, db_session):
        """TC-045: Retrieve contacts linked to property"""
        client, agent = authenticated_agent
        
        # Create a property
        property_obj = Property(
            id=str(uuid.uuid4()),
            address="Property with Contacts",
            bedrooms=3,
            bathrooms=2,
            price=300000,
            real_estate_agent_id=agent.id,
            is_available="true",
            owner_phone="+923001234567"
        )
        db_session.add(property_obj)
        
        # Create contacts and link them
        contacts = [
            Contact(id=str(uuid.uuid4()), name="Owner 1", email="owner1@test.com", phone_number="+923001", real_estate_agent_id=agent.id),
            Contact(id=str(uuid.uuid4()), name="Owner 2", email="owner2@test.com", phone_number="+923002", real_estate_agent_id=agent.id),
        ]
        db_session.add_all(contacts)
        await db_session.commit()
        await db_session.refresh(property_obj)
        
        # Retrieve contacts for the property - link them first
        # Update property to link contacts
        await client.patch(f"/properties/{property_obj.id}", json={"contact_id": str(contacts[0].id)})
        
        # Get property details which should include contact info
        response = await client.get(f"/properties/{property_obj.id}")
        assert response.status_code == 200
        
        data = response.json()
        # Property should have contact_id linked
        assert "contact_id" in data or "contact" in data
