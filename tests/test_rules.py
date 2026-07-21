"""Tests for the deterministic security-control rule engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.models import ControlStatus
from src.rule_engine import (
    CRITICAL_PATCH_DEADLINE_DAYS,
    evaluate_mfa,
    evaluate_organization,
    evaluate_patch_management,
    load_control_catalogue,
)
from src.validator import load_json_file, validate_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture(scope="module")
def catalogue() -> dict[str, Any]:
    """Load the control catalogue once for this test module."""
    return load_control_catalogue()


@pytest.fixture(scope="module")
def expected_results() -> dict[str, Any]:
    """Load the a priori expected scenario results."""
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
def test_scenario_control_statuses_match_expected_results(
    scenario_filename: str,
    expected_results: dict[str, Any],
) -> None:
    """Each complete scenario must produce its declared statuses."""
    scenario_path = DATA_DIR / scenario_filename

    validate_file(scenario_path)
    scenario = load_json_file(scenario_path)
    results = evaluate_organization(scenario)

    actual_statuses = {
        result.control_id: result.status.value
        for result in results
    }

    expected_statuses = expected_results["scenarios"][
        scenario_filename
    ]["control_statuses"]

    assert actual_statuses == expected_statuses


def test_rule_engine_returns_results_in_stable_order() -> None:
    """Control results must always follow the declared evaluator order."""
    scenario = load_json_file(DATA_DIR / "scenario_mixed.json")
    results = evaluate_organization(scenario)

    assert tuple(result.control_id for result in results) == (
        "mfa",
        "backup",
        "patch_management",
        "incident_response",
    )


def test_mfa_null_is_not_assessable(
    catalogue: dict[str, Any],
) -> None:
    """JSON null must not be treated as explicit non-implementation."""
    result = evaluate_mfa(
        {
            "implemented": None,
            "evidence_available": False,
        },
        catalogue,
    )

    assert result.status is ControlStatus.NOT_ASSESSABLE
    assert result.numeric_score is None
    assert result.is_assessable is False


def test_mfa_absent_key_is_not_assessable(
    catalogue: dict[str, Any],
) -> None:
    """An absent critical key must behave like an explicit null value."""
    result = evaluate_mfa(
        {
            "evidence_available": False,
        },
        catalogue,
    )

    assert result.status is ControlStatus.NOT_ASSESSABLE


def test_mfa_false_is_not_satisfied(
    catalogue: dict[str, Any],
) -> None:
    """Explicit False must remain distinct from missing information."""
    result = evaluate_mfa(
        {
            "implemented": False,
            "privileged_accounts_covered": False,
            "remote_access_covered": False,
            "evidence_available": False,
        },
        catalogue,
    )

    assert result.status is ControlStatus.NOT_SATISFIED
    assert result.numeric_score == 0.0


def test_patch_deadline_at_threshold_is_satisfied(
    catalogue: dict[str, Any],
) -> None:
    """The exact prototype threshold is included in the accepted range."""
    result = evaluate_patch_management(
        {
            "patch_process_defined": True,
            "vulnerability_scanning_enabled": True,
            "critical_patch_deadline_days": (
                CRITICAL_PATCH_DEADLINE_DAYS
            ),
            "unsupported_software_present": False,
            "patch_status_reviewed": True,
            "evidence_available": True,
        },
        catalogue,
    )

    assert result.status is ControlStatus.SATISFIED


def test_patch_deadline_above_threshold_is_partial(
    catalogue: dict[str, Any],
) -> None:
    """One day above the prototype threshold must produce a gap."""
    result = evaluate_patch_management(
        {
            "patch_process_defined": True,
            "vulnerability_scanning_enabled": True,
            "critical_patch_deadline_days": (
                CRITICAL_PATCH_DEADLINE_DAYS + 1
            ),
            "unsupported_software_present": False,
            "patch_status_reviewed": True,
            "evidence_available": True,
        },
        catalogue,
    )

    assert result.status is ControlStatus.PARTIALLY_SATISFIED
    assert any(
        "deadline" in recommendation.lower()
        for recommendation in result.recommendations
    )


def test_missing_patch_field_is_not_assessable(
    catalogue: dict[str, Any],
) -> None:
    """A missing decisive patch field must not silently become False."""
    result = evaluate_patch_management(
        {
            "patch_process_defined": True,
            "vulnerability_scanning_enabled": True,
            "critical_patch_deadline_days": None,
            "unsupported_software_present": False,
            "patch_status_reviewed": True,
            "evidence_available": False,
        },
        catalogue,
    )

    assert result.status is ControlStatus.NOT_ASSESSABLE
    assert "critical_patch_deadline_days" in result.rationale


def test_missing_evidence_does_not_override_operational_status(
    catalogue: dict[str, Any],
) -> None:
    """
    Evidence absence creates an observation, not an automatic status failure.
    """
    result = evaluate_mfa(
        {
            "implemented": True,
            "privileged_accounts_covered": True,
            "remote_access_covered": True,
            "evidence_available": False,
        },
        catalogue,
    )

    assert result.status is ControlStatus.SATISFIED
    assert any(
        "self-reported input" in observation
        for observation in result.evidence
    )


def test_framework_mappings_are_loaded_into_results() -> None:
    """Rule results must include structured framework mappings."""
    scenario = load_json_file(DATA_DIR / "scenario_improved.json")
    results = evaluate_organization(scenario)

    mfa_result = next(
        result
        for result in results
        if result.control_id == "mfa"
    )

    references = {
        mapping.reference
        for mapping in mfa_result.mappings
    }

    assert "A.8.5" in references
    assert "Article 21(2)(j)" in references