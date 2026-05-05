import asyncio
from types import SimpleNamespace

import pytest

from app.services.errors import ProviderError
from app.services.llm_provider import (
    GeminiClient,
    LLMResponse,
    OpenRouterClient,
    ProviderFallbackClient,
)


def openrouter_settings(**overrides):
    defaults = {
        "openrouter_api_key": "test-key",
        "openrouter_chat_model": "primary-model",
        "openrouter_chat_fallback_models": None,
        "openrouter_embedding_model": "embedding-model",
        "openrouter_base_url": "https://openrouter.test/api/v1",
        "openrouter_http_referer": "http://localhost:5173",
        "openrouter_app_title": "Test App",
        "request_timeout_seconds": 1,
        "llm_temperature": 0.2,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def gemini_settings(**overrides):
    defaults = {
        "gemini_api_key": "test-key",
        "gemini_chat_model": "gemini-chat",
        "gemini_embedding_model": "text-embedding-004",
        "gemini_base_url": "https://gemini.test/v1beta",
        "request_timeout_seconds": 1,
        "llm_temperature": 0.2,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class RecordingOpenRouter(OpenRouterClient):
    def __init__(self, settings, failing_models=None):
        super().__init__(settings)
        self.failing_models = set(failing_models or [])
        self.models_seen = []

    async def _post_json(self, path, payload):
        model = payload["model"]
        self.models_seen.append(model)
        if model in self.failing_models:
            raise ProviderError(f"{model} failed")
        return {
            "choices": [{"message": {"content": "openrouter answer"}}],
            "usage": {"total_tokens": 3},
            "model": model,
        }


class RecordingGemini(GeminiClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.paths_seen = []
        self.payloads_seen = []

    async def _post_json(self, path, payload):
        self.paths_seen.append(path)
        self.payloads_seen.append(payload)
        return {
            "embeddings": [
                {"values": [1.0, 0.0]},
                {"values": [0.0, 1.0]},
            ]
        }


class FailingPrimary:
    embedding_model_name = "primary-embedding"

    async def chat(self, messages):
        raise ProviderError("primary failed")

    async def chat_stream(self, messages):
        if False:
            yield ""
        raise ProviderError("primary stream failed")

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class FailingEmbeddingPrimary(FailingPrimary):
    async def embed(self, texts):
        raise ProviderError("primary embedding failed")


class PartiallyFailingPrimary(FailingPrimary):
    async def chat_stream(self, messages):
        yield "partial "
        raise ProviderError("primary stream failed after tokens")


class WorkingFallback:
    is_configured = True
    is_embedding_configured = True
    embedding_model_name = "fallback-embedding"

    async def chat(self, messages):
        return LLMResponse(content="fallback answer", usage={"provider": "gemini"})

    async def chat_stream(self, messages):
        yield "fallback "
        yield "answer"

    async def embed(self, texts):
        return [[0.0, 1.0] for _ in texts]


class UnconfiguredFallback:
    is_configured = False
    is_embedding_configured = False

    async def chat(self, messages):
        raise AssertionError("fallback should not be called")

    async def embed(self, texts):
        raise AssertionError("fallback should not be called")


def test_provider_fallback_uses_gemini_for_chat_failures():
    client = ProviderFallbackClient(FailingPrimary(), WorkingFallback())

    response = asyncio.run(client.chat([{"role": "user", "content": "hello"}]))

    assert response.content == "fallback answer"
    assert response.usage["provider"] == "gemini"
    assert response.usage["fallback_used"] is True


def test_provider_fallback_streams_gemini_when_openrouter_fails_before_tokens():
    client = ProviderFallbackClient(FailingPrimary(), WorkingFallback())

    tokens = asyncio.run(_collect_stream(client.chat_stream([{"role": "user", "content": "hello"}])))

    assert tokens == ["fallback ", "answer"]


def test_provider_fallback_does_not_mix_partial_primary_stream_with_gemini():
    client = ProviderFallbackClient(PartiallyFailingPrimary(), WorkingFallback())

    with pytest.raises(ProviderError):
        asyncio.run(_collect_stream(client.chat_stream([{"role": "user", "content": "hello"}])))


def test_provider_fallback_does_not_fallback_embeddings():
    client = ProviderFallbackClient(FailingPrimary(), WorkingFallback())

    embeddings = asyncio.run(client.embed(["hello"]))

    assert embeddings == [[1.0, 0.0]]
    assert client.embedding_model_name == "primary-embedding"


def test_provider_fallback_uses_gemini_for_embedding_failures():
    client = ProviderFallbackClient(FailingEmbeddingPrimary(), WorkingFallback())

    embeddings = asyncio.run(client.embed(["hello", "world"]))

    assert embeddings == [[0.0, 1.0], [0.0, 1.0]]


def test_provider_fallback_raises_embedding_error_without_gemini_embeddings():
    client = ProviderFallbackClient(FailingEmbeddingPrimary(), UnconfiguredFallback())

    with pytest.raises(ProviderError, match="primary embedding failed"):
        asyncio.run(client.embed(["hello"]))


def test_gemini_embeddings_use_batch_endpoint():
    client = RecordingGemini(gemini_settings())

    embeddings = asyncio.run(client.embed(["hello", "world"]))

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert client.paths_seen == ["/models/text-embedding-004:batchEmbedContents"]
    assert client.payloads_seen[0]["requests"][0]["model"] == "models/text-embedding-004"
    assert client.payloads_seen[0]["requests"][0]["content"]["parts"][0]["text"] == "hello"


def test_provider_fallback_raises_when_fallback_is_unconfigured():
    client = ProviderFallbackClient(FailingPrimary(), UnconfiguredFallback())

    with pytest.raises(ProviderError):
        asyncio.run(client.chat([{"role": "user", "content": "hello"}]))


def test_openrouter_chat_tries_configured_fallback_model():
    client = RecordingOpenRouter(
        openrouter_settings(
            openrouter_chat_model="bad-model",
            openrouter_chat_fallback_models="good-model,other-model",
        ),
        failing_models={"bad-model"},
    )

    response = asyncio.run(client.chat([{"role": "user", "content": "hello"}]))

    assert response.content == "openrouter answer"
    assert response.usage["model"] == "good-model"
    assert response.usage["openrouter_fallback_used"] is True
    assert response.usage["openrouter_model_attempts"] == 2
    assert client.models_seen == ["bad-model", "good-model"]


def test_openrouter_chat_candidates_include_default_free_models():
    client = OpenRouterClient(
        openrouter_settings(
            openrouter_chat_model="primary-model",
            openrouter_chat_fallback_models="tencent/hy3-preview:free",
        )
    )

    assert client.chat_model_candidates[0] == "primary-model"
    assert client.chat_model_candidates.count("tencent/hy3-preview:free") == 1
    assert "google/gemma-3-27b-it:free" in client.chat_model_candidates


def test_provider_fallback_uses_gemini_after_all_openrouter_models_fail():
    primary = RecordingOpenRouter(
        openrouter_settings(
            openrouter_chat_model="bad-model",
            openrouter_chat_fallback_models="also-bad",
        )
    )
    primary.failing_models = set(primary.chat_model_candidates)
    client = ProviderFallbackClient(primary, WorkingFallback())

    response = asyncio.run(client.chat([{"role": "user", "content": "hello"}]))

    assert response.content == "fallback answer"
    assert response.usage["provider"] == "gemini"
    assert response.usage["fallback_used"] is True
    assert "All OpenRouter chat models failed" in response.usage["primary_error"]


async def _collect_stream(stream):
    return [token async for token in stream]
