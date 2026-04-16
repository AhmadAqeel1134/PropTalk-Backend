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
    
    # OpenAI (legacy - can be removed if not needed)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = "gpt-3.5-turbo"
    OPENAI_MAX_TOKENS: Optional[int] = 150
    OPENAI_TEMPERATURE: Optional[float] = 0.7
    
    # Google Gemini API
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = "gemini-2.5-flash-lite"  # Balanced model optimized for low latency
    GEMINI_MAX_TOKENS: Optional[int] = 200  # Gemini allows more tokens
    GEMINI_TEMPERATURE: Optional[float] = 0.7
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    
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

    # Hugging Face / external sentiment service (user-only transcript)
    SENTIMENT_ENABLED: bool = True
    SENTIMENT_SERVICE_URL: str = "https://zayan0978-proptalk-sentiment.hf.space"
    SENTIMENT_REQUEST_TIMEOUT_SECONDS: float = 60.0

    # Email (SMTP) — used for showing confirmations
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SENDER_EMAIL: Optional[str] = None
    SENDER_EMAIL_PASSWORD: Optional[str] = None
    SENDER_NAME: str = "PropTalk"

    # ElevenLabs TTS — human-quality voice for the calling agent
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_DEFAULT_VOICE_ID: str = "pNInz6obpgDQGcFmaJgB"   # "Adam" — warm male
    ELEVENLABS_MODEL_ID: str = "eleven_turbo_v2_5"               # lowest-latency model

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

