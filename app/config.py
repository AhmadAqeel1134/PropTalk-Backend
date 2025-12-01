from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_VOICE_WEBHOOK_URL: Optional[str] = None  # Base URL for webhooks (ngrok or production)
    
    OPENAI_API_KEY: Optional[str] = None
    
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str
    
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    ADMIN_ONE_EMAIL: str
    ADMIN_TWO_EMAIL: str
    ADMIN_THREE_EMAIL: str
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def admin_email_list(self) -> list[str]:
        """Get admin email whitelist from env"""
        return [
            self.ADMIN_ONE_EMAIL.lower(),
            self.ADMIN_TWO_EMAIL.lower(),
            self.ADMIN_THREE_EMAIL.lower(),
        ]


settings = Settings()

