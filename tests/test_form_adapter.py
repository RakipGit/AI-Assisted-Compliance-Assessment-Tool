"""Tests for guided-form conversion into canonical assessment input."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.form_adapter import (
    FormInputError,
    build_backup_input,
    build_incident_response_input,
    build_mfa_input,
    build_organization_payload,
    build_patch_input,
)
from src.models import ControlStatus
from src.rule_engine import evaluate_organization
from src.scoring import calculate_score
from src.validator import load_schema, validate_data


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def build_valid_payload() -> dict[str, Any]:
    """Return a complete form-derived payload."""
    return build_organization_payload(
        name="Example SME",
        size="small",
        employees=25,
        sector="IT services",
        description="Form adapter test.",
        mfa=build_mfa_input(
            unknown=False,
            implemented=True,
            privileged_accounts_covered=True,
            remote_access_covered=False,
            evidence_available=True,
        ),
        backup=build_backup_input(
            unknown=False,
            backups_enabled=True,
            backup_frequency="daily",
            offsite_or_separate_storage=True,
            restore_tests_performed=False,
            last_restore_test_date=None,
            evidence_available=True,
        ),
        patch_management=build_patch_input(
            unknown=False,
            process_defined=True,
            vulnerability_scanning_enabled=True,
            critical_patch_deadline_days=30,
            unsupported_software_present=False,
            patch_status_reviewed=True,
            evidence_available=True,
        ),
        incident_response=build_incident_response_input(
            unknown=False,
            plan_exists=True,
            roles_defined=True,
            communication_procedure_defined=True,
            reporting_procedure_defined=True,
            plan_tested=True,
            last_test_date=date(2026, 7, 10),
            evidence_available=True,
        ),
    )


def test_form_payload_conforms_to_schema() -> None:
    """A complete form-derived payload must pass schema validation."""
    payload = build_valid_payload()
    schema = load_schema(DATA_DIR / "organization_schema.json")

    validate_data(payload, schema)


def test_mfa_unknown_produces_null_fields() -> None:
    """Unknown MFA information must become canonical null values."""
    result = build_mfa_input(
        unknown=True,
        implemented=True,
        privileged_accounts_covered=True,
        remote_access_covered=True,
        evidence_available=True,
    )

    assert result == {
        "implemented": None,
        "privileged_accounts_covered": None,
        "remote_access_covered": None,
        "evidence_available": None,
    }


def test_mfa_not_implemented_sets_dependent_fields_false() -> None:
    """No MFA means its dependent coverage fields are confirmed False."""
    result = build_mfa_input(
        unknown=False,
        implemented=False,
        privileged_accounts_covered=True,
        remote_access_covered=True,
        evidence_available=False,
    )

    assert result["implemented"] is False
    assert result["privileged_accounts_covered"] is False
    assert result["remote_access_covered"] is False


def test_disabled_backups_have_no_frequency_or_test_date() -> None:
    """Disabled backups must not retain inapplicable values."""
    result = build_backup_input(
        unknown=False,
        backups_enabled=False,
        backup_frequency="daily",
        offsite_or_separate_storage=True,
        restore_tests_performed=True,
        last_restore_test_date=date(2026, 7, 1),
        evidence_available=False,
    )

    assert result == {
        "backups_enabled": False,
        "backup_frequency": None,
        "offsite_or_separate_storage": False,
        "restore_tests_performed": False,
        "last_restore_test_date": None,
        "evidence_available": False,
    }


def test_restore_test_date_is_serialized_to_iso() -> None:
    """Streamlit date objects must become JSON-compatible ISO text."""
    result = build_backup_input(
        unknown=False,
        backups_enabled=True,
        backup_frequency="daily",
        offsite_or_separate_storage=True,
        restore_tests_performed=True,
        last_restore_test_date=date(2026, 6, 15),
        evidence_available=True,
    )

    assert result["last_restore_test_date"] == "2026-06-15"


def test_no_patch_process_sets_boolean_dependencies_false() -> None:
    """An absent patch process must not retain contradictory sub-values."""
    result = build_patch_input(
        unknown=False,
        process_defined=False,
        vulnerability_scanning_enabled=True,
        critical_patch_deadline_days=14,
        unsupported_software_present=True,
        patch_status_reviewed=True,
        evidence_available=False,
    )

    assert result["patch_process_defined"] is False
    assert result["vulnerability_scanning_enabled"] is False
    assert result["critical_patch_deadline_days"] is None
    assert result["unsupported_software_present"] is False
    assert result["patch_status_reviewed"] is False


def test_no_incident_plan_sets_dependencies_false() -> None:
    """An absent incident plan must clear dependent preparedness values."""
    result = build_incident_response_input(
        unknown=False,
        plan_exists=False,
        roles_defined=True,
        communication_procedure_defined=True,
        reporting_procedure_defined=True,
        plan_tested=True,
        last_test_date=date(2026, 7, 1),
        evidence_available=False,
    )

    assert result["plan_exists"] is False
    assert result["roles_defined"] is False
    assert result["communication_procedure_defined"] is False
    assert result["reporting_procedure_defined"] is False
    assert result["plan_tested"] is False
    assert result["last_test_date"] is None


def test_required_text_is_trimmed() -> None:
    """Organization text input must be normalized."""
    payload = build_valid_payload()

    payload = build_organization_payload(
        name="  Example SME  ",
        size="small",
        employees=25,
        sector="  IT services  ",
        description="  Description  ",
        mfa=payload["security_controls"]["mfa"],
        backup=payload["security_controls"]["backup"],
        patch_management=(
            payload["security_controls"]["patch_management"]
        ),
        incident_response=(
            payload["security_controls"]["incident_response"]
        ),
    )

    assert payload["organization"]["name"] == "Example SME"
    assert payload["organization"]["sector"] == "IT services"
    assert payload["organization"]["description"] == "Description"


def test_empty_organization_name_is_rejected() -> None:
    """The guided form must reject an empty organization name."""
    payload = build_valid_payload()

    with pytest.raises(
        FormInputError,
        match="Organization name is required",
    ):
        build_organization_payload(
            name="   ",
            size="small",
            employees=25,
            sector="IT services",
            description=None,
            mfa=payload["security_controls"]["mfa"],
            backup=payload["security_controls"]["backup"],
            patch_management=(
                payload["security_controls"]["patch_management"]
            ),
            incident_response=(
                payload["security_controls"]["incident_response"]
            ),
        )


def test_form_payload_produces_expected_backend_results() -> None:
    """Form conversion must integrate correctly with rules and scoring."""
    payload = build_valid_payload()

    results = evaluate_organization(payload)
    score = calculate_score(results)

    statuses = {
        result.control_id: result.status
        for result in results
    }

    assert statuses["mfa"] is ControlStatus.PARTIALLY_SATISFIED
    assert statuses["backup"] is ControlStatus.PARTIALLY_SATISFIED
    assert statuses["patch_management"] is ControlStatus.SATISFIED
    assert statuses["incident_response"] is ControlStatus.SATISFIED

    assert score.coverage_percentage == 75.0