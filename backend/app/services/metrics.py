import threading
from collections import Counter
from dataclasses import dataclass
from statistics import mean

from app.models import QueryMode, ResponseMetrics


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[index]


@dataclass
class SessionMetricTotals:
    query_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    latencies_ms: list[float] | None = None

    def record(self, metrics: ResponseMetrics) -> None:
        if self.latencies_ms is None:
            self.latencies_ms = []
        self.query_count += 1
        self.total_tokens += metrics.tokens
        self.total_cost += float(metrics.cost or 0.0)
        self.latencies_ms.append(metrics.latency_ms)


class MetricsRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.request_count: Counter[tuple[str, str]] = Counter()
        self.mode_count: Counter[str] = Counter()
        self.error_count: Counter[str] = Counter()
        self.total_tokens = 0
        self.total_cost = 0.0
        self.http_latencies_ms: list[float] = []
        self.query_latencies_ms: list[float] = []
        self.retrieval_latencies_ms: list[float] = []
        self.cache_hits = 0
        self.query_count = 0
        self.latest_accuracy: float | None = None
        self.session_totals: dict[str, SessionMetricTotals] = {}

    def record_http(self, endpoint: str, status: str, latency_ms: float) -> None:
        with self._lock:
            self.request_count[(endpoint, status)] += 1
            self.http_latencies_ms.append(latency_ms)

    def record_query(
        self,
        mode: QueryMode,
        metrics: ResponseMetrics,
        session_id: str | None = None,
    ) -> None:
        with self._lock:
            self.mode_count[mode.value] += 1
            self.query_count += 1
            self.query_latencies_ms.append(metrics.latency_ms)
            self.retrieval_latencies_ms.append(metrics.retrieval_time_ms)
            self.total_tokens += metrics.tokens
            if metrics.cache_hit:
                self.cache_hits += 1
            if metrics.cost is not None:
                self.total_cost += metrics.cost
            if metrics.error:
                self.error_count[metrics.error] += 1
            if session_id:
                self.session_totals.setdefault(
                    session_id,
                    SessionMetricTotals(),
                ).record(metrics)

    def record_evaluation(self, avg_score: float) -> None:
        with self._lock:
            self.latest_accuracy = avg_score

    def aggregate(
        self,
        *,
        num_documents: int = 0,
        num_chunks: int = 0,
    ) -> dict[str, float | int | None | dict[str, float | int | None]]:
        with self._lock:
            avg_latency = mean(self.query_latencies_ms) if self.query_latencies_ms else 0.0
            avg_retrieval = (
                mean(self.retrieval_latencies_ms)
                if self.retrieval_latencies_ms
                else 0.0
            )
            cache_hit_rate = self.cache_hits / self.query_count if self.query_count else 0.0
            error_total = sum(self.error_count.values())
            payload = {
                "avg_latency": avg_latency,
                "p95_latency": _percentile(self.query_latencies_ms, 0.95),
                "cache_hit_rate": cache_hit_rate,
                "avg_retrieval_time_ms": avg_retrieval,
                "total_requests": self.query_count,
                "total_tokens": self.total_tokens,
                "total_cost": self.total_cost,
                "sessions_tracked": len(self.session_totals),
                "error_rate": error_total / self.query_count if self.query_count else 0.0,
                "scale": {
                    "documents": num_documents,
                    "chunks": num_chunks,
                    "avg_latency_ms": avg_latency,
                    "accuracy": self.latest_accuracy,
                },
            }
        return payload

    def session_metrics(self, session_id: str) -> dict[str, float | int | str]:
        with self._lock:
            totals = self.session_totals.get(session_id, SessionMetricTotals())
            latencies = totals.latencies_ms or []
            return {
                "session_id": session_id,
                "query_count": totals.query_count,
                "total_tokens": totals.total_tokens,
                "total_cost": totals.total_cost,
                "avg_latency_ms": mean(latencies) if latencies else 0.0,
            }

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP copilot_http_requests_total Total HTTP requests.",
                "# TYPE copilot_http_requests_total counter",
            ]
            for (endpoint, status), count in sorted(self.request_count.items()):
                lines.append(
                    f'copilot_http_requests_total{{endpoint="{endpoint}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP copilot_query_mode_total Total queries by selected mode.",
                    "# TYPE copilot_query_mode_total counter",
                ]
            )
            for mode, count in sorted(self.mode_count.items()):
                lines.append(f'copilot_query_mode_total{{mode="{mode}"}} {count}')

            lines.extend(
                [
                    "# HELP copilot_query_tokens_total Total tokens reported by provider.",
                    "# TYPE copilot_query_tokens_total counter",
                    f"copilot_query_tokens_total {self.total_tokens}",
                    "# HELP copilot_query_cost_total Total cost reported by provider.",
                    "# TYPE copilot_query_cost_total counter",
                    f"copilot_query_cost_total {self.total_cost}",
                    "# HELP copilot_query_latency_ms_avg Average HTTP latency in milliseconds.",
                    "# TYPE copilot_query_latency_ms_avg gauge",
                    f"copilot_query_latency_ms_avg {mean(self.query_latencies_ms) if self.query_latencies_ms else 0}",
                    "# HELP copilot_cache_hit_rate Query response cache hit rate.",
                    "# TYPE copilot_cache_hit_rate gauge",
                    f"copilot_cache_hit_rate {self.cache_hits / self.query_count if self.query_count else 0}",
                ]
            )

            for error, count in sorted(self.error_count.items()):
                lines.append(f'copilot_errors_total{{error="{error}"}} {count}')

        return "\n".join(lines) + "\n"
