import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, desc, func, select

from app.database.connection import AsyncSessionLocal
from app.models.rag_query_log import RagQueryLog
from app.schemas.rag_metrics import RagQueryLogCreate


def _parse_window(window: str) -> datetime:
    now = datetime.now(timezone.utc)
    if window == "7d":
        return now - timedelta(days=7)
    if window == "30d":
        return now - timedelta(days=30)
    if window == "90d":
        return now - timedelta(days=90)
    raise ValueError("window must be one of: 7d, 30d, 90d")


def _percentile(values: List[int], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    idx = int(round((len(values_sorted) - 1) * p))
    return float(values_sorted[idx])


async def create_rag_query_log(payload: RagQueryLogCreate) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        rec = RagQueryLog(
            id=str(uuid.uuid4()),
            real_estate_agent_id=payload.real_estate_agent_id,
            end_user_id=payload.end_user_id,
            question=payload.question,
            answer=payload.answer,
            status=payload.status,
            error_message=payload.error_message,
            rag_enabled=payload.rag_enabled,
            retrieval_k=payload.retrieval_k,
            retrieved_chunks=payload.retrieved_chunks,
            context_recall_score=payload.context_recall_score,
            context_precision_score=payload.context_precision_score,
            answer_relevance_score=payload.answer_relevance_score,
            faithfulness_score=payload.faithfulness_score,
            correctness_score=payload.correctness_score,
            citation_precision_score=payload.citation_precision_score,
            hallucination_flag=payload.hallucination_flag,
            retrieval_latency_ms=payload.retrieval_latency_ms,
            generation_latency_ms=payload.generation_latency_ms,
            total_latency_ms=payload.total_latency_ms,
            prompt_tokens=payload.prompt_tokens,
            completion_tokens=payload.completion_tokens,
            total_tokens=payload.total_tokens,
            estimated_cost_usd=payload.estimated_cost_usd,
            top_sources=payload.top_sources or [],
            metadata_json=payload.metadata_json or {},
        )
        session.add(rec)
        await session.commit()
        return {"id": rec.id}


async def get_rag_overview(real_estate_agent_id: str, window: str = "30d") -> Dict[str, Any]:
    start_dt = _parse_window(window)
    async with AsyncSessionLocal() as session:
        base = and_(
            RagQueryLog.real_estate_agent_id == real_estate_agent_id,
            RagQueryLog.created_at >= start_dt,
        )
        rows = (
            await session.execute(
                select(
                    RagQueryLog.status,
                    RagQueryLog.rag_enabled,
                    RagQueryLog.total_latency_ms,
                    RagQueryLog.faithfulness_score,
                    RagQueryLog.answer_relevance_score,
                    RagQueryLog.context_recall_score,
                    RagQueryLog.context_precision_score,
                    RagQueryLog.correctness_score,
                    RagQueryLog.hallucination_flag,
                    RagQueryLog.estimated_cost_usd,
                ).where(base)
            )
        ).all()

        total = len(rows)
        if total == 0:
            return {
                "total_queries": 0,
                "success_queries": 0,
                "failed_queries": 0,
                "success_rate_pct": 0.0,
                "rag_enabled_rate_pct": 0.0,
                "avg_total_latency_ms": 0.0,
                "p95_total_latency_ms": 0.0,
                "avg_faithfulness": None,
                "avg_answer_relevance": None,
                "avg_context_recall": None,
                "avg_context_precision": None,
                "avg_correctness": None,
                "hallucination_rate_pct": 0.0,
                "avg_estimated_cost_usd": None,
            }

        success = [r for r in rows if r[0] == "success"]
        failed = [r for r in rows if r[0] != "success"]
        rag_enabled_count = len([r for r in rows if r[1]])
        latencies = [r[2] for r in rows if isinstance(r[2], int)]
        faithful = [r[3] for r in rows if r[3] is not None]
        answer_rel = [r[4] for r in rows if r[4] is not None]
        context_recall = [r[5] for r in rows if r[5] is not None]
        context_precision = [r[6] for r in rows if r[6] is not None]
        correctness = [r[7] for r in rows if r[7] is not None]
        hallucinations = [r[8] for r in rows if r[8] is not None]
        costs = [r[9] for r in rows if r[9] is not None]

        return {
            "total_queries": total,
            "success_queries": len(success),
            "failed_queries": len(failed),
            "success_rate_pct": round((len(success) / total) * 100, 2),
            "rag_enabled_rate_pct": round((rag_enabled_count / total) * 100, 2),
            "avg_total_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_total_latency_ms": round(_percentile(latencies, 0.95), 2) if latencies else 0.0,
            "avg_faithfulness": round(sum(faithful) / len(faithful), 4) if faithful else None,
            "avg_answer_relevance": round(sum(answer_rel) / len(answer_rel), 4) if answer_rel else None,
            "avg_context_recall": round(sum(context_recall) / len(context_recall), 4) if context_recall else None,
            "avg_context_precision": round(sum(context_precision) / len(context_precision), 4) if context_precision else None,
            "avg_correctness": round(sum(correctness) / len(correctness), 4) if correctness else None,
            "hallucination_rate_pct": round((len([h for h in hallucinations if h]) / len(hallucinations)) * 100, 2)
            if hallucinations
            else 0.0,
            "avg_estimated_cost_usd": round(sum(costs) / len(costs), 6) if costs else None,
        }


async def get_rag_timeseries(
    real_estate_agent_id: str, window: str = "30d", bucket: str = "day"
) -> List[Dict[str, Any]]:
    if bucket not in ("day", "week"):
        raise ValueError("bucket must be one of: day, week")
    start_dt = _parse_window(window)
    async with AsyncSessionLocal() as session:
        bucket_expr = func.date_trunc(bucket, RagQueryLog.created_at)
        rows = (
            await session.execute(
                select(
                    bucket_expr.label("b"),
                    func.count(RagQueryLog.id),
                    func.avg(case((RagQueryLog.status == "success", 1), else_=0)),
                    func.avg(RagQueryLog.total_latency_ms),
                    func.avg(RagQueryLog.faithfulness_score),
                    func.avg(RagQueryLog.answer_relevance_score),
                )
                .where(
                    and_(
                        RagQueryLog.real_estate_agent_id == real_estate_agent_id,
                        RagQueryLog.created_at >= start_dt,
                    )
                )
                .group_by(bucket_expr)
                .order_by(bucket_expr.asc())
            )
        ).all()

        return [
            {
                "bucket": r[0].isoformat() if r[0] else "",
                "total_queries": int(r[1] or 0),
                "success_rate_pct": round(float(r[2] or 0) * 100, 2),
                "avg_total_latency_ms": round(float(r[3] or 0), 2),
                "avg_faithfulness": round(float(r[4]), 4) if r[4] is not None else None,
                "avg_answer_relevance": round(float(r[5]), 4) if r[5] is not None else None,
            }
            for r in rows
        ]


async def get_rag_failures(
    real_estate_agent_id: str, window: str = "30d", limit: int = 20
) -> List[Dict[str, Any]]:
    start_dt = _parse_window(window)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(RagQueryLog)
                .where(
                    and_(
                        RagQueryLog.real_estate_agent_id == real_estate_agent_id,
                        RagQueryLog.created_at >= start_dt,
                        RagQueryLog.status != "success",
                    )
                )
                .order_by(desc(RagQueryLog.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "question": r.question,
                "error_message": r.error_message,
                "status": r.status,
                "total_latency_ms": r.total_latency_ms,
            }
            for r in rows
        ]


async def get_rag_top_sources(
    real_estate_agent_id: str, window: str = "30d", limit: int = 10
) -> List[Dict[str, Any]]:
    start_dt = _parse_window(window)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(RagQueryLog.top_sources).where(
                    and_(
                        RagQueryLog.real_estate_agent_id == real_estate_agent_id,
                        RagQueryLog.created_at >= start_dt,
                    )
                )
            )
        ).all()

        counts: Dict[str, int] = {}
        for (sources,) in rows:
            if not isinstance(sources, list):
                continue
            for s in sources:
                if not s:
                    continue
                counts[str(s)] = counts.get(str(s), 0) + 1
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"source": src, "count": cnt} for src, cnt in top]


async def get_rag_recent_queries(
    real_estate_agent_id: str, page: int = 1, page_size: int = 20, window: str = "30d"
) -> Tuple[List[Dict[str, Any]], int]:
    start_dt = _parse_window(window)
    async with AsyncSessionLocal() as session:
        base = and_(
            RagQueryLog.real_estate_agent_id == real_estate_agent_id,
            RagQueryLog.created_at >= start_dt,
        )
        total = (
            await session.execute(select(func.count(RagQueryLog.id)).where(base))
        ).scalar_one() or 0

        rows = (
            await session.execute(
                select(RagQueryLog)
                .where(base)
                .order_by(desc(RagQueryLog.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        items = []
        for r in rows:
            answer_preview = (r.answer[:220] + "...") if r.answer and len(r.answer) > 220 else r.answer
            items.append(
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "question": r.question,
                    "answer_preview": answer_preview,
                    "status": r.status,
                    "rag_enabled": r.rag_enabled,
                    "total_latency_ms": r.total_latency_ms,
                    "retrieval_latency_ms": r.retrieval_latency_ms,
                    "generation_latency_ms": r.generation_latency_ms,
                    "faithfulness_score": r.faithfulness_score,
                    "answer_relevance_score": r.answer_relevance_score,
                    "context_recall_score": r.context_recall_score,
                    "context_precision_score": r.context_precision_score,
                    "correctness_score": r.correctness_score,
                    "citation_precision_score": r.citation_precision_score,
                    "hallucination_flag": r.hallucination_flag,
                    "top_sources": r.top_sources or [],
                }
            )
        return items, int(total)
