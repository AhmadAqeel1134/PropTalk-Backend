from pydantic import BaseModel


class RealEstateAgentStats(BaseModel):
    total_agents: int
    active_agents: int
    inactive_agents: int
    verified_agents: int
    unverified_agents: int


class OverallStats(BaseModel):
    total_properties: int
    total_documents: int
    total_phone_numbers: int
    total_contacts: int


class AdminDashboardResponse(BaseModel):
    real_estate_agents: RealEstateAgentStats
    overall_stats: OverallStats

