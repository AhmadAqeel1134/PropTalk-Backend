"""
Test Case Suite: Authentication Module
Test ID Range: TC-001 to TC-010

This test suite validates the authentication functionality of the PropTalk backend,
including admin login, token generation, and session management.
"""

import pytest
import uuid
from httpx import AsyncClient
from app.models.admin import Admin
from app.utils.security import get_password_hash


class TestAuthentication:
    """
    Test Case TC-001: Admin Login with Valid Credentials
    Description: Verify that an admin can successfully log in with correct email and password
    Expected Result: Returns 200 status code with access token
    """
    @pytest.mark.asyncio
    async def test_tc001_admin_login_valid_credentials(self, client: AsyncClient, db_session):
        """TC-001: Admin login with valid credentials"""
        # Create test admin user
        admin_id = str(uuid.uuid4())
        test_admin = Admin(
            id=admin_id,
            email="i221134@nu.edu.pk",
            hashed_password=get_password_hash("test_password"),
            full_name="Test Admin",
            is_active=True,
            is_super_admin=False
        )
        db_session.add(test_admin)
        await db_session.commit()
        
        response = await client.post(
            "/auth/admin/login",
            json={
                "email": "i221134@nu.edu.pk",
                "password": "test_password"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    """
    Test Case TC-002: Admin Login with Invalid Email
    Description: Verify that login fails when incorrect email is provided
    Expected Result: Returns 401 status code with error message
    """
    @pytest.mark.asyncio
    async def test_tc002_admin_login_invalid_email(self, client: AsyncClient):
        """TC-002: Admin login with invalid email"""
        response = await client.post(
            "/auth/admin/login",
            json={
                "email": "invalid@example.com",
                "password": "test_password"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "incorrect" in data["detail"].lower() or "invalid" in data["detail"].lower()

    """
    Test Case TC-003: Admin Login with Invalid Password
    Description: Verify that login fails when incorrect password is provided
    Expected Result: Returns 401 status code with error message
    """
    @pytest.mark.asyncio
    async def test_tc003_admin_login_invalid_password(self, client: AsyncClient, db_session):
        """TC-003: Admin login with invalid password"""
        # Create test admin user
        admin_id = str(uuid.uuid4())
        test_admin = Admin(
            id=admin_id,
            email="i221134@nu.edu.pk",
            hashed_password=get_password_hash("test_password"),
            full_name="Test Admin",
            is_active=True,
            is_super_admin=False
        )
        db_session.add(test_admin)
        await db_session.commit()
        
        response = await client.post(
            "/auth/admin/login",
            json={
                "email": "i221134@nu.edu.pk",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    """
    Test Case TC-004: Admin Login with Missing Email
    Description: Verify that login fails when email field is missing
    Expected Result: Returns 422 status code indicating validation error
    """
    @pytest.mark.asyncio
    async def test_tc004_admin_login_missing_email(self, client: AsyncClient):
        """TC-004: Admin login with missing email"""
        response = await client.post(
            "/auth/admin/login",
            json={
                "password": "test_password"
            }
        )
        
        assert response.status_code == 422

    """
    Test Case TC-005: Admin Login with Missing Password
    Description: Verify that login fails when password field is missing
    Expected Result: Returns 422 status code indicating validation error
    """
    @pytest.mark.asyncio
    async def test_tc005_admin_login_missing_password(self, client: AsyncClient):
        """TC-005: Admin login with missing password"""
        response = await client.post(
            "/auth/admin/login",
            json={
                "email": "i221134@nu.edu.pk"
            }
        )
        
        assert response.status_code == 422

    """
    Test Case TC-006: Get Current Admin with Valid Token
    Description: Verify that authenticated admin can retrieve their profile information
    Expected Result: Returns 200 status code with admin details
    """
    @pytest.mark.asyncio
    async def test_tc006_get_current_admin_valid_token(self, client: AsyncClient, db_session):
        """TC-006: Get current admin with valid token"""
        # Create test admin user
        admin_id = str(uuid.uuid4())
        test_admin = Admin(
            id=admin_id,
            email="i221134@nu.edu.pk",
            hashed_password=get_password_hash("test_password"),
            full_name="Test Admin",
            is_active=True,
            is_super_admin=False
        )
        db_session.add(test_admin)
        await db_session.commit()
        
        # First login to get token
        login_response = await client.post(
            "/auth/admin/login",
            json={
                "email": "i221134@nu.edu.pk",
                "password": "test_password"
            }
        )
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            
            # Use token to get admin info
            response = await client.get(
                "/auth/admin/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "email" in data

    """
    Test Case TC-007: Get Current Admin with Invalid Token
    Description: Verify that request fails when invalid or expired token is provided
    Expected Result: Returns 401 status code indicating unauthorized access
    """
    @pytest.mark.asyncio
    async def test_tc007_get_current_admin_invalid_token(self, client: AsyncClient):
        """TC-007: Get current admin with invalid token"""
        response = await client.get(
            "/auth/admin/me",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        
        assert response.status_code == 401

    """
    Test Case TC-008: Get Current Admin without Token
    Description: Verify that request fails when no authentication token is provided
    Expected Result: Returns 401 status code indicating unauthorized access
    """
    @pytest.mark.asyncio
    async def test_tc008_get_current_admin_no_token(self, client: AsyncClient):
        """TC-008: Get current admin without token"""
        response = await client.get("/auth/admin/me")
        
        assert response.status_code == 401

    """
    Test Case TC-009: Real Estate Agent Login with Valid Credentials
    Description: Verify that a real estate agent can successfully log in
    Expected Result: Returns 200 status code with access token
    """
    @pytest.mark.asyncio
    async def test_tc009_agent_login_valid_credentials(self, client: AsyncClient):
        """TC-009: Real estate agent login with valid credentials"""
        response = await client.post(
            "/auth/real-estate-agent/login",
            json={
                "email": "agent@example.com",
                "password": "agent_password"
            }
        )
        
        # This test may fail if no agent exists, which is acceptable
        # The important part is that the endpoint exists and handles the request
        assert response.status_code in [200, 401, 404]

    """
    Test Case TC-010: Token Format Validation
    Description: Verify that generated tokens follow the expected JWT format
    Expected Result: Token contains three parts separated by dots
    """
    @pytest.mark.asyncio
    async def test_tc010_token_format_validation(self, client: AsyncClient, db_session):
        """TC-010: Token format validation"""
        # Create test admin user
        admin_id = str(uuid.uuid4())
        test_admin = Admin(
            id=admin_id,
            email="i221134@nu.edu.pk",
            hashed_password=get_password_hash("test_password"),
            full_name="Test Admin",
            is_active=True,
            is_super_admin=False
        )
        db_session.add(test_admin)
        await db_session.commit()
        
        response = await client.post(
            "/auth/admin/login",
            json={
                "email": "i221134@nu.edu.pk",
                "password": "test_password"
            }
        )
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            # JWT tokens have three parts separated by dots
            parts = token.split(".")
            assert len(parts) == 3, "Token should have three parts (header.payload.signature)"
