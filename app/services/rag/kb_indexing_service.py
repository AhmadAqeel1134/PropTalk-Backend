from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Tuple

from app.services.document_parser_service import extract_plain_text_for_kb
from app.services.rag.chunk_store import delete_chunks_for_document, insert_kb_chunks
from app.services.rag.embedding_client import embed_text, embedding_model_id, resolve_embedding_backend
from app.services.rag.embedding_job_service import update_embedding_job

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1400
CHUNK_OVERLAP = 200
MAX_CONCURRENT_EMBEDS = 6


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = " ".join((text or "").split())
    if not text:
        return []
    chunks: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + size, n)
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i = max(end - overlap, i + 1)
    return chunks


async def run_kb_indexing(
    *,
    job_id: str,
    real_estate_agent_id: str,
    document_id: str,
    file_content: bytes,
    file_type: str,
) -> None:
    started = time.perf_counter()
    try:
        if not resolve_embedding_backend():
            raise ValueError("No embedding API key configured (GEMINI_API_KEY or OPENAI_API_KEY)")
        _, model_label = embedding_model_id()
        await update_embedding_job(
            job_id,
            status="processing",
            embedding_model=model_label,
            notes="Extracting text and generating embeddings",
        )
        raw = await extract_plain_text_for_kb(file_content, file_type)
        if not raw or not raw.strip():
            raise ValueError("No extractable text in this file for indexing")
        pieces = _chunk_text(raw)
        if not pieces:
            raise ValueError("Chunking produced no segments")

        sem = asyncio.Semaphore(MAX_CONCURRENT_EMBEDS)

        async def _one(idx: int, content: str) -> Tuple[int, str, List[float]]:
            body = content[:12000]
            async with sem:
                vec = await embed_text(body)
            return (idx, content, vec)

        embedded = await asyncio.gather(*[_one(i, c) for i, c in enumerate(pieces)])
        embedded.sort(key=lambda x: x[0])

        await delete_chunks_for_document(document_id)
        await insert_kb_chunks(
            real_estate_agent_id=real_estate_agent_id,
            document_id=document_id,
            chunks=[(i, c, v) for i, c, v in embedded],
            embedding_model=model_label,
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        dims = len(embedded[0][2]) if embedded else None
        avg_chars = sum(len(c) for _, c, _ in embedded) // max(len(embedded), 1)
        await update_embedding_job(
            job_id,
            status="completed",
            chunk_count=len(embedded),
            avg_chunk_chars=avg_chars,
            vector_dim=dims,
            processing_time_ms=elapsed_ms,
            notes=None,
            metrics_json={"chunking": {"chunk_size": CHUNK_SIZE, "overlap": CHUNK_OVERLAP}},
        )
    except Exception as e:
        logger.exception("KB indexing failed document_id=%s", document_id)
        await update_embedding_job(
            job_id,
            status="failed",
            processing_time_ms=int((time.perf_counter() - started) * 1000),
            notes=str(e)[:2000],
        )
