from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.database.connection import close_db, engine
from app.controllers.auth_controller import router as auth_router
from app.controllers.admin_controller import router as admin_router
from app.controllers.real_estate_agent_auth_controller import router as agent_auth_router
from app.controllers.google_auth_controller import router as google_auth_router
from app.controllers.phone_number_controller import router as phone_number_router
from app.controllers.document_controller import router as document_router
from app.controllers.property_controller import router as property_router
from app.controllers.real_estate_agent.contact_controller import router as contact_router
from app.controllers.real_estate_agent.dashboard_controller import router as agent_dashboard_router
from app.controllers.real_estate_agent.property_controller import router as agent_property_router
from app.controllers.real_estate_agent.profile_controller import router as agent_profile_router
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Test database connection on startup
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise
    
    yield
    await close_db()


app = FastAPI(
    title="PropTalk API",
    description="AI-Powered Receptionist Service for Real Estate",
    version="1.0.0",
    lifespan=lifespan
)

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
# Keep old property router for backward compatibility, but agent_property_router has enhanced features
app.include_router(property_router)
app.include_router(contact_router)
app.include_router(agent_dashboard_router)
app.include_router(agent_property_router)
app.include_router(agent_profile_router)


@app.get("/")
async def root():
    return {"message": "PropTalk API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

