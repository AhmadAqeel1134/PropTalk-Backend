from google.auth.transport import requests
from google.oauth2 import id_token
from app.config import settings
from typing import Dict


async def verify_google_token(token: str) -> Dict[str, str]:
    """
    Verify Google ID token and return user info
    
    Args:
        token: Google ID token from frontend
        
    Returns:
        Dictionary with user info: email, name, picture, google_id
        
    Raises:
        ValueError: If token is invalid
    """
    try:
        if not settings.GOOGLE_CLIENT_ID:
            raise ValueError("Google Client ID not configured")
            
        # Verify the token with clock skew tolerance (10 seconds)
        # This handles small time differences between client and server clocks
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10
        )
        
        # Check if token is from the correct issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')
        
        return {
            "email": idinfo["email"],
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
            "google_id": idinfo["sub"]
        }
    except ValueError as e:
        raise ValueError(f"Invalid Google token: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error verifying Google token: {str(e)}")
