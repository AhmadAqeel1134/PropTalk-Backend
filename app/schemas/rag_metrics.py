from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class RagOverviewResponse(BaseModel):
    total_queries: int = 0
    success_queries: int = 0
    failed_queries: int = 0
    success_rate_pct: float = 0.0
    rag_enabled_rate_pct: float = 0.0
    avg_total_latency_ms: float = 0.0
    p95_total_latency_ms: float = 0.0
    avg_faithfulness: Optional[float] = None
    avg_answer_relevance: Optional[float] = None
    avg_context_recall: Optional[float] = None
    avg_context_precision: Optional[float] = None
    avg_correctness: Optional[float] = None
    hallucination_rate_pct: float = 0.0
    avg_estimated_cost_usd: Optional[float] = None


class RagEmbeddingOverviewResponse(BaseModel):
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    stored_only_jobs: int = 0
    avg_processing_time_ms: float = 0.0
    avg_chunk_count: float = 0.0
    avg_quality_score: Optional[float] = None


class RagEmbeddingJobItem(BaseModel):
    id: str
    document_id: str
    status: str
    embedding_model: Optional[str] = None
    chunk_count: Optional[int] = None
    avg_chunk_chars: Optional[int] = None
    vector_dim: Optional[int] = None
    processing_time_ms: Optional[int] = None
    quality_score: Optional[float] = None
    notes: Optional[str] = None
    created_at: str


class RagTimeseriesPoint(BaseModel):
    bucket: str
    total_queries: int
    success_rate_pct: float
    avg_total_latency_ms: float
    avg_faithfulness: Optional[float] = None
    avg_answer_relevance: Optional[float] = None


class RagFailuresItem(BaseModel):
    id: str
    created_at: str
    question: str
    error_message: Optional[str] = None
    status: str
    total_latency_ms: Optional[int] = None


class RagTopSourceItem(BaseModel):
    source: str
    count: int


class RagQueryLogItem(BaseModel):
    id: str
    created_at: str
    question: str
    answer_preview: Optional[str] = None
    status: str
    rag_enabled: bool
    total_latency_ms: Optional[int] = None
    retrieval_latency_ms: Optional[int] = None
    generation_latency_ms: Optional[int] = None
    faithfulness_score: Optional[float] = None
    answer_relevance_score: Optional[float] = None
    context_recall_score: Optional[float] = None
    context_precision_score: Optional[float] = None
    correctness_score: Optional[float] = None
    citation_precision_score: Optional[float] = None
    hallucination_flag: Optional[bool] = None
    top_sources: Optional[List[str]] = Field(default_factory=list)


class RagRecentQueriesResponse(BaseModel):
    items: List[RagQueryLogItem]
    total: int
    page: int
    page_size: int


class RagQueryLogCreate(BaseModel):
    real_estate_agent_id: str
    end_user_id: Optional[str] = None
    question: str
    answer: Optional[str] = None
    status: str = "success"
    error_message: Optional[str] = None
    rag_enabled: bool = False
    retrieval_k: Optional[int] = None
    retrieved_chunks: Optional[int] = None
    context_recall_score: Optional[float] = None
    context_precision_score: Optional[float] = None
    answer_relevance_score: Optional[float] = None
    faithfulness_score: Optional[float] = None
    correctness_score: Optional[float] = None
    citation_precision_score: Optional[float] = None
    hallucination_flag: Optional[bool] = None
    retrieval_latency_ms: Optional[int] = None
    generation_latency_ms: Optional[int] = None
    total_latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    top_sources: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
