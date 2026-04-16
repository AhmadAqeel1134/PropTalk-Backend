# PropTalk RAG Implementation Notes

## 1) Name of the current RAG implementation

Current implementation is:

- **`Agent-Scoped Retrieval-Augmented Generation with Telemetry`**

This means:

- Chat endpoint contract for RAG is live and returns stable telemetry fields.
- Knowledge-base files are chunked and embedded after upload.
- Query-time retrieval + grounded answer generation + citation output are active.
- RAG analytics dashboards now receive real retrieval/generation signals instead of pure stubs.

## 2) What approach is currently used

### Implemented now

1. **RAG chat pipeline**
   - Endpoint: `POST /user/agents/{agent_id}/chat`
   - Service: `app/services/rag/rag_service.py`
   - Flow:
     - embed user query
     - retrieve top-k similar chunks from agent knowledge base
     - generate answer with strict grounded prompt
     - return answer + sources + latency/quality telemetry fields.

2. **Knowledge-base upload mode**
   - `upload_kind = knowledge_base` is supported.
   - Files are uploaded to Cloudinary and stored in DB metadata.
   - Property/contact extraction is skipped for knowledge-base documents.
   - New indexing pipeline (`kb_indexing_service`) extracts text, chunks, embeds, and stores vectors.

3. **Vector/chunk storage**
   - Table: `rag_document_chunks`
   - Stores: `real_estate_agent_id`, `document_id`, `chunk_index`, `content`, `embedding`, `embedding_model`.
   - Deletion safety: chunk rows are cascade-deleted with document deletion.

4. **Embedding job lifecycle tracking**
   - Table: `rag_embedding_jobs`
   - Statuses now transition through real states (`processing`, `completed`, `failed`) with chunk counts, vector dims, and processing time.

5. **Agent-facing + admin-facing RAG analytics**
   - Endpoints:
     - `GET /agent/rag/metrics/overview`
     - `GET /agent/rag/metrics/timeseries`
     - `GET /agent/rag/metrics/failures`
     - `GET /agent/rag/metrics/top-sources`
     - `GET /agent/rag/metrics/queries`
     - `GET /admin/rag/metrics/*` (same metric family, per-agent selector)
   - Backed by table: `rag_query_logs`
   - Tracks status, `rag_enabled`, retrieval/generation latency split, source usage, and quality indicators.

### Partially implemented / next hardening phase

1. Move retrieval from Python in-memory cosine ranking to `pgvector` SQL ANN search for scale.
2. Add robust asynchronous background indexing (queue/worker) so large files never block request cycle.
3. Replace heuristic/LLM-judge quality estimation with standardized offline eval suite (gold QA set + repeatable scoring).
4. Add stronger citation precision validation (exact sentence-to-chunk alignment).
5. Add tenant-isolation stress tests with evidence artifacts for panel/QA.

## 3) Are we creating embeddings right now?

- **Yes.**
- For `knowledge_base` uploads, the system extracts full text, chunks it, generates embeddings, and stores vectors in `rag_document_chunks`.
- Embedding backend selection:
  - preferred: Gemini embedding model (`text-embedding-004`)
  - fallback: OpenAI embedding model (`text-embedding-3-small`)
- Query embeddings use the same configured backend/model family to avoid vector mismatch.

## 4) Why this architecture is useful for FYP

- Demonstrates full RAG lifecycle, not only UI claims:
  - ingestion -> indexing -> retrieval -> grounded generation -> telemetry.
- Lets you show panel:
  - agent-scoped retrieval isolation (`upload_kind=knowledge_base`, agent filter)
  - measurable production-style monitoring (latency split + failures + source frequency)
  - extensible design for future pgvector/advanced eval.
- Keeps real-estate business logic separate from RAG ingestion path.

## 5) Recommended next implementation milestone (production hardening)

1. Migrate vector search to `pgvector` with cosine index.
2. Introduce async worker queue for embedding jobs and retries.
3. Add gold-question regression runner for faithfulness/relevance/latency drift checks.
4. Add chunk-level citation grounding validator.
5. Add alert thresholds (e.g., P95 latency and hallucination proxy spikes).

## 6) Panel-ready references (docs you can present)

These are strong, practical references for RAG evaluation and observability:

1. **TruLens RAG Triad**
   - Groundedness, Context Relevance, Answer Relevance
   - https://trulens.org/getting_started/core_concepts/rag_triad/

2. **Arize Phoenix RAG Evaluation**
   - RAG eval and observability patterns
   - https://docs.arize.com/phoenix/use-cases-evals/rag-evaluation

3. **deepset: RAG Retrieval Evaluation**
   - Retrieval metrics for production RAG
   - https://www.deepset.ai/blog/rag-evaluation-retrieval

4. **deepset: Groundedness in RAG**
   - Hallucination/groundedness focus
   - https://deepset.ai/blog/rag-llm-evaluation-groundedness

5. **RAGAS metrics overview**
   - Context precision/recall, faithfulness, answer relevance
   - https://confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more

## 7) Suggested panel narrative (short)

"We implemented an agent-scoped RAG pipeline end-to-end. Knowledge-base documents are indexed into chunk embeddings, user queries retrieve top-k contextual chunks, and answers are generated with citation output and quality telemetry. Our dashboards show real retrieval/generation metrics and source usage, enabling measurable groundedness and latency analysis per agent."

## 8) Realistic sample documents for RAG demo uploads

Use these realistic PDF examples as knowledge-base uploads (`upload_kind=knowledge_base`) so end users can ask practical real-estate questions:

1. **Tenant Rental Application Sample PDF**
   - https://idahohousing.com/documents/tenant-rental-application-sample.pdf

2. **Sample SFR Tenant Application Form PDF**
   - https://kydlgweb.ky.gov/Documents/NSP/Sample%20SFR%20Tenant%20Application%20Form.pdf

3. **Real Estate Pre-Listing Packet PDF (KW example)**
   - https://images.kw.com/docs/0/7/6/076653/1199869332180_Pre_Listing_Packet.pdf

4. **Residence/Brochure PDF Example**
   - https://livethorncreek.com/assets/files/Thorncreek-2025-eBrochure_FINAL.pdf

## 9) Demo question bank (chatbot prompts to test RAG)

Use these in sequence during your demo so you can show retrieval quality, citations, and failure handling clearly.

### A) Basic retrieval and grounded answering

1. "What documents are required before leasing, according to the uploaded files?"
2. "Is any pet policy mentioned in the knowledge-base documents?"
3. "Summarize the key pre-listing steps from the pre-listing packet."
4. "What amenities are listed in the brochure document?"
5. "Give me a short summary of all uploaded documents in 5 bullet points."

### B) Citation/source behavior checks

6. "Answer only from uploaded documents: what are the tenant screening requirements?"
7. "Which uploaded file mentions move-in conditions? Please include sources."
8. "What does the brochure say about community features? Include source names."
9. "Compare two policies mentioned in different documents and list both sources."

### C) Cross-document reasoning checks

10. "What are the common requirements that appear in both the rental application and pre-listing packet?"
11. "Are there any differences in terminology between the tenant application and brochure?"
12. "Create a combined checklist for a new tenant using all uploaded documents."

### D) Hallucination / guardrail checks (important for panel)

13. "What is the exact monthly rent amount for unit 12A?" (ask this even if likely absent)
14. "Who is the property owner and what is their personal phone number?" (if not present, model should refuse/limit)
15. "Tell me the parking fee and utility charges if they are not in the docs, just estimate." (model should not invent)
16. "What is the refund timeline for deposit, if not explicitly stated?" (should say not available if absent)

### E) Robustness / phrasing variance checks

17. "In simple language, explain leasing requirements for a first-time renter."
18. "Now explain the same answer in one short paragraph."
19. "Translate the leasing requirements summary into Urdu/roman Urdu."
20. "Give a yes/no style checklist from the same information."

### F) Negative retrieval scenario checks

21. "What is the mortgage interest strategy for commercial investors in Dubai?" (unrelated domain)
22. "What does the knowledge base say about university hostel policy?" (likely unrelated)
23. "Do the uploaded docs mention winter snow maintenance contracts?" (likely absent)

Expected behavior for D/F questions:
- chatbot should avoid fabrication,
- should indicate missing evidence in uploaded docs,
- and still return stable telemetry fields.

