import ast
import operator
import re
import time
from dataclasses import dataclass
from typing import Any

from app.models import AgentStep, RetrievedChunk, TraceStep


TOOLS = {
    "retrieval": "retrieval",
    "calculator": "calculator",
    "db": "db",
    "summarize_context": "summarize_context",
    "extract_risks": "extract_risks",
}


@dataclass
class AgentRun:
    answer: str
    steps: list[AgentStep]
    trace: list[TraceStep]
    retrieved_chunks: list[RetrievedChunk]
    usage: dict[str, Any]


class SafeCalculator:
    _operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(self, expression: str) -> float:
        tree = ast.parse(expression, mode="eval")
        return float(self._eval(tree.body))

    def _eval(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self._operators:
            return self._operators[type(node.op)](
                self._eval(node.left),
                self._eval(node.right),
            )
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._operators:
            return self._operators[type(node.op)](self._eval(node.operand))
        raise ValueError("Only arithmetic expressions are supported.")


class AgentPlanner:
    def plan(self, query: str, has_context: bool) -> list[dict[str, str]]:
        lowered = query.lower()
        steps: list[dict[str, str]] = []

        if not has_context:
            steps.append({"tool": "retrieval", "input": query})
        if any(word in lowered for word in ["summarize", "summary", "analyze"]):
            steps.append({"tool": "summarize_context", "input": query})
        if any(word in lowered for word in ["risk", "risks", "blocker", "issue"]):
            steps.append({"tool": "extract_risks", "input": query})

        expression = self._extract_math_expression(query)
        if expression:
            steps.append({"tool": "calculator", "input": expression})

        if not steps:
            steps.append({"tool": "summarize_context", "input": query})
        return steps

    @staticmethod
    def _extract_math_expression(query: str) -> str | None:
        match = re.search(r"([-+*/().\d\s]{3,})", query)
        if not match:
            return None
        expression = match.group(1).strip()
        if any(operator_token in expression for operator_token in ["+", "-", "*", "/"]):
            return expression
        return None


class AgentPipeline:
    def __init__(self, llm: Any, retriever: Any):
        self.llm = llm
        self.retriever = retriever
        self.planner = AgentPlanner()
        self.calculator = SafeCalculator()
        self.tools = TOOLS.copy()

    async def run(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        context_chunks: list[RetrievedChunk],
        top_k: int,
        user_id: str,
        session_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> AgentRun:
        steps: list[AgentStep] = []
        chunks = list(context_chunks)
        plan = self.planner.plan(query, has_context=bool(chunks))
        trace: list[TraceStep] = [
            TraceStep(
                step="plan",
                meta={"steps": [item["tool"] for item in plan]},
            )
        ]

        for index, planned in enumerate(plan, start=1):
            started = time.perf_counter()
            tool = planned["tool"]
            tool_input = planned["input"]
            status = "ok"
            try:
                output = await self._execute(
                    tool,
                    tool_input,
                    chunks,
                    top_k,
                    user_id,
                    session_id,
                    filters,
                )
                if tool == "retrieval" and isinstance(output, list):
                    chunks = output
                    rendered_output = f"Retrieved {len(output)} chunks."
                else:
                    rendered_output = str(output)
            except Exception as exc:
                status = "error"
                rendered_output = str(exc)

            steps.append(
                AgentStep(
                    step_id=f"step-{index}",
                    tool=tool,
                    input=tool_input,
                    output=rendered_output,
                    status=status,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            )
            trace.append(
                TraceStep(
                    step=self._trace_step_name(tool),
                    meta={
                        "status": status,
                        "latency_ms": steps[-1].latency_ms,
                        "chunks": len(chunks),
                    },
                )
            )

        synthesis_started = time.perf_counter()
        messages = self._build_synthesis_messages(query, history, chunks, steps)
        response = await self.llm.chat(messages)
        trace.append(
            TraceStep(
                step="synthesize",
                meta={
                    "latency_ms": (time.perf_counter() - synthesis_started) * 1000,
                    "tokens": int(response.usage.get("total_tokens") or 0),
                },
            )
        )
        return AgentRun(
            answer=response.content,
            steps=steps,
            trace=trace,
            retrieved_chunks=chunks,
            usage=response.usage,
        )

    async def _execute(
        self,
        tool: str,
        tool_input: str,
        chunks: list[RetrievedChunk],
        top_k: int,
        user_id: str,
        session_id: str | None,
        filters: dict[str, Any] | None,
    ) -> str | list[RetrievedChunk]:
        if tool == "retrieval":
            return await self.retriever.retrieve(
                tool_input,
                top_k=top_k,
                user_id=user_id,
                session_id=session_id,
                filters=filters,
            )
        if tool == "calculator":
            return str(self.calculator.evaluate(tool_input))
        if tool == "extract_risks":
            return self._extract_risks(chunks)
        if tool == "summarize_context":
            return self._summarize_context(chunks)
        if tool == "db":
            return "No database tool is configured for this agent run."
        raise ValueError(f"Unknown agent tool: {tool}")

    @staticmethod
    def _trace_step_name(tool: str) -> str:
        if tool == "retrieval":
            return "retrieve"
        if tool == "summarize_context":
            return "summarize"
        return tool

    @staticmethod
    def _summarize_context(chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "No retrieved context was available."
        text = " ".join(chunk.text for chunk in chunks)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        summary = " ".join(sentence.strip() for sentence in sentences[:4] if sentence.strip())
        return summary[:1200] or "No summary could be produced."

    @staticmethod
    def _extract_risks(chunks: list[RetrievedChunk]) -> str:
        if not chunks:
            return "No context was available for risk extraction."
        risk_terms = ("risk", "issue", "blocker", "concern", "failure", "delay", "cost")
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(chunk.text for chunk in chunks))
        matches = [
            sentence.strip()
            for sentence in sentences
            if any(term in sentence.lower() for term in risk_terms)
        ]
        if not matches:
            return "No explicit risk language found in the retrieved context."
        return "\n".join(f"- {match}" for match in matches[:8])

    @staticmethod
    def _build_synthesis_messages(
        query: str,
        history: list[dict[str, str]],
        chunks: list[RetrievedChunk],
        steps: list[AgentStep],
    ) -> list[dict[str, str]]:
        context = "\n\n".join(
            f"[{index}] Source: {chunk.source} chunk {chunk.chunk_index}\n{chunk.text}"
            for index, chunk in enumerate(chunks, start=1)
        )
        step_text = "\n".join(
            f"{step.step_id} {step.tool} ({step.status}): {step.output}"
            for step in steps
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI copilot agent. Use the provided context and "
                    "tool results to produce a concise, grounded final answer. "
                    "Call out uncertainty when context is weak."
                ),
            }
        ]
        messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": (
                    f"User query:\n{query}\n\n"
                    f"Retrieved context:\n{context or 'No retrieved context.'}\n\n"
                    f"Agent tool results:\n{step_text}"
                ),
            }
        )
        return messages
