"""Tests for the AI-assisted explanation layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.ai_summary import (
    AISummaryError,
    SUMMARY_DISCLAIMER,
    build_ai_prompt,
    generate_summary,
)
from src.models import ControlStatus
from src.rule_engine import evaluate_organization
from src.scoring import calculate_score
from src.validator import load_json_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture
def mixed_assessment() -> tuple[
    dict[str, Any],
    tuple,
    object,
]:
    """Return one realistic mixed assessment and its score."""
    organization = load_json_file(
        DATA_DIR / "scenario_mixed.json"
    )
    results = evaluate_organization(organization)
    score = calculate_score(results)

    return organization, results, score


def test_ai_summary_does_not_modify_control_statuses(
    mixed_assessment: tuple,
) -> None:
    """AI text generation must not change deterministic statuses."""
    organization, results, score = mixed_assessment

    statuses_before = tuple(
        (result.control_id, result.status)
        for result in results
    )

    def fake_generator(prompt: str) -> str:
        assert isinstance(prompt, str)
        return (
            "Executive Summary\n"
            "The fixed assessment results were explained without changes."
        )

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=fake_generator,
        model_name="mock-model",
    )

    statuses_after = tuple(
        (result.control_id, result.status)
        for result in results
    )

    assert statuses_after == statuses_before
    assert summary.source == "ai"
    assert summary.model_name == "mock-model"
    assert summary.fallback_reason is None


def test_ai_summary_does_not_modify_numeric_scores(
    mixed_assessment: tuple,
) -> None:
    """Numeric scores must remain deterministic and unchanged."""
    organization, results, score = mixed_assessment

    scores_before = tuple(
        result.numeric_score
        for result in results
    )
    coverage_before = score.coverage_percentage

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=lambda prompt: "Generated explanation.",
    )

    scores_after = tuple(
        result.numeric_score
        for result in results
    )

    assert scores_after == scores_before
    assert score.coverage_percentage == coverage_before
    assert summary.text == "Generated explanation."
    assert summary.source == "ai"


def test_generator_receives_text_prompt_not_result_objects(
    mixed_assessment: tuple,
) -> None:
    """The provider adapter must receive only the serialized prompt."""
    organization, results, score = mixed_assessment
    received_arguments: list[object] = []

    def recording_generator(prompt: str) -> str:
        received_arguments.append(prompt)
        return "Safe generated summary."

    generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=recording_generator,
    )

    assert len(received_arguments) == 1
    assert isinstance(received_arguments[0], str)
    assert not any(
        argument is result
        for argument in received_arguments
        for result in results
    )


def test_prompt_contains_fixed_statuses_and_constraints(
    mixed_assessment: tuple,
) -> None:
    """The prompt must preserve deterministic outcomes and limitations."""
    organization, results, score = mixed_assessment

    prompt = build_ai_prompt(
        organization=organization,
        results=results,
        score=score,
    )

    assert (
        "Do not change, reinterpret or recalculate any control status"
        in prompt
    )
    assert (
        "Do not change or recalculate the coverage percentage"
        in prompt
    )
    assert "Selected-controls coverage: 62.50%" in prompt

    assert "Fixed status: Satisfied" in prompt
    assert "Fixed status: Partially Satisfied" in prompt
    assert "Fixed status: Not Satisfied" in prompt

    assert "Article 21(2)(j)" in prompt
    assert "A.8.5" in prompt


def test_prompt_distinguishes_not_assessable_from_failure() -> None:
    """The prompt must explicitly define missing information correctly."""
    organization = load_json_file(
        DATA_DIR / "scenario_missing_data.json"
    )
    results = evaluate_organization(organization)
    score = calculate_score(results)

    prompt = build_ai_prompt(
        organization=organization,
        results=results,
        score=score,
    )

    assert (
        "Not Assessable means insufficient information, not failure"
        in prompt
    )
    assert "Selected-controls coverage: 50.00%" in prompt
    assert "Not Assessable controls: 2" in prompt


def test_deterministic_fallback_works_without_ai_provider(
    mixed_assessment: tuple,
) -> None:
    """The application must remain functional without an AI API."""
    organization, results, score = mixed_assessment

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
    )

    assert summary.source == "deterministic-fallback"
    assert summary.model_name is None
    assert summary.fallback_reason is None
    assert "Executive Summary" in summary.text
    assert "Priority Improvement Areas" in summary.text
    assert (
        "Incident Response Planning and Preparedness"
        in summary.text
    )
    assert summary.disclaimer == SUMMARY_DISCLAIMER


def test_empty_ai_output_is_rejected(
    mixed_assessment: tuple,
) -> None:
    """An empty provider response must not be accepted in strict mode."""
    organization, results, score = mixed_assessment

    with pytest.raises(
        AISummaryError,
        match="returned an empty summary",
    ):
        generate_summary(
            organization=organization,
            results=results,
            score=score,
            text_generator=lambda prompt: "   ",
        )


def test_non_string_ai_output_is_rejected(
    mixed_assessment: tuple,
) -> None:
    """Provider adapters must return textual output in strict mode."""
    organization, results, score = mixed_assessment

    with pytest.raises(
        AISummaryError,
        match="must return a string",
    ):
        generate_summary(
            organization=organization,
            results=results,
            score=score,
            text_generator=lambda prompt: {
                "summary": "Invalid provider contract"
            },
        )


def test_provider_exception_is_wrapped(
    mixed_assessment: tuple,
) -> None:
    """Provider failures must become controlled errors in strict mode."""
    organization, results, score = mixed_assessment

    def failing_generator(prompt: str) -> str:
        raise RuntimeError("Provider unavailable")

    with pytest.raises(
        AISummaryError,
        match="Text generation failed: Provider unavailable",
    ):
        generate_summary(
            organization=organization,
            results=results,
            score=score,
            text_generator=failing_generator,
        )


def test_not_assessable_status_remains_unchanged_after_summary() -> None:
    """Missing-data statuses must remain unchanged after AI processing."""
    organization = load_json_file(
        DATA_DIR / "scenario_missing_data.json"
    )
    results = evaluate_organization(organization)
    score = calculate_score(results)

    before = {
        result.control_id: result.status
        for result in results
    }

    generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=lambda prompt: (
            "The assessment contains information gaps."
        ),
    )

    after = {
        result.control_id: result.status
        for result in results
    }

    assert before == after
    assert after["mfa"] is ControlStatus.NOT_ASSESSABLE
    assert (
        after["patch_management"]
        is ControlStatus.NOT_ASSESSABLE
    )


def test_provider_failure_uses_fallback_when_enabled(
    mixed_assessment: tuple,
) -> None:
    """Provider failure must not terminate an assessment when enabled."""
    organization, results, score = mixed_assessment

    statuses_before = tuple(
        (result.control_id, result.status)
        for result in results
    )
    scores_before = tuple(
        result.numeric_score
        for result in results
    )
    coverage_before = score.coverage_percentage

    def failing_generator(prompt: str) -> str:
        raise RuntimeError("Provider unavailable")

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=failing_generator,
        model_name="test-model",
        fallback_on_error=True,
    )

    statuses_after = tuple(
        (result.control_id, result.status)
        for result in results
    )
    scores_after = tuple(
        result.numeric_score
        for result in results
    )

    assert summary.source == "deterministic-fallback"
    assert summary.model_name is None
    assert summary.fallback_reason == "Provider unavailable"
    assert "Executive Summary" in summary.text

    assert statuses_after == statuses_before
    assert scores_after == scores_before
    assert score.coverage_percentage == coverage_before


def test_empty_provider_output_uses_fallback_when_enabled(
    mixed_assessment: tuple,
) -> None:
    """Empty provider output must trigger deterministic fallback."""
    organization, results, score = mixed_assessment

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=lambda prompt: "   ",
        model_name="test-model",
        fallback_on_error=True,
    )

    assert summary.source == "deterministic-fallback"
    assert summary.model_name is None
    assert (
        summary.fallback_reason
        == "The text generator returned an empty summary."
    )
    assert "Executive Summary" in summary.text


def test_non_string_provider_output_uses_fallback_when_enabled(
    mixed_assessment: tuple,
) -> None:
    """Invalid provider output must trigger deterministic fallback."""
    organization, results, score = mixed_assessment

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=lambda prompt: {"invalid": True},
        model_name="test-model",
        fallback_on_error=True,
    )

    assert summary.source == "deterministic-fallback"
    assert summary.model_name is None
    assert (
        summary.fallback_reason
        == "The text generator must return a string."
    )
    assert "Executive Summary" in summary.text


def test_successful_provider_has_no_fallback_reason(
    mixed_assessment: tuple,
) -> None:
    """Successful AI generation must not be marked as fallback."""
    organization, results, score = mixed_assessment

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=lambda prompt: "Generated explanation.",
        model_name="test-model",
        fallback_on_error=True,
    )

    assert summary.source == "ai"
    assert summary.model_name == "test-model"
    assert summary.fallback_reason is None
    assert summary.text == "Generated explanation."


def test_fallback_preserves_not_assessable_statuses() -> None:
    """Provider fallback must preserve missing-information results."""
    organization = load_json_file(
        DATA_DIR / "scenario_missing_data.json"
    )
    results = evaluate_organization(organization)
    score = calculate_score(results)

    statuses_before = {
        result.control_id: result.status
        for result in results
    }

    def failing_generator(prompt: str) -> str:
        raise RuntimeError("Simulated timeout")

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
        text_generator=failing_generator,
        model_name="test-model",
        fallback_on_error=True,
    )

    statuses_after = {
        result.control_id: result.status
        for result in results
    }

    assert summary.source == "deterministic-fallback"
    assert summary.fallback_reason == "Simulated timeout"
    assert statuses_after == statuses_before
    assert statuses_after["mfa"] is ControlStatus.NOT_ASSESSABLE
    assert (
        statuses_after["patch_management"]
        is ControlStatus.NOT_ASSESSABLE
    )