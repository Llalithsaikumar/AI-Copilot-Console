import asyncio

from app.models import AgentStep, QueryMode, QueryRequest, RetrievedChunk, TraceStep
from app.services.agent import AgentRun
from app.services.cache import ResponseCache
from app.services.llm_provider import LLMResponse
from app.services.memory import InMemoryMemoryStore
from app.services.orchestrator import Orchestrator


class FakeLLM:
    embedding_model_name = "fake-embedding"

    async def chat(self, messages):
        return LLMResponse(
            content="grounded answer",
            usage={"prompt_tokens": 4, "completion_tokens": 5, "total_tokens": 9},
        )

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FailingLLM(FakeLLM):
    async def chat(self, messages):
        raise RuntimeError("provider unavailable")


class FakeRetriever:
    def __init__(self):
        self.chunk = RetrievedChunk(
            id="chunk-1",
            text="The launch report lists schedule risk.",
            source="report.txt",
            chunk_index=0,
            score=0.91,
            metadata={},
        )

    async def retrieve(self, query, top_k, user_id=None, session_id=None, filters=None):
        return [self.chunk]

    def all_chunks(self, user_id=None, session_id=None, filters=None):
        return [self.chunk]

    def revision(self, user_id=None):
        return 1


class FakeAgent:
    async def run(
        self,
        *,
        query,
        history,
        context_chunks,
        top_k,
        user_id=None,
        session_id=None,
        filters=None,
    ):
        return AgentRun(
            answer="agent answer",
            steps=[
                AgentStep(
                    step_id="step-1",
                    tool="extract_risks",
                    input=query,
                    output="schedule risk",
                    status="ok",
                    latency_ms=1.0,
                )
            ],
            trace=[
                TraceStep(
                    step="extract_risks",
                    meta={"status": "ok", "chunks": len(context_chunks)},
                )
            ],
            retrieved_chunks=context_chunks,
            usage={"total_tokens": 3},
        )


class CostSettings:
    price_per_1k_tokens = 0.5


def build_orchestrator(tmp_path, llm=None):
    return Orchestrator(
        llm=llm or FakeLLM(),
        retriever=FakeRetriever(),
        agent=FakeAgent(),
        memory=InMemoryMemoryStore(),
        cache=ResponseCache(),
        settings=CostSettings(),
    )


def test_route_uses_explicit_mode(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    request = QueryRequest(query="hello", session_id="session-1", mode=QueryMode.RAG)

    route = orchestrator.route(request, "user-1")

    assert route.mode == QueryMode.RAG
    assert route.reason == "explicit_rag"


def test_auto_routes_contact_field_lookup_to_rag(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    request = QueryRequest(query="give me mail id", session_id="session-1", mode=QueryMode.AUTO)

    route = orchestrator.route(request, "user-1")

    assert route.mode == QueryMode.RAG
    assert route.reason == "indexed_document_field_lookup"


def test_rag_query_returns_citations(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    request = QueryRequest(
        query="What does the uploaded report say?",
        session_id="session-1",
        mode=QueryMode.RAG,
    )

    response = asyncio.run(
        orchestrator.handle_query(request, request_id="request-1", user_id="user-1")
    )

    assert response.mode_used == QueryMode.RAG
    assert response.citations[0].source == "report.txt"
    assert response.metrics.total_tokens == 9
    assert response.metrics.tokens == 9
    assert response.metrics.cost == 0.0045
    assert response.metrics.retrieval_time_ms >= 0
    assert [step.step for step in response.trace] == [
        "route",
        "cache_check",
        "retrieve",
        "llm",
    ]


def test_agent_query_returns_steps(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    request = QueryRequest(
        query="Analyze the report and extract risks",
        session_id="session-2",
        mode=QueryMode.AGENT,
    )

    response = asyncio.run(
        orchestrator.handle_query(request, request_id="request-2", user_id="user-1")
    )

    assert response.mode_used == QueryMode.AGENT
    assert response.answer == "agent answer"
    assert response.agent_steps[0].tool == "extract_risks"
    assert any(step.step == "extract_risks" for step in response.trace)


def test_email_lookup_uses_local_extractor(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    orchestrator.retriever.chunk.text = "Reach me at person@example.com for details."
    request = QueryRequest(
        query="give me mail id",
        session_id="session-3",
        mode=QueryMode.AUTO,
    )

    response = asyncio.run(
        orchestrator.handle_query(request, request_id="request-3", user_id="user-1")
    )

    assert response.mode_used == QueryMode.RAG
    assert "person@example.com" in response.answer
    assert response.metrics.provider == "local-extractor"


def test_repeated_query_returns_cache_hit(tmp_path):
    orchestrator = build_orchestrator(tmp_path)
    request = QueryRequest(
        query="What does the uploaded report say?",
        session_id="session-cache",
        mode=QueryMode.RAG,
    )

    first = asyncio.run(
        orchestrator.handle_query(request, request_id="request-1", user_id="user-1")
    )
    second = asyncio.run(
        orchestrator.handle_query(request, request_id="request-2", user_id="user-1")
    )

    assert first.metrics.cache_hit is False
    assert second.metrics.cache_hit is True
    assert second.metrics.retrieval_time_ms == 0
    assert [step.step for step in second.trace] == [
        "route",
        "cache_check",
        "cache_return",
    ]
    assert second.metrics.cost == 0


def test_llm_failure_returns_graceful_error_response(tmp_path):
    orchestrator = build_orchestrator(tmp_path, llm=FailingLLM())
    request = QueryRequest(
        query="What does the uploaded report say?",
        session_id="session-error",
        mode=QueryMode.RAG,
    )

    response = asyncio.run(
        orchestrator.handle_query(request, request_id="request-error", user_id="user-1")
    )

    assert response.error is True
    assert response.answer == "Temporary issue, retrying..."
    assert response.metrics.error == "runtimeerror"
    assert any(step.step == "error" for step in response.trace)
