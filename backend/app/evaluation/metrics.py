from typing import Any


def average_score(
    results: list[dict[str, Any]],
    field: str = "score",
) -> float:
    scored = [
        float(item[field])
        for item in results
        if item.get(field) is not None
    ]
    if not scored:
        return 0.0
    return sum(scored) / len(scored)


def build_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_score": average_score(results),
        "avg_keyword_score": average_score(results, "keyword_score"),
        "avg_retrieval_score": average_score(results, "retrieval_score"),
        "avg_llm_score": average_score(results, "llm_score"),
        "total_cases": len(results),
        "results": results,
    }
