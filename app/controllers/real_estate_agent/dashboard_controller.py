"""
Agent Dashboard Controller - Dashboard statistics endpoint
"""
from fastapi import APIRouter, Depends
from app.schemas.agent_dashboard import AgentDashboardStatsResponse
from app.services.real_estate_agent.dashboard_service import get_agent_dashboard_stats
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/agent", tags=["Agent Dashboard"])


@router.get("/dashboard", response_model=AgentDashboardStatsResponse)
async def get_dashboard_stats(agent_id: str = Depends(get_current_real_estate_agent_id)):
    """
    Get comprehensive dashboard statistics for current agent
    Includes properties, documents, contacts, phone status, and recent activity
    Optimized for performance with database aggregations
    """
    stats = await get_agent_dashboard_stats(agent_id)
    return AgentDashboardStatsResponse(**stats)

