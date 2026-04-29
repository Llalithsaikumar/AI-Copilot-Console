import inspect
import json
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.evaluation.metrics import build_report
from app.evaluation.rag_eval import retrieval_score


DatasetItem = dict[str, Any]
LLMFunction = Callable[[str], str | Awaitable[str]]


class Evaluator:
    def keyword_score(self, answer: str, expected: list[str]) -> float:
        if not expected:
            return 1.0
        answer_lower = answer.lower()
        hits = sum(1 for keyword in expected if keyword.lower() in answer_lower)
        return hits / len(expected)

    def length_score(self, answer: str, max_len: int) -> float:
        if max_len <= 0:
            return 0.0
        return min(len(answer.split()) / max_len, 1.0)

    def evaluate(self, question: str, answer: str, spec: DatasetItem) -> float:
        if spec["type"] == "keyword":
            return self.keyword_score(answer, spec["expected_keywords"])
        if spec["type"] == "summary":
            return self.length_score(answer, spec["max_length"])
        raise ValueError(f"Unsupported evaluation type for {question!r}: {spec['type']}")


def default_dataset_path() -> Path:
    return Path(__file__).with_name("dataset.json")


def default_report_path() -> Path:
    return Path(__file__).with_name("report.json")


def load_dataset(path: Path | None = None) -> list[DatasetItem]:
    dataset_path = path or default_dataset_path()
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _extract_score(text: str) -> float:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and "score" in payload:
            return max(0.0, min(float(payload["score"]), 1.0))
        if isinstance(payload, int | float):
            return max(0.0, min(float(payload), 1.0))
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    match = re.search(r"\b(?:0(?:\.\d+)?|1(?:\.0+)?)\b", text)
    if not match:
        return 0.0
    return max(0.0, min(float(match.group(0)), 1.0))


async def llm_judge(answer: str, reference: str, llm: Any) -> float:
    prompt = (
        "Score this answer from 0-1 based on correctness. "
        "Return only JSON like {\"score\": 0.75}.\n\n"
        f"Answer: {answer}\n"
        f"Reference: {reference}"
    )
    try:
        response = await llm.chat([{"role": "user", "content": prompt}])
    except Exception:
        return 0.0
    return _extract_score(response.content)


async def run_evaluation(
    dataset: list[DatasetItem],
    llm_fn: LLMFunction,
    *,
    judge_llm: Any | None = None,
) -> dict[str, Any]:
    evaluator = Evaluator()
    results: list[dict[str, Any]] = []

    for item in dataset:
        output_or_awaitable = llm_fn(item["question"])
        output = (
            await output_or_awaitable
            if inspect.isawaitable(output_or_awaitable)
            else output_or_awaitable
        )
        answer = getattr(output, "answer", output)
        retrieved_chunks = getattr(output, "retrieved_chunks", [])
        retrieved_ids = [
            getattr(chunk, "id", str(chunk))
            for chunk in retrieved_chunks
        ]

        keyword_score = None
        base_score = None
        if item["type"] in {"keyword", "summary"}:
            base_score = evaluator.evaluate(item["question"], str(answer), item)
            if item["type"] == "keyword":
                keyword_score = base_score

        rag_score = None
        if "expected_chunks" in item:
            rag_score = retrieval_score(retrieved_ids, item["expected_chunks"])

        judge_score = None
        if judge_llm is not None and item.get("reference"):
            judge_score = await llm_judge(str(answer), str(item["reference"]), judge_llm)

        scores = [
            score
            for score in [base_score, rag_score, judge_score]
            if score is not None
        ]
        score = sum(scores) / len(scores) if scores else 0.0
        results.append(
            {
                "id": item["id"],
                "score": score,
                "keyword_score": keyword_score,
                "retrieval_score": rag_score,
                "llm_score": judge_score,
                "type": item["type"],
                "answer": str(answer),
                "retrieved_chunks": retrieved_ids,
            }
        )

    return build_report(results)


def write_report(report: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    report_path = path or default_report_path()
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
