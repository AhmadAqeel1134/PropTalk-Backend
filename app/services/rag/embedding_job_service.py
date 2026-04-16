import uuid
from typing import Any, Dict, Optional
from sqlalchemy import desc, select

from app.database.connection import AsyncSessionLocal
from app.models.rag_embedding_job import RagEmbeddingJob


async def create_embedding_job(
    *,
    real_estate_agent_id: str,
    document_id: str,
    status: str = "stored_only",
    embedding_model: Optional[str] = None,
    chunk_count: Optional[int] = None,
    avg_chunk_chars: Optional[int] = None,
    vector_dim: Optional[int] = None,
    processing_time_ms: Optional[int] = None,
    quality_score: Optional[float] = None,
    notes: Optional[str] = None,
    metrics_json: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        row = RagEmbeddingJob(
            id=str(uuid.uuid4()),
            real_estate_agent_id=real_estate_agent_id,
            document_id=document_id,
            status=status,
            embedding_model=embedding_model,
            chunk_count=chunk_count,
            avg_chunk_chars=avg_chunk_chars,
            vector_dim=vector_dim,
            processing_time_ms=processing_time_ms,
            quality_score=quality_score,
            notes=notes,
            metrics_json=metrics_json or {},
        )
        session.add(row)
        await session.commit()
        return {"id": row.id}


async def update_embedding_job(job_id: str, **fields: Any) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(RagEmbeddingJob, job_id)
        if not row:
            return
        for key, val in fields.items():
            if hasattr(row, key):
                setattr(row, key, val)
        await session.commit()


async def get_embedding_overview(agent_id: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    RagEmbeddingJob.status,
                    RagEmbeddingJob.processing_time_ms,
                    RagEmbeddingJob.chunk_count,
                    RagEmbeddingJob.quality_score,
                ).where(RagEmbeddingJob.real_estate_agent_id == agent_id)
            )
        ).all()
        total = len(rows)
        if total == 0:
            return {
                "total_jobs": 0,
                "avg_processing_time_ms": 0.0,
                "avg_chunk_count": 0.0,
                "avg_quality_score": None,
                "completed_jobs": 0,
                "failed_jobs": 0,
                "stored_only_jobs": 0,
            }

        completed = len([r for r in rows if r[0] == "completed"])
        failed = len([r for r in rows if r[0] in ("failed", "error")])
        stored_only = len([r for r in rows if r[0] == "stored_only"])
        proc = [r[1] for r in rows if r[1] is not None]
        chunks = [r[2] for r in rows if r[2] is not None]
        quality = [r[3] for r in rows if r[3] is not None]
        return {
            "total_jobs": total,
            "avg_processing_time_ms": round(sum(proc) / len(proc), 2) if proc else 0.0,
            "avg_chunk_count": round(sum(chunks) / len(chunks), 2) if chunks else 0.0,
            "avg_quality_score": round(sum(quality) / len(quality), 4) if quality else None,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "stored_only_jobs": stored_only,
        }


async def get_embedding_jobs(agent_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(RagEmbeddingJob)
                .where(RagEmbeddingJob.real_estate_agent_id == agent_id)
                .order_by(desc(RagEmbeddingJob.created_at))
                .limit(limit)
            )
        ).scalars().all()
        return [
            {
                "id": r.id,
                "document_id": r.document_id,
                "status": r.status,
                "embedding_model": r.embedding_model,
                "chunk_count": r.chunk_count,
                "avg_chunk_chars": r.avg_chunk_chars,
                "vector_dim": r.vector_dim,
                "processing_time_ms": r.processing_time_ms,
                "quality_score": r.quality_score,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]
