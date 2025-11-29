from app.config import settings


def is_admin_email_allowed(email: str) -> bool:
    """Check if email is in admin whitelist (from env)"""
    return email.lower() in settings.admin_email_list

