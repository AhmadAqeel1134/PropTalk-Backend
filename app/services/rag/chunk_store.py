from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select

from app.database.connection import AsyncSessionLocal
from app.models.document import Document
from app.models.rag_document_chunk import RagDocumentChunk


async def delete_chunks_for_document(document_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(RagDocumentChunk).where(RagDocumentChunk.document_id == document_id))
        await session.commit()


async def insert_kb_chunks(
    *,
    real_estate_agent_id: str,
    document_id: str,
    chunks: List[Tuple[int, str, List[float]]],
    embedding_model: str,
) -> int:
    """chunks: list of (chunk_index, content, embedding_vector)."""
    async with AsyncSessionLocal() as session:
        for idx, content, emb in chunks:
            session.add(
                RagDocumentChunk(
                    id=str(uuid.uuid4()),
                    real_estate_agent_id=real_estate_agent_id,
                    document_id=document_id,
                    chunk_index=idx,
                    content=content,
                    embedding=emb,
                    embedding_model=embedding_model,
                )
            )
        await session.commit()
    return len(chunks)


async def load_kb_chunks_for_agent(real_estate_agent_id: str) -> List[Dict[str, Any]]:
    """
    All knowledge-base chunks with vectors for an agent (in-process cosine ranking).
    """
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(RagDocumentChunk, Document.file_name, Document.id)
                .join(Document, RagDocumentChunk.document_id == Document.id)
                .where(
                    RagDocumentChunk.real_estate_agent_id == real_estate_agent_id,
                    Document.upload_kind == "knowledge_base",
                )
            )
        ).all()
    out: List[Dict[str, Any]] = []
    for chunk, file_name, doc_id in rows:
        emb = chunk.embedding
        if not isinstance(emb, list) or not emb:
            continue
        vec = [float(x) for x in emb]
        out.append(
            {
                "chunk_id": chunk.id,
                "document_id": doc_id,
                "file_name": file_name or "document",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content or "",
                "embedding": vec,
                "embedding_model": chunk.embedding_model,
            }
        )
    return out


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def rank_chunks_by_query(
    query_vec: List[float],
    rows: List[Dict[str, Any]],
    *,
    top_k: int,
    embedding_model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    qdim = len(query_vec)
    pool: List[Dict[str, Any]] = []
    for r in rows:
        emb = r.get("embedding") or []
        if len(emb) != qdim:
            continue
        if embedding_model and r.get("embedding_model") != embedding_model:
            continue
        pool.append(r)
    if not pool:
        for r in rows:
            emb = r.get("embedding") or []
            if len(emb) == qdim:
                pool.append(r)
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for r in pool:
        sim = cosine_similarity(query_vec, r["embedding"])
        scored.append((sim, {**r, "similarity": sim}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:top_k]]
