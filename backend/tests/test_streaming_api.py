import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.auth import get_account_id
from app.main import app
from app.models import QueryMode, QueryResponse, ResponseMetrics


class FakeMetrics:
    def record_query(self, mode, metrics, session_id=None):
        self.query_recorded = True

    def record_http(self, endpoint, status, latency_ms):
        self.http_recorded = (endpoint, status)


class FakeOrchestrator:
    async def handle_query(self, request, request_id, on_token=None, account_id=None):
        return QueryResponse(
            answer="streamed answer",
            session_id=request.session_id,
            mode_used=QueryMode.RAG,
            metrics=ResponseMetrics(
                latency_ms=1,
                tokens=2,
                route_decision="explicit_rag",
            ),
            request_id=request_id,
        )


def test_streaming_endpoint_emits_meta_tokens_and_final(monkeypatch):
    previous = app.state.container
    fake_container = SimpleNamespace(
        orchestrator=FakeOrchestrator(),
        metrics=FakeMetrics(),
    )
    app.state.container = fake_container
    app.dependency_overrides[get_account_id] = lambda: "user"
    try:
        client = TestClient(app)
        response = client.post(
            "/v1/query/stream",
            json={"query": "hello", "session_id": "user:s1", "mode": "rag"},
        )
    finally:
        app.state.container = previous
        app.dependency_overrides.pop(get_account_id, None)

    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    assert events[0]["type"] == "meta"
    assert [event["type"] for event in events[1:-1]] == ["token", "token"]
    assert events[-1]["type"] == "final"
    assert events[-1]["response"]["answer"] == "streamed answer"
