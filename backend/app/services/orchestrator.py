import json
import time
from dataclasses import dataclass
from typing import Any

from app.models import QueryMode, QueryRequest, QueryResponse, ResponseMetrics, TraceStep
from app.services.cache import ResponseCache, make_cache_key
from app.services.errors import CopilotError
from app.services.extraction import (
    build_email_answer,
    chunks_with_emails,
    is_document_field_lookup,
    is_email_lookup,
)
from app.services.retrieval import chunks_to_citations


@dataclass
class RouteDecision:
    mode: QueryMode
    reason: str


class Orchestrator:
    def __init__(
        self,
        *,
        llm: Any,
        retriever: Any,
        agent: Any,
        memory: Any,
        cache: ResponseCache,
        settings: Any | None = None,
    ):
        self.llm = llm
        self.retriever = retriever
        self.agent = agent
        self.memory = memory
        self.cache = cache
        self.settings = settings

    async def handle_query(
        self,
        request: QueryRequest,
        request_id: str,
        on_token: Any | None = None,
        user_id: str | None = None,
    ) -> QueryResponse:
        started = time.perf_counter()
        route = self.route(request)
        trace: list[TraceStep] = [
            TraceStep(
                step="route",
                meta={"mode": route.mode.value, "reason": route.reason},
            )
        ]
        history = self.memory.recent_messages(request.session_id, user_id=user_id)
        retrieval_revision = (
            self.retriever.revision()
            if route.mode in {QueryMode.RAG, QueryMode.AGENT}
            else 0
        )
        cache_key = make_cache_key(
            request.session_id,
            request.query,
            request.context,
            request.mode.value,
            route.mode.value,
            retrieval_revision,
            request.filters.model_dump(mode="json"),
        )

        cached = self.cache.get(cache_key)
        if cached is not None:
            trace.append(TraceStep(step="cache_check", meta={"hit": True}))
            response = QueryResponse.model_validate(cached)
            response.trace = trace + [
                TraceStep(
                    step="cache_return",
                    meta={"cached_trace_steps": len(response.trace)},
                )
            ]
            response.metrics.cache_hit = True
            response.metrics.latency_ms = (time.perf_counter() - started) * 1000
            response.metrics.retrieval_time_ms = 0.0
            response.metrics.tokens = self._token_count({}, response.answer)
            response.metrics.total_tokens = response.metrics.tokens
            response.metrics.cost = 0.0
            response.request_id = request_id
            self._remember(request, response, request_id, user_id=user_id)
            return response
        trace.append(TraceStep(step="cache_check", meta={"hit": False}))

        retrieved_chunks = []
        retrieval_time_ms = 0.0
        usage: dict[str, Any] = {}
        agent_steps = []

        email_answer = None
        if route.mode == QueryMode.RAG and is_email_lookup(request.query):
            retrieval_started = time.perf_counter()
            try:
                email_chunks = chunks_with_emails(
                    self.retriever.all_chunks(
                        session_id=request.session_id,
                        filters=request.filters,
                        user_id=user_id,
                    )
                )
            except Exception as exc:
                return self._error_response(
                    request=request,
                    request_id=request_id,
                    started=started,
                    route=route,
                    trace=trace,
                    error=exc,
                    retrieval_time_ms=retrieval_time_ms,
                    retrieved_chunks=retrieved_chunks,
                    agent_steps=agent_steps,
                )
            elapsed = (time.perf_counter() - retrieval_started) * 1000
            retrieval_time_ms += elapsed
            trace.append(
                TraceStep(
                    step="retrieve",
                    meta={
                        "strategy": "local_email_scan",
                        "chunks": len(email_chunks),
                        "latency_ms": elapsed,
                    },
                )
            )
            email_answer = build_email_answer(email_chunks)
            if email_answer:
                retrieved_chunks = email_chunks

        if not email_answer and route.mode in {QueryMode.RAG, QueryMode.AGENT}:
            retrieval_started = time.perf_counter()
            try:
                retrieved_chunks = await self.retriever.retrieve(
                    request.query,
                    top_k=request.top_k,
                    session_id=request.session_id,
                    filters=request.filters,
                    user_id=user_id,
                )
            except Exception as exc:
                return self._error_response(
                    request=request,
                    request_id=request_id,
                    started=started,
                    route=route,
                    trace=trace,
                    error=exc,
                    retrieval_time_ms=retrieval_time_ms,
                    retrieved_chunks=retrieved_chunks,
                    agent_steps=agent_steps,
                )
            elapsed = (time.perf_counter() - retrieval_started) * 1000
            retrieval_time_ms += elapsed
            trace.append(
                TraceStep(
                    step="retrieve",
                    meta={
                        "chunks": len(retrieved_chunks),
                        "top_k": request.top_k,
                        "latency_ms": elapsed,
                    },
                )
            )

        if not email_answer and route.mode == QueryMode.RAG and is_email_lookup(request.query):
            extraction_started = time.perf_counter()
            email_chunks = chunks_with_emails(retrieved_chunks)
            email_answer = build_email_answer(email_chunks)
            trace.append(
                TraceStep(
                    step="extract_emails",
                    meta={
                        "matches": len(email_chunks),
                        "latency_ms": (time.perf_counter() - extraction_started) * 1000,
                    },
                )
            )
            if email_answer:
                retrieved_chunks = email_chunks

        if email_answer:
            answer = email_answer
            usage = {"provider": "local-extractor"}
            trace.append(
                TraceStep(
                    step="local_extract",
                    meta={"extractor": "email", "chunks": len(retrieved_chunks)},
                )
            )
        elif route.mode == QueryMode.AGENT:
            agent_started = time.perf_counter()
            try:
                agent_run = await self.agent.run(
                    query=request.query,
                    history=history,
                    context_chunks=retrieved_chunks,
                    top_k=request.top_k,
                    session_id=request.session_id,
                    filters=request.filters.model_dump(mode="json"),
                )
            except Exception as exc:
                return self._error_response(
                    request=request,
                    request_id=request_id,
                    started=started,
                    route=route,
                    trace=trace,
                    error=exc,
                    retrieval_time_ms=retrieval_time_ms,
                    retrieved_chunks=retrieved_chunks,
                    agent_steps=agent_steps,
                )
            answer = agent_run.answer
            retrieved_chunks = agent_run.retrieved_chunks
            agent_steps = agent_run.steps
            trace.extend(agent_run.trace)
            trace.append(
                TraceStep(
                    step="agent_complete",
                    meta={"latency_ms": (time.perf_counter() - agent_started) * 1000},
                )
            )
            usage = agent_run.usage
        else:
            messages = self._build_messages(
                request=request,
                history=history,
                retrieved_chunks=retrieved_chunks,
            )
            llm_started = time.perf_counter()
            try:
                if on_token is not None and hasattr(self.llm, "chat_stream"):
                    streamed_parts: list[str] = []
                    async for token in self.llm.chat_stream(messages):
                        streamed_parts.append(token)
                        await on_token(token)
                    answer = "".join(streamed_parts)
                    usage = {
                        "provider": "stream",
                        "total_tokens": self._token_count({}, answer),
                    }
                else:
                    llm_response = await self.llm.chat(messages)
                    answer = llm_response.content
                    usage = llm_response.usage
            except Exception as exc:
                return self._error_response(
                    request=request,
                    request_id=request_id,
                    started=started,
                    route=route,
                    trace=trace,
                    error=exc,
                    retrieval_time_ms=retrieval_time_ms,
                    retrieved_chunks=retrieved_chunks,
                    agent_steps=agent_steps,
                )
            trace.append(
                TraceStep(
                    step="llm",
                    meta={
                        "latency_ms": (time.perf_counter() - llm_started) * 1000,
                        "tokens": int(usage.get("total_tokens") or 0),
                        "streamed": on_token is not None,
                    },
                )
            )

        metrics = self._build_metrics(
            started,
            route,
            usage,
            answer=answer,
            retrieval_time_ms=retrieval_time_ms,
            cache_hit=False,
        )
        response = QueryResponse(
            answer=answer,
            session_id=request.session_id,
            mode_used=route.mode,
            citations=chunks_to_citations(retrieved_chunks),
            retrieved_chunks=retrieved_chunks,
            agent_steps=agent_steps,
            trace=trace,
            metrics=metrics,
            request_id=request_id,
        )
        self.cache.set(cache_key, response.model_dump(mode="json"))
        self._remember(request, response, request_id, user_id=user_id)
        return response

    def route(self, request: QueryRequest) -> RouteDecision:
        if request.mode != QueryMode.AUTO:
            return RouteDecision(mode=request.mode, reason=f"explicit_{request.mode.value}")

        query = request.query.lower()
        if is_document_field_lookup(query) and self.retriever.revision() > 0:
            return RouteDecision(mode=QueryMode.RAG, reason="indexed_document_field_lookup")
        if self._needs_agent(query):
            return RouteDecision(mode=QueryMode.AGENT, reason="multi_step_or_tool_request")
        if request.context or self._needs_retrieval(query):
            return RouteDecision(mode=QueryMode.RAG, reason="external_knowledge_request")
        return RouteDecision(mode=QueryMode.LLM, reason="direct_generation")

    @staticmethod
    def _needs_retrieval(query: str) -> bool:
        markers = [
            "document",
            "report",
            "policy",
            "uploaded",
            "file",
            "pdf",
            "according to",
            "based on",
            "knowledge base",
            "context",
            "email",
            "e-mail",
            "mail id",
            "mailid",
            "mail",
            "contact",
            "phone",
            "mobile",
            "profile",
            "resume",
            "cv",
        ]
        return any(marker in query for marker in markers)

    @staticmethod
    def _needs_agent(query: str) -> bool:
        markers = [
            "analyze",
            "extract",
            "compare",
            "calculate",
            "risk",
            "risks",
            "steps",
            "plan",
            "summarize and",
            "multi-step",
        ]
        return any(marker in query for marker in markers)

    @staticmethod
    def _build_messages(
        *,
        request: QueryRequest,
        history: list[dict[str, str]],
        retrieved_chunks: list,
    ) -> list[dict[str, str]]:
        context_parts = []
        if request.context:
            context_parts.append(f"Inline context:\n{request.context}")
        if retrieved_chunks:
            rendered_chunks = "\n\n".join(
                f"[{index}] Source: {chunk.source} chunk {chunk.chunk_index}\n{chunk.text}"
                for index, chunk in enumerate(retrieved_chunks, start=1)
            )
            context_parts.append(f"Retrieved context:\n{rendered_chunks}")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI copilot. Answer with grounded, actionable output. "
                    "When retrieved context is provided, use it as the primary source "
                    "and mention source names when relevant."
                ),
            }
        ]
        messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"User query:\n{request.query}\n\n"
                    f"{chr(10).join(context_parts) if context_parts else 'No external context was provided.'}"
                ),
            }
        )
        return messages

    def _build_metrics(
        self,
        started: float,
        route: RouteDecision,
        usage: dict[str, Any],
        *,
        answer: str,
        retrieval_time_ms: float,
        cache_hit: bool,
        error: str | None = None,
    ) -> ResponseMetrics:
        tokens = Orchestrator._token_count(usage, answer)
        provider_cost = usage.get("cost")
        cost = (
            float(provider_cost)
            if provider_cost is not None
            else (tokens / 1000) * float(getattr(self.settings, "price_per_1k_tokens", 0.0))
        )
        if cache_hit:
            cost = 0.0
        return ResponseMetrics(
            latency_ms=(time.perf_counter() - started) * 1000,
            tokens=tokens,
            retrieval_time_ms=retrieval_time_ms,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or tokens),
            cost=cost,
            provider=usage.get("provider"),
            fallback_used=bool(usage.get("fallback_used") or False),
            route_decision=route.reason,
            cache_hit=cache_hit,
            error=error,
        )

    @staticmethod
    def _token_count(usage: dict[str, Any], answer: str) -> int:
        tokens = int(
            usage.get("tokens")
            or usage.get("total_tokens")
            or (
                int(usage.get("prompt_tokens") or 0)
                + int(usage.get("completion_tokens") or 0)
            )
            or 0
        )
        if tokens > 0:
            return tokens
        return len(answer.split()) if answer else 0

    def _error_response(
        self,
        *,
        request: QueryRequest,
        request_id: str,
        started: float,
        route: RouteDecision,
        trace: list[TraceStep],
        error: Exception,
        retrieval_time_ms: float,
        retrieved_chunks: list,
        agent_steps: list,
    ) -> QueryResponse:
        error_code = (
            error.error_code
            if isinstance(error, CopilotError)
            else error.__class__.__name__.lower()
        )
        answer = "Temporary issue, retrying..."
        trace.append(
            TraceStep(
                step="error",
                meta={"error": error_code, "message": str(error)},
            )
        )
        metrics = self._build_metrics(
            started,
            route,
            {"provider": "fallback"},
            answer=answer,
            retrieval_time_ms=retrieval_time_ms,
            cache_hit=False,
            error=error_code,
        )
        response = QueryResponse(
            answer=answer,
            session_id=request.session_id,
            mode_used=route.mode,
            error=True,
            citations=chunks_to_citations(retrieved_chunks),
            retrieved_chunks=retrieved_chunks,
            agent_steps=agent_steps,
            trace=trace,
            metrics=metrics,
            request_id=request_id,
        )
        self._remember(request, response, request_id)
        return response

    def _remember(
        self,
        request: QueryRequest,
        response: QueryResponse,
        request_id: str,
        user_id: str | None = None,
    ) -> None:
        self.memory.add_turn(
            session_id=request.session_id,
            user_input=request.query,
            system_response=response.answer,
            mode_used=response.mode_used.value,
            request_id=request_id,
            metadata={
                "metrics": json.loads(response.metrics.model_dump_json()),
                "citations": [citation.model_dump() for citation in response.citations],
                "trace": [step.model_dump() for step in response.trace],
            },
        )
        # Also save to memory store with user_id for multi-tenant isolation
        self.memory.save(
            session_id=request.session_id,
            message={
                "user_input": request.query,
                "system_response": response.answer,
                "mode_used": response.mode_used.value,
                "request_id": request_id,
                "metadata": {
                    "metrics": json.loads(response.metrics.model_dump_json()),
                    "citations": [citation.model_dump() for citation in response.citations],
                    "trace": [step.model_dump() for step in response.trace],
                },
            },
            user_id=user_id,
        )
