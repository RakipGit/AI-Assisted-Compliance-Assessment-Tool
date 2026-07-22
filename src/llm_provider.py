"""OpenAI LLM provider adapter for assessment explanations."""

from __future__ import annotations

import os
from typing import Any


DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_MAX_OUTPUT_TOKENS = 4000
DEFAULT_TIMEOUT_SECONDS = 30.0


class LLMProviderError(RuntimeError):
    """Raised when the external LLM provider cannot return valid text."""


def get_openai_model(explicit_model: str | None = None) -> str:
    """Return the configured OpenAI model identifier."""
    model = (
        explicit_model
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_OPENAI_MODEL
    )

    if not isinstance(model, str) or not model.strip():
        raise LLMProviderError(
            "The OpenAI model identifier is invalid."
        )

    return model.strip()


def _get_api_key(explicit_api_key: str | None = None) -> str:
    """Return the configured OpenAI API key."""
    api_key = explicit_api_key or os.getenv("OPENAI_API_KEY")

    if not isinstance(api_key, str) or not api_key.strip():
        raise LLMProviderError(
            "OPENAI_API_KEY is not configured."
        )

    return api_key.strip()


def _extract_output_text(response: Any) -> str:
    """Extract and validate plain text from an OpenAI response."""
    output_text = getattr(response, "output_text", None)

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    response_status = getattr(response, "status", None)
    incomplete_details = getattr(
        response,
        "incomplete_details",
        None,
    )

    details: list[str] = []

    if response_status:
        details.append(f"status={response_status}")

    if incomplete_details is not None:
        details.append(
            f"incomplete_details={incomplete_details}"
        )

    details_text = (
        " " + ", ".join(details)
        if details
        else ""
    )

    raise LLMProviderError(
        "The OpenAI response did not contain usable text."
        f"{details_text}"
    )


def call_openai(
    prompt: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: Any | None = None,
) -> str:
    """
    Send an explanatory prompt through the OpenAI Responses API.

    The function accepts only plain text and returns only plain text.
    It has no access to ControlResult or ScoreSummary objects.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise LLMProviderError(
            "The LLM prompt must be non-empty text."
        )

    if (
        isinstance(max_output_tokens, bool)
        or not isinstance(max_output_tokens, int)
        or max_output_tokens <= 0
    ):
        raise LLMProviderError(
            "max_output_tokens must be a positive integer."
        )

    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        raise LLMProviderError(
            "timeout_seconds must be a positive number."
        )

    resolved_model = get_openai_model(model)

    if client is None:
        resolved_api_key = _get_api_key(api_key)

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMProviderError(
                "The openai Python package is not installed."
            ) from exc

        try:
            client = OpenAI(
                api_key=resolved_api_key,
                timeout=float(timeout_seconds),
                max_retries=1,
            )
        except Exception as exc:
            raise LLMProviderError(
                "The OpenAI client could not be initialized."
            ) from exc

    try:
        response = client.responses.create(
            model=resolved_model,
            input=prompt.strip(),
            reasoning={
                "effort": "low",
            },
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        raise LLMProviderError(
            "The OpenAI API request failed."
        ) from exc

    return _extract_output_text(response)