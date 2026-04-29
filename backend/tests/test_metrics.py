from app.models import QueryMode, ResponseMetrics
from app.services.metrics import MetricsRecorder


def test_metrics_aggregate_reports_latency_and_cache_rate():
    recorder = MetricsRecorder()
    recorder.record_query(
        QueryMode.RAG,
        ResponseMetrics(
            latency_ms=100,
            tokens=20,
            retrieval_time_ms=30,
            cost=0.01,
            route_decision="explicit_rag",
            cache_hit=False,
        ),
        session_id="session-1",
        user_id="user-1",
    )
    recorder.record_query(
        QueryMode.RAG,
        ResponseMetrics(
            latency_ms=200,
            tokens=0,
            retrieval_time_ms=0,
            cost=0,
            route_decision="explicit_rag",
            cache_hit=True,
        ),
        session_id="session-1",
        user_id="user-1",
    )

    aggregate = recorder.aggregate(num_documents=2, num_chunks=7)

    assert aggregate["avg_latency"] == 150
    assert aggregate["cache_hit_rate"] == 0.5
    assert aggregate["total_cost"] == 0.01
    assert aggregate["scale"]["documents"] == 2
    assert aggregate["scale"]["chunks"] == 7

    session = recorder.session_metrics("user-1", "session-1")
    assert session["query_count"] == 2
    assert session["total_tokens"] == 20
    assert session["total_cost"] == 0.01
