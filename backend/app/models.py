from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class QueryMode(str, Enum):
    AUTO = "auto"
    LLM = "llm"
    RAG = "rag"
    AGENT = "agent"


class QueryFilters(BaseModel):
    document_id: str | None = None
    section: str | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    context: str | None = None
    mode: QueryMode = QueryMode.AUTO
    top_k: int = Field(default=5, ge=1, le=10)
    filters: QueryFilters = Field(default_factory=QueryFilters)

    @field_validator("filters", mode="before")
    @classmethod
    def default_filters(cls, value):
        return {} if value is None else value


class Citation(BaseModel):
    source: str
    chunk_id: str
    chunk_index: int
    score: float | None = None
    quote: str


class RetrievedChunk(BaseModel):
    id: str
    text: str
    source: str
    chunk_index: int
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStep(BaseModel):
    step_id: str
    tool: str
    input: str
    output: str
    status: str
    latency_ms: float


class TraceStep(BaseModel):
    step: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ResponseMetrics(BaseModel):
    latency_ms: float
    tokens: int = 0
    retrieval_time_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None
    provider: str | None = None
    fallback_used: bool = False
    route_decision: str
    cache_hit: bool = False
    error: str | None = None


class QueryResponse(BaseModel):
    answer: str
    session_id: str
    mode_used: QueryMode
    error: bool = False
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    agent_steps: list[AgentStep] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    metrics: ResponseMetrics
    request_id: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    file_name: str
    chunks_indexed: int
    chunks_skipped: int
    status: str
    suggested_queries: list[str] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    document_id: str
    file_name: str
    chunks: int
    updated_at: str


class HistoryTurn(BaseModel):
    id: int
    session_id: str
    user_input: str
    system_response: str
    mode_used: str
    request_id: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class HistoryResponse(BaseModel):
    session_id: str
    turns: list[HistoryTurn]


class SessionMetricsResponse(BaseModel):
    session_id: str
    query_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
