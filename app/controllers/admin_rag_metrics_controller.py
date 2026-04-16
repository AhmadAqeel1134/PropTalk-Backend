from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.database.connection import AsyncSessionLocal
from app.models.real_estate_agent import RealEstateAgent
from app.models.rag_query_log import RagQueryLog
from app.schemas.rag_metrics import (
    RagEmbeddingJobItem,
    RagEmbeddingOverviewResponse,
    RagFailuresItem,
    RagOverviewResponse,
    RagRecentQueriesResponse,
    RagTimeseriesPoint,
    RagTopSourceItem,
)
from app.services.rag.embedding_job_service import get_embedding_jobs, get_embedding_overview
from app.services.rag.telemetry_service import (
    get_rag_failures,
    get_rag_overview,
    get_rag_recent_queries,
    get_rag_timeseries,
    get_rag_top_sources,
)
from app.utils.dependencies import get_current_admin_id

router = APIRouter(prefix="/admin/rag/metrics", tags=["Admin RAG Metrics"])


async def _ensure_agent(agent_id: str) -> None:
    async with AsyncSessionLocal() as session:
        exists = (
            await session.execute(
                select(func.count(RealEstateAgent.id)).where(RealEstateAgent.id == agent_id)
            )
        ).scalar_one()
        if not exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")


@router.get("/agents")
async def list_agents_with_rag_counts(admin_id: str = Depends(get_current_admin_id)):
    _ = admin_id
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    RealEstateAgent.id,
                    RealEstateAgent.full_name,
                    RealEstateAgent.company_name,
                    func.count(RagQueryLog.id).label("rag_queries"),
                )
                .outerjoin(
                    RagQueryLog,
                    RagQueryLog.real_estate_agent_id == RealEstateAgent.id,
                )
                .group_by(
                    RealEstateAgent.id,
                    RealEstateAgent.full_name,
                    RealEstateAgent.company_name,
                )
                .order_by(RealEstateAgent.full_name.asc())
            )
        ).all()
        return [
            {
                "id": r[0],
                "full_name": r[1],
                "company_name": r[2],
                "rag_queries": int(r[3] or 0),
            }
            for r in rows
        ]


@router.get("/{agent_id}/overview", response_model=RagOverviewResponse)
async def admin_get_overview(
    agent_id: str,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    return RagOverviewResponse(**(await get_rag_overview(agent_id, window)))


@router.get("/{agent_id}/timeseries", response_model=list[RagTimeseriesPoint])
async def admin_get_timeseries(
    agent_id: str,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    bucket: str = Query("day", pattern="^(day|week)$"),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    rows = await get_rag_timeseries(agent_id, window=window, bucket=bucket)
    return [RagTimeseriesPoint(**r) for r in rows]


@router.get("/{agent_id}/failures", response_model=list[RagFailuresItem])
async def admin_get_failures(
    agent_id: str,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    limit: int = Query(20, ge=1, le=200),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    rows = await get_rag_failures(agent_id, window=window, limit=limit)
    return [RagFailuresItem(**r) for r in rows]


@router.get("/{agent_id}/top-sources", response_model=list[RagTopSourceItem])
async def admin_get_top_sources(
    agent_id: str,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    limit: int = Query(10, ge=1, le=50),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    rows = await get_rag_top_sources(agent_id, window=window, limit=limit)
    return [RagTopSourceItem(**r) for r in rows]


@router.get("/{agent_id}/queries", response_model=RagRecentQueriesResponse)
async def admin_get_queries(
    agent_id: str,
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    items, total = await get_rag_recent_queries(
        agent_id, page=page, page_size=page_size, window=window
    )
    return RagRecentQueriesResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{agent_id}/embedding/overview", response_model=RagEmbeddingOverviewResponse)
async def admin_get_embedding_overview(
    agent_id: str,
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    return RagEmbeddingOverviewResponse(**(await get_embedding_overview(agent_id)))


@router.get("/{agent_id}/embedding/jobs", response_model=list[RagEmbeddingJobItem])
async def admin_get_embedding_jobs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=200),
    admin_id: str = Depends(get_current_admin_id),
):
    _ = admin_id
    await _ensure_agent(agent_id)
    rows = await get_embedding_jobs(agent_id, limit=limit)
    return [RagEmbeddingJobItem(**r) for r in rows]
