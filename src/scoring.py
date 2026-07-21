"""Coverage scoring for deterministic security-control results."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ControlResult, ControlStatus


class ScoringError(ValueError):
    """Raised when control results cannot be scored safely."""


@dataclass(frozen=True)
class ScoreSummary:
    """
    Immutable scoring summary for one organization assessment.

    Attributes:
        coverage_percentage:
            Percentage calculated only from assessable controls.
            None when no control is assessable.

        earned_score:
            Sum of numeric control scores.

        maximum_score:
            Maximum possible score for the assessable controls.

        total_controls:
            Total number of control results received.

        assessable_controls:
            Number of controls included in scoring.

        not_assessable_controls:
            Number of controls excluded from scoring.

        status_counts:
            Number of controls assigned to each status.

        interpretation:
            Human-readable interpretation of the scoring result.
    """

    coverage_percentage: float | None
    earned_score: float
    maximum_score: float
    total_controls: int
    assessable_controls: int
    not_assessable_controls: int
    status_counts: tuple[tuple[ControlStatus, int], ...]
    interpretation: str

    @property
    def can_calculate_coverage(self) -> bool:
        """Return True when at least one control is assessable."""
        return self.coverage_percentage is not None

    def status_count(self, status: ControlStatus) -> int:
        """Return the number of results assigned to a specific status."""
        return dict(self.status_counts).get(status, 0)

    def status_counts_dict(self) -> dict[str, int]:
        """Return status counts using human-readable status values."""
        return {
            status.value: count
            for status, count in self.status_counts
        }


def _validate_results(
    results: tuple[ControlResult, ...] | list[ControlResult],
) -> tuple[ControlResult, ...]:
    """
    Validate and normalize the result collection.

    Raises:
        ScoringError:
            If the collection is empty, contains invalid objects or contains
            duplicate control identifiers.
    """
    normalized_results = tuple(results)

    if not normalized_results:
        raise ScoringError(
            "At least one ControlResult is required for scoring."
        )

    if not all(
        isinstance(result, ControlResult)
        for result in normalized_results
    ):
        raise ScoringError(
            "Every scoring input must be a ControlResult instance."
        )

    control_ids = [
        result.control_id
        for result in normalized_results
    ]

    duplicate_control_ids = sorted({
        control_id
        for control_id in control_ids
        if control_ids.count(control_id) > 1
    })

    if duplicate_control_ids:
        raise ScoringError(
            "Duplicate control results were provided: "
            + ", ".join(duplicate_control_ids)
        )

    return normalized_results


def _build_status_counts(
    results: tuple[ControlResult, ...],
) -> tuple[tuple[ControlStatus, int], ...]:
    """Count results in the stable ControlStatus declaration order."""
    return tuple(
        (
            status,
            sum(
                result.status is status
                for result in results
            ),
        )
        for status in ControlStatus
    )


def _interpret_coverage(
    coverage_percentage: float | None,
    assessable_controls: int,
    total_controls: int,
) -> str:
    """
    Return a restrained interpretation of the prototype coverage indicator.

    The interpretation is intentionally descriptive and must not be treated
    as an official compliance determination.
    """
    if coverage_percentage is None:
        return (
            "Coverage could not be calculated because none of the selected "
            "controls contained sufficient information for assessment."
        )

    if coverage_percentage == 100.0:
        assessment_text = (
            "All assessable selected controls satisfied the prototype rules."
        )
    elif coverage_percentage >= 75.0:
        assessment_text = (
            "The assessable selected controls show a comparatively high "
            "level of coverage, with remaining improvement areas."
        )
    elif coverage_percentage >= 50.0:
        assessment_text = (
            "The assessable selected controls show partial coverage and "
            "require targeted improvements."
        )
    elif coverage_percentage > 0.0:
        assessment_text = (
            "The assessable selected controls show limited coverage and "
            "require substantial improvement."
        )
    else:
        assessment_text = (
            "None of the assessable selected controls satisfied or partially "
            "satisfied the prototype rules."
        )

    if assessable_controls < total_controls:
        assessment_text += (
            f" Coverage is based on {assessable_controls} of "
            f"{total_controls} selected controls because "
            f"{total_controls - assessable_controls} control(s) were "
            "Not Assessable."
        )

    return assessment_text


def calculate_score(
    results: tuple[ControlResult, ...] | list[ControlResult],
) -> ScoreSummary:
    """
    Calculate the prototype coverage score.

    Formula:
        coverage_percentage =
            earned_score / maximum_score * 100

    Only assessable controls participate in the denominator.
    A Not Assessable result is excluded rather than scored as zero.
    """
    validated_results = _validate_results(results)

    assessable_results = tuple(
        result
        for result in validated_results
        if result.is_assessable
    )

    assessable_controls = len(assessable_results)
    total_controls = len(validated_results)
    not_assessable_controls = total_controls - assessable_controls

    earned_score = sum(
        result.numeric_score
        for result in assessable_results
        if result.numeric_score is not None
    )

    maximum_score = float(assessable_controls)

    if assessable_controls == 0:
        coverage_percentage: float | None = None
    else:
        coverage_percentage = round(
            (earned_score / maximum_score) * 100,
            2,
        )

    status_counts = _build_status_counts(validated_results)

    interpretation = _interpret_coverage(
        coverage_percentage=coverage_percentage,
        assessable_controls=assessable_controls,
        total_controls=total_controls,
    )

    return ScoreSummary(
        coverage_percentage=coverage_percentage,
        earned_score=earned_score,
        maximum_score=maximum_score,
        total_controls=total_controls,
        assessable_controls=assessable_controls,
        not_assessable_controls=not_assessable_controls,
        status_counts=status_counts,
        interpretation=interpretation,
    )