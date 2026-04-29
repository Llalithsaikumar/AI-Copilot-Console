import asyncio

import pytest

from app.services.errors import ProviderError
from app.services.llm_provider import LLMResponse, ProviderFallbackClient


class FailingPrimary:
    embedding_model_name = "primary-embedding"

    async def chat(self, messages):
        raise ProviderError("primary failed")

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class WorkingFallback:
    is_configured = True

    async def chat(self, messages):
        return LLMResponse(content="fallback answer", usage={"provider": "gemini"})


class UnconfiguredFallback:
    is_configured = False

    async def chat(self, messages):
        raise AssertionError("fallback should not be called")


def test_provider_fallback_uses_gemini_for_chat_failures():
    client = ProviderFallbackClient(FailingPrimary(), WorkingFallback())

    response = asyncio.run(client.chat([{"role": "user", "content": "hello"}]))

    assert response.content == "fallback answer"
    assert response.usage["provider"] == "gemini"
    assert response.usage["fallback_used"] is True


def test_provider_fallback_does_not_fallback_embeddings():
    client = ProviderFallbackClient(FailingPrimary(), WorkingFallback())

    embeddings = asyncio.run(client.embed(["hello"]))

    assert embeddings == [[1.0, 0.0]]
    assert client.embedding_model_name == "primary-embedding"


def test_provider_fallback_raises_when_fallback_is_unconfigured():
    client = ProviderFallbackClient(FailingPrimary(), UnconfiguredFallback())

    with pytest.raises(ProviderError):
        asyncio.run(client.chat([{"role": "user", "content": "hello"}]))
