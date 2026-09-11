"""Tests for the selected-controls scoring component."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.models import ControlResult, ControlStatus
from src.rule_engine import evaluate_organization
from src.scoring import ScoringError, calculate_score
from src.validator import load_json_file, validate_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(scope="module")
def expected_results() -> dict[str, Any]:
    """Load expected score values for all maintained scenarios."""
    return load_json_file(DATA_DIR / "expected_results.json")


@pytest.mark.parametrize(
    "scenario_filename",
    (
        "scenario_low.json",
        "scenario_partial.json",
        "scenario_improved.json",
        "scenario_missing_data.json",
        "scenario_mixed.json",
    ),
)
def test_scenario_scores_match_expected_results(
    scenario_filename: str,
    expected_results: dict[str, Any],
) -> None:
    """Scenario score summaries must match their a priori expectations."""
    scenario_path = DATA_DIR / scenario_filename

    validate_file(scenario_path)
    scenario = load_json_file(scenario_path)

    results = evaluate_organization(scenario)
    score = calculate_score(results)

    expected = expected_results["scenarios"][scenario_filename]

    assert score.coverage_percentage == pytest.approx(
        expected["coverage_percentage"]
    )
    assert score.earned_score == pytest.approx(
        expected["earned_score"]
    )
    assert score.maximum_score == pytest.approx(
        expected["maximum_score"]
    )
    assert score.assessable_controls == expected[
        "assessable_controls"
    ]
    assert score.not_assessable_controls == expected[
        "not_assessable_controls"
    ]


def test_missing_data_scenario_excludes_not_assessable_controls() -> None:
    """The denominator must include only the two assessable controls."""
    scenario = load_json_file(
        DATA_DIR / "scenario_missing_data.json"
    )
    results = evaluate_organization(scenario)
    score = calculate_score(results)

    assert score.total_controls == 4
    assert score.assessable_controls == 2
    assert score.not_assessable_controls == 2
    assert score.maximum_score == 2.0
    assert score.earned_score == 1.0
    assert score.coverage_percentage == 50.0


def test_all_not_assessable_returns_no_percentage() -> None:
    """No assessable controls must produce None rather than zero."""
    results = (
        ControlResult(
            control_id="mfa",
            control_name="Multi Factor Authentication",
            status=ControlStatus.NOT_ASSESSABLE,
            rationale="Insufficient information.",
        ),
        ControlResult(
            control_id="backup",
            control_name="Backup and Restore Testing",
            status=ControlStatus.NOT_ASSESSABLE,
            rationale="Insufficient information.",
        ),
    )

    score = calculate_score(results)

    assert score.coverage_percentage is None
    assert score.earned_score == 0.0
    assert score.maximum_score == 0.0
    assert score.assessable_controls == 0
    assert score.not_assessable_controls == 2
    assert score.can_calculate_coverage is False


def test_confirmed_zero_coverage_is_distinct_from_unavailable_score() -> None:
    """Confirmed failures must produce 0%, not None."""
    results = (
        ControlResult(
            control_id="mfa",
            control_name="Multi Factor Authentication",
            status=ControlStatus.NOT_SATISFIED,
            rationale="MFA is not implemented.",
        ),
        ControlResult(
            control_id="backup",
            control_name="Backup and Restore Testing",
            status=ControlStatus.NOT_SATISFIED,
            rationale="Backups are disabled.",
        ),
    )

    score = calculate_score(results)

    assert score.coverage_percentage == 0.0
    assert score.can_calculate_coverage is True
    assert score.assessable_controls == 2


def test_duplicate_control_results_are_rejected() -> None:
    """One control must not contribute to the score twice."""
    result = ControlResult(
        control_id="mfa",
        control_name="Multi Factor Authentication",
        status=ControlStatus.SATISFIED,
        rationale="MFA is implemented.",
    )

    with pytest.raises(
        ScoringError,
        match="Duplicate control results were provided: mfa",
    ):
        calculate_score((result, result))


def test_empty_result_collection_is_rejected() -> None:
    """A score cannot be calculated without control results."""
    with pytest.raises(
        ScoringError,
        match="At least one ControlResult is required",
    ):
        calculate_score(())


def test_status_counts_are_correct() -> None:
    """The mixed scenario must expose the expected status distribution."""
    scenario = load_json_file(DATA_DIR / "scenario_mixed.json")
    results = evaluate_organization(scenario)
    score = calculate_score(results)

    assert score.status_count(ControlStatus.SATISFIED) == 2
    assert score.status_count(
        ControlStatus.PARTIALLY_SATISFIED
    ) == 1
    assert score.status_count(ControlStatus.NOT_SATISFIED) == 1
    assert score.status_count(ControlStatus.NOT_ASSESSABLE) == 0

    assert score.status_counts_dict() == {
        "Satisfied": 2,
        "Partially Satisfied": 1,
        "Not Satisfied": 1,
        "Not Assessable": 0,
    }


def test_score_summary_is_immutable() -> None:
    """The calculated summary must not be mutable after creation."""
    scenario = load_json_file(DATA_DIR / "scenario_mixed.json")
    results = evaluate_organization(scenario)
    score = calculate_score(results)

    with pytest.raises(AttributeError):
        score.coverage_percentage = 100.0