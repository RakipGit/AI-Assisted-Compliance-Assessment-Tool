"""Tests for the OpenAI LLM provider adapter."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.llm_provider import (
    DEFAULT_OPENAI_MODEL,
    LLMProviderError,
    call_openai,
)


class FakeResponsesAPI:
    """Fake OpenAI Responses resource."""

    def __init__(
        self,
        *,
        response: Any | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.response = response
        self.exception = exception
        self.last_request: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.last_request = kwargs

        if self.exception is not None:
            raise self.exception

        return self.response


class FakeOpenAIClient:
    """Minimal OpenAI-compatible fake client."""

    def __init__(
        self,
        *,
        response: Any | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.responses = FakeResponsesAPI(
            response=response,
            exception=exception,
        )


def test_call_openai_returns_output_text() -> None:
    client = FakeOpenAIClient(
        response=SimpleNamespace(
            output_text="Generated explanation."
        )
    )

    result = call_openai(
        "Assessment prompt.",
        api_key="test-key",
        client=client,
    )

    assert result == "Generated explanation."


def test_call_openai_sends_expected_request() -> None:
    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="Result.")
    )

    call_openai(
        "  Assessment prompt.  ",
        api_key="test-key",
        model="test-model",
        max_output_tokens=800,
        client=client,
    )

    request = client.responses.last_request

    assert request is not None
    assert request["model"] == "test-model"
    assert request["input"] == "Assessment prompt."
    assert request["reasoning"] == {"effort": "low"}
    assert request["max_output_tokens"] == 800


def test_default_model_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="Result.")
    )

    call_openai(
        "Assessment prompt.",
        api_key="test-key",
        client=client,
    )

    assert client.responses.last_request is not None
    assert (
        client.responses.last_request["model"]
        == DEFAULT_OPENAI_MODEL
    )


def test_environment_model_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OPENAI_MODEL",
        "environment-test-model",
    )

    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="Result.")
    )

    call_openai(
        "Assessment prompt.",
        api_key="test-key",
        client=client,
    )

    assert client.responses.last_request is not None
    assert (
        client.responses.last_request["model"]
        == "environment-test-model"
    )


def test_empty_prompt_is_rejected() -> None:
    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="Result.")
    )

    with pytest.raises(
        LLMProviderError,
        match="prompt must be non-empty",
    ):
        call_openai(
            "   ",
            api_key="test-key",
            client=client,
        )


def test_provider_exception_is_wrapped() -> None:
    client = FakeOpenAIClient(
        exception=RuntimeError("Network failure")
    )

    with pytest.raises(
        LLMProviderError,
        match="OpenAI API request failed",
    ):
        call_openai(
            "Assessment prompt.",
            api_key="test-key",
            client=client,
        )


def test_empty_output_is_rejected() -> None:
    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="   ")
    )

    with pytest.raises(
        LLMProviderError,
        match="did not contain usable text",
    ):
        call_openai(
            "Assessment prompt.",
            api_key="test-key",
            client=client,
        )


@pytest.mark.parametrize(
    "invalid_value",
    [0, -1, True, 1.5],
)
def test_invalid_max_output_tokens_is_rejected(
    invalid_value: Any,
) -> None:
    client = FakeOpenAIClient(
        response=SimpleNamespace(output_text="Result.")
    )

    with pytest.raises(
        LLMProviderError,
        match="must be a positive integer",
    ):
        call_openai(
            "Assessment prompt.",
            api_key="test-key",
            max_output_tokens=invalid_value,
            client=client,
        )