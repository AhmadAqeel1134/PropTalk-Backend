from pydantic import BaseModel


class RealEstateAgentStats(BaseModel):
    total_agents: int
    active_agents: int
    inactive_agents: int
    verified_agents: int
    unverified_agents: int


class AdminDashboardResponse(BaseModel):
    real_estate_agents: RealEstateAgentStats

