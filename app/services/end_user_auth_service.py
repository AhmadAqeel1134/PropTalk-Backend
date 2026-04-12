import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from app.database.connection import AsyncSessionLocal
from app.models.end_user import EndUser
from app.utils.security import verify_password, get_password_hash
from app.services.real_estate_agent.contact_service import normalize_phone


async def register_end_user(
    email: str,
    password: str,
    full_name: str,
    phone_number: Optional[str] = None,
) -> dict:
    async with AsyncSessionLocal() as session:
        stmt = select(EndUser).where(EndUser.email == email.lower())
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("An account with this email already exists")

        user_id = str(uuid.uuid4())
        normalized_phone = normalize_phone(phone_number) if phone_number else None
        now = datetime.now(timezone.utc)
        new_user = EndUser(
            id=user_id,
            email=email.lower(),
            hashed_password=get_password_hash(password),
            full_name=full_name,
            phone_number=normalized_phone or None,
            phone_saved_at=now if normalized_phone else None,
            is_active=True,
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return _user_to_public_dict(new_user)


async def authenticate_end_user(email: str, password: str) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        stmt = select(EndUser).where(EndUser.email == email.lower())
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return _user_to_public_dict(user)


async def get_end_user_by_id(user_id: str) -> Optional[dict]:
    async with AsyncSessionLocal() as session:
        stmt = select(EndUser).where(EndUser.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None
        return _user_to_public_dict(user)


async def update_end_user_phone(user_id: str, phone_number: str) -> dict:
    digits = normalize_phone(phone_number)
    if len(digits) < 10:
        raise ValueError("Phone number must contain at least 10 digits")

    async with AsyncSessionLocal() as session:
        stmt = select(EndUser).where(EndUser.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        user.phone_number = digits
        user.phone_saved_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(user)
        return _user_to_public_dict(user)


def _user_to_public_dict(user: EndUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone_number": user.phone_number,
        "phone_saved_at": user.phone_saved_at.isoformat() if user.phone_saved_at else None,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }
