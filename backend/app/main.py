import asyncio
import json
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse

from app.config import Settings, get_settings
from app.db import SessionLocal
from app.evaluation.evaluator import (
    default_report_path,
    load_dataset,
    run_evaluation,
    write_report,
)
from app.models import (
    AuthCredentials,
    AuthResponse,
    DocumentRecord,
    DocumentUploadResponse,
    HistoryResponse,
    QueryMode,
    QueryRequest,
    QueryResponse,
    SessionCreateResponse,
    SessionMetricsResponse,
    UserResponse,
)
from app.services.agent import AgentPipeline
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    lookup_user_by_email,
    lookup_user_by_id,
    register_user,
    verify_password,
)
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
    memory = build_memory_store(SessionLocal)
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


app = FastAPI(
    title="AI Copilot System",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.container = build_container()


def container() -> ServiceContainer:
    return app.state.container


def _set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path=settings.auth_cookie_path,
        max_age=settings.access_token_exp_hours * 3600,
    )


def _clear_auth_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path=settings.auth_cookie_path,
    )


def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = decode_access_token(token, settings)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = lookup_user_by_id(settings, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user_id


@app.exception_handler(CopilotError)
async def copilot_error_handler(_, exc: CopilotError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message},
    )


@app.post("/auth/register", response_model=UserResponse)
def register(
    credentials: AuthCredentials,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    try:
        user = register_user(settings, credentials.email, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    token = create_access_token(user["_id"], settings)
    _set_auth_cookie(response, token, settings)
    return UserResponse(user_id=user["_id"], email=user["email"])


@app.post("/auth/login", response_model=AuthResponse)
def login(
    credentials: AuthCredentials,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    user = lookup_user_by_email(settings, credentials.email)
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user["_id"], settings)
    _set_auth_cookie(response, token, settings)
    return AuthResponse(user_id=user["_id"], access_token=token)


@app.post("/auth/logout")
def logout(response: Response) -> dict:
    _clear_auth_cookie(response, get_settings())
    return {"status": "ok"}


@app.get("/auth/me", response_model=UserResponse)
def me(
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> UserResponse:
    user = lookup_user_by_id(settings, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(user_id=user["_id"], email=user["email"])


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
        "documents_indexed": 0,
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
async def metrics(user_id: str = Depends(get_current_user)) -> dict:
    services = container()
    documents = services.retriever.list_documents(user_id=user_id)
    return services.metrics.aggregate_for_user(
        user_id,
        num_documents=len(documents),
        num_chunks=sum(document.chunks for document in documents),
    )


@app.get("/metrics/prometheus")
async def prometheus_metrics(user_id: str = Depends(get_current_user)) -> PlainTextResponse:
    return PlainTextResponse(
        container().metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@app.post("/v1/sessions", response_model=SessionCreateResponse)
async def create_session(user_id: str = Depends(get_current_user)) -> SessionCreateResponse:
    session_id = container().memory.create_session(user_id)
    return SessionCreateResponse(session_id=session_id)


@app.post("/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest, user_id: str = Depends(get_current_user)) -> QueryResponse:
    request_id = str(uuid4())
    started = time.perf_counter()
    services = container()
    try:
        try:
            services.memory.ensure_session(user_id, request.session_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Session not found")
        response = await services.orchestrator.handle_query(request, request_id, user_id)
        services.metrics.record_query(
            response.mode_used,
            response.metrics,
            request.session_id,
            user_id,
        )
        services.metrics.record_http(
            "/v1/query",
            "200",
            (time.perf_counter() - started) * 1000,
            user_id,
        )
        return response
    except CopilotError as exc:
        services.metrics.record_http(
            "/v1/query",
            str(exc.status_code),
            (time.perf_counter() - started) * 1000,
            user_id,
        )
        raise


@app.post("/v1/query/stream")
async def query_stream(
    request: QueryRequest,
    user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    request_id = str(uuid4())
    started = time.perf_counter()
    services = container()

    try:
        services.memory.ensure_session(user_id, request.session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

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
                    user_id,
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
                user_id,
            )
            services.metrics.record_http(
                "/v1/query/stream",
                "200",
                (time.perf_counter() - started) * 1000,
                user_id,
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
                user_id,
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
    user_id: str = Depends(get_current_user),
) -> DocumentUploadResponse:
    started = time.perf_counter()
    services = container()
    try:
        if session_id:
            try:
                services.memory.ensure_session(user_id, session_id)
            except ValueError:
                raise HTTPException(status_code=404, detail="Session not found")
        text = await extract_text_from_upload(
            file,
            max_bytes=services.settings.max_upload_bytes,
        )
        result = await services.retriever.add_document(
            file.filename or "document",
            text,
            user_id=user_id,
            session_id=session_id,
        )
        services.metrics.record_http(
            "/v1/documents/upload",
            "200",
            (time.perf_counter() - started) * 1000,
            user_id,
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
            user_id,
        )
        raise


@app.get("/v1/documents", response_model=list[DocumentRecord])
async def list_documents(
    session_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> list[DocumentRecord]:
    return container().retriever.list_documents(user_id=user_id, session_id=session_id)


@app.get("/v1/sessions/{session_id}/history", response_model=HistoryResponse)
async def session_history(
    session_id: str,
    user_id: str = Depends(get_current_user),
) -> HistoryResponse:
    try:
        container().memory.ensure_session(user_id, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    turns = container().memory.list_turns(user_id, session_id)
    return HistoryResponse(session_id=session_id, turns=turns)


@app.get("/v1/sessions/{session_id}/metrics", response_model=SessionMetricsResponse)
async def session_metrics(
    session_id: str,
    user_id: str = Depends(get_current_user),
) -> SessionMetricsResponse:
    try:
        container().memory.ensure_session(user_id, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionMetricsResponse(
        **container().metrics.session_metrics(user_id, session_id)
    )


@app.get("/v1/evaluation/dataset")
async def evaluation_dataset(user_id: str = Depends(get_current_user)) -> list[dict]:
    return load_dataset()


@app.get("/v1/evaluation/report")
async def evaluation_report(user_id: str = Depends(get_current_user)) -> dict:
    path = default_report_path()
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/v1/evaluation/run")
async def run_evaluation_endpoint(user_id: str = Depends(get_current_user)) -> dict:
    services = container()
    dataset = load_dataset()

    async def llm_fn(question: str) -> str:
        item = next((dataset_item for dataset_item in dataset if dataset_item["question"] == question), {})
        session_id = services.memory.create_session(user_id)
        response = await services.orchestrator.handle_query(
            QueryRequest(
                query=question,
                session_id=session_id,
                mode=QueryMode.AUTO,
                filters=item.get("filters") or {},
            ),
            request_id=str(uuid4()),
            user_id=user_id,
        )
        services.metrics.record_query(
            response.mode_used,
            response.metrics,
            response.session_id,
            user_id,
        )
        return response

    report = await run_evaluation(dataset, llm_fn, judge_llm=services.llm)
    write_report(report)
    services.metrics.record_evaluation(float(report["avg_score"]), user_id)
    return report


@app.get("/")
async def root(user_id: str = Depends(get_current_user)) -> dict:
    return {
        "message": "AI Copilot API",
        "docs": "disabled",
        "frontend": "http://127.0.0.1:5173",
        "public_api_url": container().settings.public_api_url,
    }
