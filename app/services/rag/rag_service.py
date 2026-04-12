"""
Retrieval-augmented generation entry point.

Replace `answer_user_message` with a real pipeline (embeddings, vector store, LLM)
without changing route signatures: inject a subclass via FastAPI dependencies.
"""
from typing import List


class RagService:
    """Stub implementation; swap for production RAG when ready."""

    async def answer_user_message(
        self,
        *,
        real_estate_agent_id: str,
        end_user_id: str,
        end_user_phone_digits: str,
        message: str,
    ) -> dict:
        return {
            "answer": (
                "Document Q&A is not enabled yet. When your agent adds knowledge-base "
                "documents, answers here will use retrieval-augmented generation."
            ),
            "sources": [],
            "rag_enabled": False,
        }


def get_rag_service() -> RagService:
    return RagService()
