from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database.connection import close_db, engine
from app.controllers.auth_controller import router as auth_router
from app.controllers.admin_controller import router as admin_router
from app.controllers.real_estate_agent_auth_controller import router as agent_auth_router
from app.controllers.google_auth_controller import router as google_auth_router
from app.controllers.phone_number_controller import router as phone_number_router
from app.controllers.document_controller import router as document_router
from app.controllers.real_estate_agent.contact_controller import router as contact_router
from app.controllers.real_estate_agent.dashboard_controller import router as agent_dashboard_router
from app.controllers.real_estate_agent.property_controller import router as agent_property_router
from app.controllers.real_estate_agent.profile_controller import router as agent_profile_router
from app.controllers.voice_agent_controller import router as voice_agent_router
from app.controllers.call_controller import router as call_router
from app.controllers.twilio_controller.webhook_controller import router as webhook_router
import logging
import time

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests"""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        # Log incoming request
        print(f"\n{'='*70}")
        print(f"🌐 INCOMING REQUEST")
        print(f"{'='*70}")
        print(f"📍 Method: {request.method}")
        print(f"📍 Path: {request.url.path}")
        print(f"📍 Query: {request.url.query or 'None'}")
        print(f"📍 Client IP: {client_ip}")
        
        # Log important headers only
        headers_to_log = {}
        for header in ["authorization", "content-type", "user-agent", "origin", "referer"]:
            if header in request.headers:
                if header == "authorization":
                    headers_to_log[header] = request.headers[header][:20] + "..." if len(request.headers[header]) > 20 else request.headers[header]
                else:
                    headers_to_log[header] = request.headers[header]
        if headers_to_log:
            print(f"📍 Headers: {headers_to_log}")
        
        # For POST/PUT/PATCH, log that body exists (actual body will be logged in endpoint)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            content_length = request.headers.get("content-length", "unknown")
            print(f"📍 Body: Content-Type={content_type}, Length={content_length}")
        
        print(f"{'='*70}\n")
        logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
        
        # Process request
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        print(f"✅ Response: {response.status_code} ({process_time:.3f}s)\n")
        logger.info(f"Response: {response.status_code} for {request.method} {request.url.path} ({process_time:.3f}s)")
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Test database connection on startup (non-blocking - don't fail startup)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.warning(f"⚠️ Database connection failed on startup: {str(e)}")
        logger.warning("⚠️ App will continue, but database-dependent features may not work")
        # Don't raise - allow app to start even if DB is temporarily unavailable
        # This is important for webhook endpoints that need to respond quickly
    
    yield
    
    # Cleanup on shutdown
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {str(e)}")


app = FastAPI(
    title="PropTalk API",
    description="AI-Powered Receptionist Service for Real Estate",
    version="1.0.0",
    lifespan=lifespan
)

# Add request logging middleware first (runs before CORS)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(agent_auth_router)
app.include_router(google_auth_router)
app.include_router(phone_number_router)
app.include_router(document_router)
# Agent property router has enhanced features (filters, sorting).
# Old generic property_router has been removed to avoid route conflicts
# and to ensure all filters work correctly for agents.
app.include_router(contact_router)
app.include_router(agent_dashboard_router)
app.include_router(agent_property_router)
app.include_router(agent_profile_router)
app.include_router(voice_agent_router)
app.include_router(call_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    return {"message": "PropTalk API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

