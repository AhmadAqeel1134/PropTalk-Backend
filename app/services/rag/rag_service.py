"""
Retrieval-augmented generation: Gemini chat + embedding API (or OpenAI embeddings),
scoped to knowledge_base documents per agent.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.ai.llm_service import process_with_llm
from app.services.rag.chunk_store import load_kb_chunks_for_agent, rank_chunks_by_query
from app.services.rag.embedding_client import embed_text, embedding_model_id, resolve_embedding_backend

logger = logging.getLogger(__name__)

RETRIEVAL_K = 5


def _parse_judge_json(raw: str) -> Dict[str, Any]:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        out = json.loads(cleaned)
        return out if isinstance(out, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    brace = cleaned.find("{")
    if brace != -1:
        depth = 0
        for i in range(brace, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        out = json.loads(cleaned[brace : i + 1])
                        return out if isinstance(out, dict) else {}
                    except (json.JSONDecodeError, TypeError):
                        break
    return {}


def _extract_sources(answer: str, top: List[Dict[str, Any]]) -> List[str]:
    for line in reversed((answer or "").split("\n")):
        low = line.strip().lower()
        if low.startswith("sources:"):
            rest = line.split(":", 1)[1].strip()
            parts = [p.strip() for p in rest.split(",") if p.strip()]
            if parts:
                return parts
    names = [r.get("file_name") for r in top if r.get("file_name")]
    return list(dict.fromkeys(names))


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


class RagService:
    async def answer_user_message(
        self,
        *,
        real_estate_agent_id: str,
        end_user_id: str,
        end_user_phone_digits: str,
        message: str,
    ) -> dict:
        _ = (end_user_id, end_user_phone_digits)
        t0 = time.perf_counter()
        retrieval_latency_ms = 0
        generation_latency_ms = 0

        if not settings.GEMINI_API_KEY:
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": (
                    "Chat answers that use your agent's documents require the Gemini API key "
                    "to be configured on the server."
                ),
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": 0,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": 0,
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "no_llm_key"},
            }

        if not resolve_embedding_backend():
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": (
                    "Document Q&A needs an embedding API key. Set GEMINI_API_KEY (recommended) "
                    "or OPENAI_API_KEY on the server, then upload knowledge-base files again."
                ),
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": 0,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": 0,
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "no_embedding_key"},
            }

        rows = await load_kb_chunks_for_agent(real_estate_agent_id)
        if not rows:
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": (
                    "This agent has no indexed knowledge-base content yet. "
                    "Ask your agent to upload PDF, DOCX, or CSV files as **Knowledge base** in the portal."
                ),
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": RETRIEVAL_K,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": 0,
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "no_kb_chunks"},
            }

        try:
            _, model_label = embedding_model_id()
        except ValueError as e:
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": str(e),
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": 0,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": 0,
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "embedding_config_error"},
            }

        t_embed = time.perf_counter()
        try:
            qvec = await embed_text(message[:12000])
        except Exception as e:
            logger.warning("RAG query embedding failed: %s", e, exc_info=True)
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": "Could not process your question for document search right now. Please try again shortly.",
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": RETRIEVAL_K,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": int((time.perf_counter() - t_embed) * 1000),
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "embed_query_failed", "error": str(e)[:500]},
            }

        retrieval_latency_ms = int((time.perf_counter() - t_embed) * 1000)
        top = rank_chunks_by_query(
            qvec,
            rows,
            top_k=RETRIEVAL_K,
            embedding_model=model_label,
        )
        if not top:
            total_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "answer": (
                    "Knowledge-base files are indexed with a different embedding setup than the server "
                    "is using now. Re-upload the documents after confirming GEMINI_API_KEY or OPENAI_API_KEY."
                ),
                "sources": [],
                "rag_enabled": False,
                "retrieval_k": RETRIEVAL_K,
                "retrieved_chunks": 0,
                "retrieval_latency_ms": retrieval_latency_ms,
                "generation_latency_ms": 0,
                "total_latency_ms": total_ms,
                "context_recall_score": None,
                "context_precision_score": None,
                "answer_relevance_score": None,
                "faithfulness_score": None,
                "correctness_score": None,
                "citation_precision_score": None,
                "hallucination_flag": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "estimated_cost_usd": None,
                "metadata_json": {"mode": "embedding_mismatch", "expected_model": model_label},
            }

        context_parts: List[str] = []
        for i, row in enumerate(top, 1):
            snip = (row.get("content") or "")[:1800]
            context_parts.append(f"[{i}] (from {row.get('file_name', 'document')})\n{snip}")
        context_block = "\n\n".join(context_parts)

        system_prompt = (
            "You answer questions for property buyers and renters using ONLY the CONTEXT below. "
            "If the CONTEXT does not support an answer, say the information is not in the uploaded documents. "
            "Be concise and professional. Do not invent facts, prices, or policies. "
            "End your reply with a single line starting exactly with 'Sources:' followed by a comma-separated "
            "list of document file names you relied on (names appear in CONTEXT labels)."
        )
        user_block = f"CONTEXT:\n{context_block}\n\nQUESTION:\n{message}"

        t_gen = time.perf_counter()
        answer = await process_with_llm(
            user_input=user_block,
            system_prompt=system_prompt,
            conversation_history=None,
            max_tokens=600,
            temperature=0.35,
            timeout=28.0,
        )
        generation_latency_ms = int((time.perf_counter() - t_gen) * 1000)

        sources = _extract_sources(answer, top)
        sims = [float(row.get("similarity") or 0.0) for row in top]
        context_recall = round(min(1.0, max(0.0, sum(sims) / max(len(sims), 1))), 4)
        above = len([s for s in sims if s >= 0.22])
        context_precision = round(above / max(len(sims), 1), 4)

        faithfulness: Optional[float] = None
        answer_relevance: Optional[float] = None
        hallucination_flag: Optional[bool] = None
        judge_token_addon = 0
        try:
            judge_user = (
                f"QUESTION:\n{message[:2000]}\n\nCONTEXT (excerpts):\n{context_block[:6500]}\n\n"
                f"ANSWER:\n{answer[:3500]}\n\n"
                "Reply with ONLY valid JSON with keys: faithfulness (number 0-1), "
                "answer_relevance (number 0-1), hallucination (boolean). "
                "faithfulness is how well every factual claim in ANSWER is supported by CONTEXT. "
                "answer_relevance is how well ANSWER addresses QUESTION."
            )
            judge_sys = "You score retrieval QA. Output JSON only, no markdown."
            judge_raw = await process_with_llm(
                user_input=judge_user,
                system_prompt=judge_sys,
                conversation_history=None,
                max_tokens=180,
                temperature=0.1,
                timeout=15.0,
            )
            judge_token_addon = _estimate_tokens(judge_user + judge_sys + judge_raw)
            parsed = _parse_judge_json(judge_raw)
            if isinstance(parsed.get("faithfulness"), (int, float)):
                faithfulness = float(max(0.0, min(1.0, float(parsed["faithfulness"]))))
            if isinstance(parsed.get("answer_relevance"), (int, float)):
                answer_relevance = float(max(0.0, min(1.0, float(parsed["answer_relevance"]))))
            if isinstance(parsed.get("hallucination"), bool):
                hallucination_flag = parsed["hallucination"]
        except Exception as e:
            logger.debug("RAG judge call skipped/failed: %s", e)

        if hallucination_flag is None and faithfulness is not None:
            hallucination_flag = faithfulness < 0.35

        system_chars = len(system_prompt) + len(user_block)
        prompt_tokens = _estimate_tokens(system_prompt + user_block)
        completion_tokens = _estimate_tokens(answer)
        total_tokens = prompt_tokens + completion_tokens + judge_token_addon

        citation_precision = 1.0 if sources else None
        total_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "answer": answer,
            "sources": sources,
            "rag_enabled": True,
            "retrieval_k": RETRIEVAL_K,
            "retrieved_chunks": len(top),
            "retrieval_latency_ms": retrieval_latency_ms,
            "generation_latency_ms": generation_latency_ms,
            "total_latency_ms": total_ms,
            "context_recall_score": context_recall,
            "context_precision_score": context_precision,
            "answer_relevance_score": answer_relevance,
            "faithfulness_score": faithfulness,
            "correctness_score": None,
            "citation_precision_score": citation_precision,
            "hallucination_flag": hallucination_flag,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": None,
            "metadata_json": {
                "mode": "rag",
                "embedding_model": model_label,
                "top_similarities": [round(s, 4) for s in sims],
                "system_and_user_chars": system_chars,
            },
        }


def get_rag_service() -> RagService:
    return RagService()
