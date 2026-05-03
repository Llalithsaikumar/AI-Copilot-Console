import asyncio
import json
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from app.config import Settings, get_settings
from app.evaluation.evaluator import (
    default_report_path,
    load_dataset,
    run_evaluation,
    write_report,
)
from app.models import (
    DocumentRecord,
    DocumentUploadResponse,
    HistoryResponse,
    QueryMode,
    QueryRequest,
    QueryResponse,
    SessionMetricsResponse,
)
from app.services.agent import AgentPipeline
from app.services.cache import ResponseCache
from app.services.document_loader import extract_text_from_upload
from app.services.errors import CopilotError
from app.services.llm_provider import GeminiClient, OpenRouterClient, ProviderFallbackClient
from app.services.memory import MemoryStore, build_memory_store
from app.services.metrics import MetricsRecorder
from app.services.orchestrator import Orchestrator
from app.services.retrieval import RetrievalService
from app.services.suggestions import suggest_queries_for_document


@dataclass
class ServiceContainer:
    settings: Settings
    llm: ProviderFallbackClient
    retriever: RetrievalService
    memory: MemoryStore
    cache: ResponseCache
    metrics: MetricsRecorder
    agent: AgentPipeline
    orchestrator: Orchestrator


def build_container() -> ServiceContainer:
    settings = get_settings()
    openrouter = OpenRouterClient(settings)
    gemini = GeminiClient(settings)
    llm = ProviderFallbackClient(openrouter, gemini)
    retriever = RetrievalService(settings, llm)
    memory = build_memory_store(settings)
    cache = ResponseCache()
    metrics = MetricsRecorder()
    agent = AgentPipeline(llm, retriever)
    orchestrator = Orchestrator(
        llm=llm,
        retriever=retriever,
        agent=agent,
        memory=memory,
        cache=cache,
        settings=settings,
    )
    return ServiceContainer(
        settings=settings,
        llm=llm,
        retriever=retriever,
        memory=memory,
        cache=cache,
        metrics=metrics,
        agent=agent,
        orchestrator=orchestrator,
    )


app = FastAPI(title="AI Copilot System", version="0.1.0")
app.state.container = build_container()
app.add_middleware(
    CORSMiddleware,
    allow_origins=app.state.container.settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def container() -> ServiceContainer:
    return app.state.container


@app.exception_handler(CopilotError)
async def copilot_error_handler(_, exc: CopilotError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message},
    )


@app.get("/health")
async def health() -> dict:
    services = container()
    return {
        "status": "ok",
        "app": services.settings.app_name,
        "public_api_url": services.settings.public_api_url,
        "vector_store": "chroma",
        "memory_store": (
            services.settings.storage_backend
            or ("postgres" if services.settings.environment.lower() == "prod" else "sqlite")
        ),
        "documents_indexed": services.retriever.revision(),
        "openrouter_configured": bool(
            services.settings.openrouter_api_key
            and services.settings.openrouter_chat_model
            and services.settings.openrouter_embedding_model
        ),
        "gemini_fallback_configured": bool(
            services.settings.gemini_api_key and services.settings.gemini_chat_model
        ),
    }


@app.get("/metrics")
async def metrics() -> dict:
    services = container()
    documents = services.retriever.list_documents()
    return services.metrics.aggregate(
        num_documents=len(documents),
        num_chunks=sum(document.chunks for document in documents),
    )


@app.get("/metrics/prometheus")
async def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        container().metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@app.post("/v1/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
) -> QueryResponse:
    request_id = str(uuid4())
    started = time.perf_counter()
    services = container()
    try:
        response = await services.orchestrator.handle_query(request, request_id)
        services.metrics.record_query(
            response.mode_used,
            response.metrics,
            request.session_id,
        )
        services.metrics.record_http(
            "/v1/query",
            "200",
            (time.perf_counter() - started) * 1000,
        )
        return response
    except CopilotError as exc:
        services.metrics.record_http(
            "/v1/query",
            str(exc.status_code),
            (time.perf_counter() - started) * 1000,
        )
        raise


@app.post("/v1/query/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    request_id = str(uuid4())
    started = time.perf_counter()
    services = container()

    async def generator():
        yield json.dumps({"type": "meta", "request_id": request_id}) + "\n"
        token_queue: asyncio.Queue[str] = asyncio.Queue()
        streamed_any = False

        async def on_token(token: str) -> None:
            await token_queue.put(token)

        try:
            query_task = asyncio.create_task(
                services.orchestrator.handle_query(
                    request,
                    request_id,
                    on_token=on_token,
                )
            )
            while True:
                if query_task.done() and token_queue.empty():
                    break
                try:
                    token = await asyncio.wait_for(token_queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                streamed_any = True
                yield json.dumps({"type": "token", "text": token}) + "\n"

            response = await query_task
            services.metrics.record_query(
                response.mode_used,
                response.metrics,
                request.session_id,
            )
            services.metrics.record_http(
                "/v1/query/stream",
                "200",
                (time.perf_counter() - started) * 1000,
            )
            if response.error:
                yield json.dumps(
                    {
                        "type": "error",
                        "error": True,
                        "answer": response.answer,
                    }
                ) + "\n"
            elif not streamed_any:
                for token in _stream_tokens(response.answer):
                    yield json.dumps({"type": "token", "text": token}) + "\n"
            yield json.dumps(
                {
                    "type": "final",
                    "response": response.model_dump(mode="json"),
                }
            ) + "\n"
        except Exception as exc:
            services.metrics.record_http(
                "/v1/query/stream",
                "500",
                (time.perf_counter() - started) * 1000,
            )
            yield json.dumps(
                {
                    "type": "error",
                    "error": True,
                    "answer": "Temporary issue, retrying...",
                    "message": str(exc),
                }
            ) + "\n"

    return StreamingResponse(generator(), media_type="application/x-ndjson")


def _stream_tokens(answer: str) -> list[str]:
    parts = answer.split(" ")
    tokens = []
    for index, part in enumerate(parts):
        suffix = " " if index < len(parts) - 1 else ""
        tokens.append(f"{part}{suffix}")
    return tokens or [""]


@app.post("/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
) -> DocumentUploadResponse:
    started = time.perf_counter()
    services = container()
    try:
        text = await extract_text_from_upload(
            file,
            max_bytes=services.settings.max_upload_bytes,
        )
        result = await services.retriever.add_document(
            file.filename or "document",
            text,
            session_id=session_id,
        )
        services.metrics.record_http(
            "/v1/documents/upload",
            "200",
            (time.perf_counter() - started) * 1000,
        )
        return DocumentUploadResponse(
            document_id=result.document_id,
            file_name=file.filename or "document",
            chunks_indexed=result.chunks_indexed,
            chunks_skipped=result.chunks_skipped,
            status="indexed",
            suggested_queries=suggest_queries_for_document(
                file.filename or "document",
                text,
            ),
        )
    except CopilotError as exc:
        services.metrics.record_http(
            "/v1/documents/upload",
            str(exc.status_code),
            (time.perf_counter() - started) * 1000,
        )
        raise


@app.get("/v1/documents", response_model=list[DocumentRecord])
async def list_documents(
    session_id: str | None = Query(default=None),
) -> list[DocumentRecord]:
    return container().retriever.list_documents(session_id=session_id)


@app.get("/v1/sessions/{session_id}/history", response_model=HistoryResponse)
async def session_history(
    session_id: str,
) -> HistoryResponse:
    turns = container().memory.list_turns(session_id)
    return HistoryResponse(session_id=session_id, turns=turns)


@app.get("/v1/sessions/{session_id}/metrics", response_model=SessionMetricsResponse)
async def session_metrics(
    session_id: str,
) -> SessionMetricsResponse:
    return SessionMetricsResponse(**container().metrics.session_metrics(session_id))


@app.get("/v1/evaluation/dataset")
async def evaluation_dataset() -> list[dict]:
    return load_dataset()


@app.get("/v1/evaluation/report")
async def evaluation_report() -> dict:
    path = default_report_path()
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/v1/evaluation/run")
async def run_evaluation_endpoint() -> dict:
    services = container()
    dataset = load_dataset()

    async def llm_fn(question: str) -> str:
        item = next((dataset_item for dataset_item in dataset if dataset_item["question"] == question), {})
        response = await services.orchestrator.handle_query(
            QueryRequest(
                query=question,
                session_id=f"eval-{uuid4()}",
                mode=QueryMode.AUTO,
                filters=item.get("filters") or {},
            ),
            request_id=str(uuid4()),
        )
        services.metrics.record_query(
            response.mode_used,
            response.metrics,
            response.session_id,
        )
        return response

    report = await run_evaluation(dataset, llm_fn, judge_llm=services.llm)
    write_report(report)
    services.metrics.record_evaluation(float(report["avg_score"]))
    return report


@app.get("/")
async def root() -> dict:
    return {
        "message": "AI Copilot API",
        "docs": "/docs",
        "frontend": "http://127.0.0.1:5173",
        "public_api_url": container().settings.public_api_url,
    }
