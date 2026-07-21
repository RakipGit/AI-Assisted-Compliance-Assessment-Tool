"""AI-assisted explanation layer for deterministic assessment results.

This module does not evaluate security controls and does not calculate
coverage scores. It receives immutable deterministic results and may use
an external text-generation function only to explain those results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .models import ControlResult
from .scoring import ScoreSummary


TextGenerator = Callable[[str], str]


class AISummaryError(ValueError):
    """Raised when an AI-assisted summary cannot be generated safely."""


class AIIntegrityError(RuntimeError):
    """Raised if deterministic results change during summary generation."""


@dataclass(frozen=True)
class AISummary:
    """
    Immutable textual summary of a deterministic assessment.

    Attributes:
        text:
            Generated explanatory text.

        source:
            Source of the text, such as "ai" or "deterministic-fallback".

        model_name:
            Optional provider/model label used only for reporting.

        disclaimer:
            Scope limitation attached to every generated summary.
    """

    text: str
    source: str
    model_name: str | None
    disclaimer: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("AI summary text must not be empty.")

        if self.source not in {"ai", "deterministic-fallback"}:
            raise ValueError(
                "Summary source must be either 'ai' or "
                "'deterministic-fallback'."
            )

        if self.model_name is not None and not self.model_name.strip():
            raise ValueError(
                "Model name must be None or a non-empty string."
            )

        if not self.disclaimer.strip():
            raise ValueError("AI summary disclaimer must not be empty.")


SUMMARY_DISCLAIMER = (
    "This explanation is based on deterministic prototype results and "
    "self-reported input. It does not constitute ISO/IEC 27001 "
    "certification, NIS2 legal compliance confirmation, audit assurance "
    "or legal advice."
)


def _result_fingerprint(
    results: Sequence[ControlResult],
) -> tuple[tuple[Any, ...], ...]:
    """
    Create a stable snapshot of deterministic assessment results.

    The snapshot is captured before and after text generation. Any detected
    difference raises AIIntegrityError.
    """
    return tuple(
        (
            result.control_id,
            result.control_name,
            result.status,
            result.rationale,
            result.recommendations,
            result.evidence,
            result.mappings,
            result.metadata,
            result.numeric_score,
            result.is_assessable,
        )
        for result in results
    )


def _validate_results(
    results: tuple[ControlResult, ...] | list[ControlResult],
) -> tuple[ControlResult, ...]:
    """Validate and normalize deterministic assessment results."""
    normalized_results = tuple(results)

    if not normalized_results:
        raise AISummaryError(
            "At least one ControlResult is required to generate a summary."
        )

    if not all(
        isinstance(result, ControlResult)
        for result in normalized_results
    ):
        raise AISummaryError(
            "Every summary input must be a ControlResult instance."
        )

    control_ids = [result.control_id for result in normalized_results]

    duplicate_ids = sorted({
        control_id
        for control_id in control_ids
        if control_ids.count(control_id) > 1
    })

    if duplicate_ids:
        raise AISummaryError(
            "Duplicate control results were provided: "
            + ", ".join(duplicate_ids)
        )

    return normalized_results


def _format_coverage(score: ScoreSummary) -> str:
    """Return a safe textual representation of the coverage result."""
    if score.coverage_percentage is None:
        return "Not calculable"

    return f"{score.coverage_percentage:.2f}%"


def _format_mapping_references(result: ControlResult) -> str:
    """Return framework mappings as concise references."""
    if not result.mappings:
        return "No mappings available"

    return ", ".join(
        f"{mapping.framework} {mapping.reference}"
        for mapping in result.mappings
    )


def build_ai_prompt(
    *,
    organization: dict[str, Any],
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
) -> str:
    """
    Build a constrained prompt from deterministic assessment results.

    The prompt instructs the language model to explain existing outcomes
    without modifying, recalculating or contradicting them.
    """
    normalized_results = _validate_results(results)

    organization_data = organization.get("organization", organization)

    if not isinstance(organization_data, dict):
        raise AISummaryError(
            "Organization metadata must be provided as an object."
        )

    organization_name = organization_data.get(
        "name",
        "Unnamed organization",
    )
    organization_size = organization_data.get("size", "Not specified")
    employees = organization_data.get("employees", "Not specified")
    sector = organization_data.get("sector", "Not specified")

    result_sections: list[str] = []

    for result in normalized_results:
        recommendations = (
            "\n".join(
                f"    - {recommendation}"
                for recommendation in result.recommendations
            )
            if result.recommendations
            else "    - No additional recommendation generated."
        )

        evidence = (
            "\n".join(
                f"    - {observation}"
                for observation in result.evidence
            )
            if result.evidence
            else "    - No evidence observation available."
        )

        result_sections.append(
            "\n".join(
                (
                    f"Control ID: {result.control_id}",
                    f"Control name: {result.control_name}",
                    f"Fixed status: {result.status.value}",
                    f"Fixed numeric score: {result.numeric_score}",
                    f"Deterministic rationale: {result.rationale}",
                    (
                        "Framework references: "
                        f"{_format_mapping_references(result)}"
                    ),
                    "Deterministic recommendations:",
                    recommendations,
                    "Evidence observations:",
                    evidence,
                )
            )
        )

    controls_text = "\n\n---\n\n".join(result_sections)

    return f"""
You are producing an executive explanation of a preliminary cybersecurity
self-assessment for a small or medium-sized organization.

NON-NEGOTIABLE CONSTRAINTS:

1. Do not change, reinterpret or recalculate any control status.
2. Do not change or recalculate the coverage percentage.
3. Do not claim full ISO/IEC 27001 compliance.
4. Do not claim NIS2 legal compliance.
5. Do not describe the result as certification or audit assurance.
6. Do not invent evidence, policies, technologies, incidents or controls.
7. Treat every listed status, score and rationale as fixed input.
8. Clearly distinguish confirmed weaknesses from unavailable information.
9. Mention that Not Assessable means insufficient information, not failure.
10. Produce plain text only.

ORGANIZATION:

Name: {organization_name}
Employee-based size category: {organization_size}
Employees: {employees}
Sector: {sector}

FIXED SCORE SUMMARY:

Selected-controls coverage: {_format_coverage(score)}
Earned score: {score.earned_score}
Maximum score: {score.maximum_score}
Assessable controls: {score.assessable_controls}
Not Assessable controls: {score.not_assessable_controls}

FIXED CONTROL RESULTS:

{controls_text}

REQUIRED OUTPUT STRUCTURE:

Executive Summary
- Briefly describe the overall assessment.

Key Strengths
- Summarize controls marked Satisfied.
- Do not invent strengths when none exist.

Priority Improvement Areas
- Summarize Partially Satisfied and Not Satisfied controls.
- Preserve the relative seriousness of the fixed statuses.

Information Gaps
- Identify controls marked Not Assessable.
- Explain that further information is needed.

Recommended Next Steps
- Prioritize only recommendations supported by the deterministic results.

Scope Limitation
- State that this is a preliminary assessment of four selected controls.
- State that it is not certification, audit assurance or legal advice.
""".strip()


def generate_deterministic_fallback(
    *,
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
) -> str:
    """
    Generate a non-AI summary when no external text generator is configured.

    This keeps the application functional without changing deterministic
    assessment outcomes.
    """
    normalized_results = _validate_results(results)

    strengths = [
        result.control_name
        for result in normalized_results
        if result.status.value == "Satisfied"
    ]

    improvement_areas = [
        result.control_name
        for result in normalized_results
        if result.status.value in {
            "Partially Satisfied",
            "Not Satisfied",
        }
    ]

    information_gaps = [
        result.control_name
        for result in normalized_results
        if result.status.value == "Not Assessable"
    ]

    recommendations = [
        recommendation
        for result in normalized_results
        for recommendation in result.recommendations
        if result.status.value != "Satisfied"
    ]

    unique_recommendations = tuple(dict.fromkeys(recommendations))

    lines = [
        "Executive Summary",
        (
            "The preliminary assessment produced selected-controls coverage "
            f"of {_format_coverage(score)} based on "
            f"{score.assessable_controls} assessable control(s)."
        ),
        "",
        "Key Strengths",
    ]

    if strengths:
        lines.extend(f"- {control_name}" for control_name in strengths)
    else:
        lines.append("- No selected control was fully satisfied.")

    lines.extend(("", "Priority Improvement Areas"))

    if improvement_areas:
        lines.extend(
            f"- {control_name}"
            for control_name in improvement_areas
        )
    else:
        lines.append("- No assessable improvement area was identified.")

    lines.extend(("", "Information Gaps"))

    if information_gaps:
        lines.extend(
            f"- {control_name}: additional information is required."
            for control_name in information_gaps
        )
    else:
        lines.append("- No selected control was marked Not Assessable.")

    lines.extend(("", "Recommended Next Steps"))

    if unique_recommendations:
        lines.extend(
            f"- {recommendation}"
            for recommendation in unique_recommendations
        )
    else:
        lines.append(
            "- Continue monitoring and periodically reassess the controls."
        )

    lines.extend(
        (
            "",
            "Scope Limitation",
            f"- {SUMMARY_DISCLAIMER}",
        )
    )

    return "\n".join(lines)


def generate_summary(
    *,
    organization: dict[str, Any],
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
    text_generator: TextGenerator | None = None,
    model_name: str | None = None,
) -> AISummary:
    """
    Generate an AI-assisted or deterministic fallback summary.

    The external generator receives only a text prompt. It does not receive
    mutable ControlResult or ScoreSummary objects.

    Raises:
        AISummaryError:
            If the generated output is missing or invalid.

        AIIntegrityError:
            If deterministic results change during generation.
    """
    normalized_results = _validate_results(results)
    before_fingerprint = _result_fingerprint(normalized_results)

    if text_generator is None:
        generated_text = generate_deterministic_fallback(
            results=normalized_results,
            score=score,
        )
        source = "deterministic-fallback"
        effective_model_name = None
    else:
        prompt = build_ai_prompt(
            organization=organization,
            results=normalized_results,
            score=score,
        )

        try:
            generated_text = text_generator(prompt)
        except Exception as exc:
            raise AISummaryError(
                f"Text generation failed: {exc}"
            ) from exc

        source = "ai"
        effective_model_name = model_name

    if not isinstance(generated_text, str):
        raise AISummaryError(
            "The text generator must return a string."
        )

    if not generated_text.strip():
        raise AISummaryError(
            "The text generator returned an empty summary."
        )

    after_fingerprint = _result_fingerprint(normalized_results)

    if before_fingerprint != after_fingerprint:
        raise AIIntegrityError(
            "Deterministic assessment results changed during "
            "summary generation."
        )

    return AISummary(
        text=generated_text.strip(),
        source=source,
        model_name=effective_model_name,
        disclaimer=SUMMARY_DISCLAIMER,
    )