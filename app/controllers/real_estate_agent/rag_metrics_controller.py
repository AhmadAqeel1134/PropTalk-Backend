from fastapi import APIRouter, Depends, HTTPException, Query, status

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
from app.utils.dependencies import get_current_real_estate_agent_id

router = APIRouter(prefix="/agent/rag/metrics", tags=["Agent RAG Metrics"])


@router.get("/overview", response_model=RagOverviewResponse)
async def get_overview(
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    return RagOverviewResponse(**(await get_rag_overview(agent_id, window)))


@router.get("/timeseries", response_model=list[RagTimeseriesPoint])
async def get_timeseries(
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    bucket: str = Query("day", pattern="^(day|week)$"),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    try:
        rows = await get_rag_timeseries(agent_id, window=window, bucket=bucket)
        return [RagTimeseriesPoint(**r) for r in rows]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/failures", response_model=list[RagFailuresItem])
async def get_failures(
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    limit: int = Query(20, ge=1, le=200),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    rows = await get_rag_failures(agent_id, window=window, limit=limit)
    return [RagFailuresItem(**r) for r in rows]


@router.get("/top-sources", response_model=list[RagTopSourceItem])
async def get_top_sources(
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    limit: int = Query(10, ge=1, le=50),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    rows = await get_rag_top_sources(agent_id, window=window, limit=limit)
    return [RagTopSourceItem(**r) for r in rows]


@router.get("/queries", response_model=RagRecentQueriesResponse)
async def get_recent_queries(
    window: str = Query("30d", pattern="^(7d|30d|90d)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    items, total = await get_rag_recent_queries(
        agent_id, page=page, page_size=page_size, window=window
    )
    return RagRecentQueriesResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/embedding/overview", response_model=RagEmbeddingOverviewResponse)
async def get_embedding_overview_endpoint(
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    return RagEmbeddingOverviewResponse(**(await get_embedding_overview(agent_id)))


@router.get("/embedding/jobs", response_model=list[RagEmbeddingJobItem])
async def get_embedding_jobs_endpoint(
    limit: int = Query(20, ge=1, le=200),
    agent_id: str = Depends(get_current_real_estate_agent_id),
):
    rows = await get_embedding_jobs(agent_id, limit=limit)
    return [RagEmbeddingJobItem(**r) for r in rows]
