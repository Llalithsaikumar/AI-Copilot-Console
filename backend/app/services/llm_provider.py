import asyncio
import json
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings
from app.services.errors import ProviderConfigurationError, ProviderError


DEFAULT_OPENROUTER_CHAT_FALLBACK_MODELS = (
    "tencent/hy3-preview:free",
    "google/gemma-4-31b-it:free",
    "minimax/minimax-m2.5:free",
    "z-ai/glm-4.5-air:free",
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
)


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class OpenRouterClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.openrouter_base_url.rstrip("/")

    @property
    def embedding_model_name(self) -> str:
        return self.settings.openrouter_embedding_model or "unconfigured"

    @property
    def chat_model_candidates(self) -> list[str]:
        configured_fallbacks = self._split_model_list(
            getattr(self.settings, "openrouter_chat_fallback_models", None)
        )
        return self._dedupe_models(
            [
                self.settings.openrouter_chat_model,
                *configured_fallbacks,
                *DEFAULT_OPENROUTER_CHAT_FALLBACK_MODELS,
            ]
        )

    @staticmethod
    def _split_model_list(raw: str | None) -> list[str]:
        if not raw:
            return []
        return [
            model.strip()
            for model in raw.replace("\n", ",").split(",")
            if model.strip()
        ]

    @staticmethod
    def _dedupe_models(models: list[str | None]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for model in models:
            if not model:
                continue
            key = model.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(model)
        return result

    def _headers(self) -> dict[str, str]:
        if not self.settings.openrouter_api_key:
            raise ProviderConfigurationError(
                "OPENROUTER_API_KEY is required before calling OpenRouter."
            )
        return {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_http_referer,
            "X-OpenRouter-Title": self.settings.openrouter_app_title,
        }

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        transient_statuses = {429, 500, 502, 503, 504, 529}
        last_error: str | None = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds
                ) as client:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
                if response.status_code < 400:
                    return response.json()

                last_error = response.text
                if response.status_code not in transient_statuses or attempt == 2:
                    raise ProviderError(
                        f"OpenRouter returned {response.status_code}: {response.text}"
                    )
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt == 2:
                    raise ProviderError(f"OpenRouter request failed: {exc}") from exc

            await asyncio.sleep(0.5 * (2**attempt))

        raise ProviderError(last_error or "OpenRouter request failed.")

    async def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        models = self.chat_model_candidates
        if not models:
            raise ProviderConfigurationError(
                "OPENROUTER_CHAT_MODEL or OPENROUTER_CHAT_FALLBACK_MODELS is required before chat generation."
            )

        errors: list[str] = []
        for attempt_index, model in enumerate(models):
            try:
                response = await self._chat_with_model(messages, model)
            except ProviderError as exc:
                errors.append(f"{model}: {exc}")
                continue

            response.usage["openrouter_model_attempts"] = attempt_index + 1
            response.usage["openrouter_fallback_used"] = attempt_index > 0
            if errors:
                response.usage["openrouter_previous_errors"] = errors
            return response

        raise ProviderError(
            "All OpenRouter chat models failed. "
            f"Last errors: {' | '.join(errors[-3:])}"
        )

    async def _chat_with_model(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> LLMResponse:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
        }
        data = await self._post_json("/chat/completions", payload)
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("OpenRouter returned no completion choices.")

        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        usage = data.get("usage") or {}
        usage["provider"] = "openrouter"
        usage["model"] = data.get("model") or model
        return LLMResponse(content=content, usage=usage, raw=data)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        models = self.chat_model_candidates
        if not models:
            raise ProviderConfigurationError(
                "OPENROUTER_CHAT_MODEL or OPENROUTER_CHAT_FALLBACK_MODELS is required before chat generation."
            )

        errors: list[str] = []
        for model in models:
            streamed_any = False
            try:
                async for token in self._chat_stream_with_model(messages, model):
                    streamed_any = True
                    yield token
                return
            except ProviderError as exc:
                if streamed_any:
                    raise
                errors.append(f"{model}: {exc}")
                continue

        raise ProviderError(
            "All OpenRouter streaming chat models failed. "
            f"Last errors: {' | '.join(errors[-3:])}"
        )

    async def _chat_stream_with_model(
        self,
        messages: list[dict[str, str]],
        model: str,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "stream": True,
        }
        transient_statuses = {429, 500, 502, 503, 504, 529}
        last_error: str | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    ) as response:
                        if response.status_code >= 400:
                            last_error = await response.aread()
                            if (
                                response.status_code not in transient_statuses
                                or attempt == 2
                            ):
                                raise ProviderError(
                                    f"OpenRouter returned {response.status_code}: {last_error}"
                                )
                            continue

                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            payload_text = line.removeprefix("data:").strip()
                            if payload_text == "[DONE]":
                                return
                            try:
                                event = json.loads(payload_text)
                            except json.JSONDecodeError:
                                continue
                            choices = event.get("choices") or []
                            if not choices:
                                continue
                            delta = choices[0].get("delta") or {}
                            token = delta.get("content") or ""
                            if token:
                                yield token
                        return
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt == 2:
                    raise ProviderError(f"OpenRouter stream failed: {exc}") from exc

            await asyncio.sleep(0.5 * (2**attempt))

        raise ProviderError(str(last_error or "OpenRouter stream failed."))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.openrouter_embedding_model:
            raise ProviderConfigurationError(
                "OPENROUTER_EMBEDDING_MODEL is required before embedding text."
            )

        payload = {
            "model": self.settings.openrouter_embedding_model,
            "input": texts,
        }
        data = await self._post_json("/embeddings", payload)
        items = data.get("data") or []
        embeddings = [item.get("embedding") for item in items]
        if len(embeddings) != len(texts) or any(item is None for item in embeddings):
            raise ProviderError("OpenRouter returned an invalid embeddings response.")
        return embeddings


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.gemini_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.gemini_api_key and self.settings.gemini_chat_model)

    @property
    def is_embedding_configured(self) -> bool:
        return bool(self.settings.gemini_api_key and self.settings.gemini_embedding_model)

    @property
    def embedding_model_name(self) -> str:
        return self.settings.gemini_embedding_model or "unconfigured"

    def _headers(self) -> dict[str, str]:
        if not self.settings.gemini_api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is required before calling Gemini."
            )
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.gemini_api_key,
        }

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        transient_statuses = {429, 500, 502, 503, 504}
        last_error: str | None = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=self.settings.request_timeout_seconds
                ) as client:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
                if response.status_code < 400:
                    return response.json()

                last_error = response.text
                if response.status_code not in transient_statuses or attempt == 2:
                    raise ProviderError(
                        f"Gemini returned {response.status_code}: {response.text}"
                    )
            except httpx.HTTPError as exc:
                last_error = str(exc)
                if attempt == 2:
                    raise ProviderError(f"Gemini request failed: {exc}") from exc

            await asyncio.sleep(0.5 * (2**attempt))

        raise ProviderError(last_error or "Gemini request failed.")

    async def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        if not self.settings.gemini_chat_model:
            raise ProviderConfigurationError(
                "GEMINI_CHAT_MODEL is required before Gemini chat generation."
            )

        payload = self._to_gemini_payload(messages)
        data = await self._post_json(
            f"/models/{self.settings.gemini_chat_model}:generateContent",
            payload,
        )
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderError("Gemini returned no completion candidates.")

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )
        content = "".join(part.get("text", "") for part in parts).strip()
        usage_metadata = data.get("usageMetadata") or {}
        usage = {
            "prompt_tokens": int(usage_metadata.get("promptTokenCount") or 0),
            "completion_tokens": int(
                usage_metadata.get("candidatesTokenCount") or 0
            ),
            "total_tokens": int(usage_metadata.get("totalTokenCount") or 0),
            "provider": "gemini",
            "model": self.settings.gemini_chat_model,
        }
        return LLMResponse(content=content, usage=usage, raw=data)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        response = await self.chat(messages)
        words = response.content.split(" ")
        for index, word in enumerate(words):
            suffix = " " if index < len(words) - 1 else ""
            yield f"{word}{suffix}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.gemini_embedding_model:
            raise ProviderConfigurationError(
                "GEMINI_EMBEDDING_MODEL is required before Gemini embedding."
            )

        model = self.settings.gemini_embedding_model
        model_path = model if model.startswith("models/") else f"models/{model}"
        payload = {
            "requests": [
                {
                    "model": model_path,
                    "content": {"parts": [{"text": text}]},
                }
                for text in texts
            ]
        }
        data = await self._post_json(f"/{model_path}:batchEmbedContents", payload)
        items = data.get("embeddings") or []
        embeddings = [item.get("values") for item in items]
        if len(embeddings) != len(texts) or any(item is None for item in embeddings):
            raise ProviderError("Gemini returned an invalid embeddings response.")
        return embeddings

    def _to_gemini_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        system_parts: list[dict[str, str]] = []
        contents: list[dict[str, Any]] = []

        for message in messages:
            role = message.get("role", "user")
            text = message.get("content", "")
            if role == "system":
                system_parts.append({"text": text})
                continue
            contents.append(
                {
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": text}],
                }
            )

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.settings.llm_temperature,
            },
        }
        if system_parts:
            payload["system_instruction"] = {"parts": system_parts}
        return payload


class ProviderFallbackClient:
    def __init__(self, primary: OpenRouterClient, fallback: GeminiClient):
        self.primary = primary
        self.fallback = fallback

    @property
    def embedding_model_name(self) -> str:
        if self.primary.embedding_model_name != "unconfigured":
            return self.primary.embedding_model_name
        return f"gemini:{self.fallback.embedding_model_name}"

    async def chat(self, messages: list[dict[str, str]]) -> LLMResponse:
        try:
            return await self.primary.chat(messages)
        except (ProviderConfigurationError, ProviderError) as primary_error:
            if not self.fallback.is_configured:
                raise
            response = await self.fallback.chat(messages)
            response.usage["fallback_used"] = True
            response.usage["primary_error"] = str(primary_error)
            return response

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        streamed_any = False
        try:
            async for token in self.primary.chat_stream(messages):
                streamed_any = True
                yield token
        except (ProviderConfigurationError, ProviderError):
            if streamed_any:
                raise
            if not self.fallback.is_configured:
                raise
            async for token in self.fallback.chat_stream(messages):
                yield token

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self.primary.embed(texts)
        except (ProviderConfigurationError, ProviderError) as primary_error:
            if not self.fallback.is_embedding_configured:
                raise
            try:
                return await self.fallback.embed(texts)
            except ProviderError as fallback_error:
                raise ProviderError(
                    "Both OpenRouter and Gemini embedding providers failed. "
                    f"OpenRouter: {primary_error}; Gemini: {fallback_error}"
                ) from fallback_error
