import asyncio

from app.evaluation.evaluator import Evaluator, llm_judge, run_evaluation
from app.evaluation.rag_eval import retrieval_score
from app.services.llm_provider import LLMResponse


class FakeJudge:
    def __init__(self, content):
        self.content = content

    async def chat(self, messages):
        return LLMResponse(content=self.content)


def test_keyword_score_counts_expected_hits_case_insensitively():
    evaluator = Evaluator()

    score = evaluator.keyword_score(
        "The document mentions FINANCIAL exposure.",
        ["financial", "compliance"],
    )

    assert score == 0.5


def test_run_evaluation_returns_aggregate_report():
    async def llm_fn(question):
        if "risks" in question.lower():
            return "Financial and compliance risks are present."
        return "Short summary."

    report = asyncio.run(
        run_evaluation(
            [
                {
                    "id": "q1",
                    "question": "What are the risks mentioned?",
                    "expected_keywords": ["financial", "compliance"],
                    "type": "keyword",
                },
                {
                    "id": "q2",
                    "question": "Summarize the document",
                    "max_length": 4,
                    "type": "summary",
                },
            ],
            llm_fn,
        )
    )

    assert report["total_cases"] == 2
    assert report["avg_score"] == 0.75


def test_retrieval_score_handles_overlap_and_empty_expectations():
    assert retrieval_score(["a", "b"], ["b", "c"]) == 0.5
    assert retrieval_score(["a"], []) == 1.0


def test_llm_judge_parses_numeric_json_score():
    score = asyncio.run(
        llm_judge(
            "Financial risk is present.",
            "The reference says financial risk is present.",
            FakeJudge('{"score": 0.8}'),
        )
    )

    assert score == 0.8


def test_llm_judge_invalid_output_is_zero():
    score = asyncio.run(llm_judge("answer", "reference", FakeJudge("not a score")))

    assert score == 0.0
