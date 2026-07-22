"""Conversion of guided-form answers into canonical assessment input."""

from __future__ import annotations

from datetime import date
from typing import Any


class FormInputError(ValueError):
    """Raised when guided-form values cannot be converted safely."""


def _clean_required_text(value: str, field_name: str) -> str:
    """Normalize and validate a required text field."""
    if not isinstance(value, str):
        raise FormInputError(f"{field_name} must be text.")

    cleaned = value.strip()

    if not cleaned:
        raise FormInputError(f"{field_name} is required.")

    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    """Normalize an optional text value."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise FormInputError("Optional description must be text.")

    cleaned = value.strip()

    return cleaned or None


def _date_to_iso(value: date | str | None) -> str | None:
    """
    Convert an optional date to ISO 8601 format.

    Strings are accepted because imported or restored Streamlit state may
    already contain an ISO-formatted date.
    """
    if value is None:
        return None

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None

    raise FormInputError(
        "Date values must be datetime.date, ISO text or None."
    )


def build_mfa_input(
    *,
    unknown: bool,
    implemented: bool,
    privileged_accounts_covered: bool,
    remote_access_covered: bool,
    evidence_available: bool,
) -> dict[str, Any]:
    """Build canonical MFA input from form answers."""
    if unknown:
        return {
            "implemented": None,
            "privileged_accounts_covered": None,
            "remote_access_covered": None,
            "evidence_available": None,
        }

    if not implemented:
        return {
            "implemented": False,
            "privileged_accounts_covered": False,
            "remote_access_covered": False,
            "evidence_available": evidence_available,
        }

    return {
        "implemented": True,
        "privileged_accounts_covered": privileged_accounts_covered,
        "remote_access_covered": remote_access_covered,
        "evidence_available": evidence_available,
    }


def build_backup_input(
    *,
    unknown: bool,
    backups_enabled: bool,
    backup_frequency: str | None,
    offsite_or_separate_storage: bool,
    restore_tests_performed: bool,
    last_restore_test_date: date | str | None,
    evidence_available: bool,
) -> dict[str, Any]:
    """Build canonical backup input from form answers."""
    if unknown:
        return {
            "backups_enabled": None,
            "backup_frequency": None,
            "offsite_or_separate_storage": None,
            "restore_tests_performed": None,
            "last_restore_test_date": None,
            "evidence_available": None,
        }

    if not backups_enabled:
        return {
            "backups_enabled": False,
            "backup_frequency": None,
            "offsite_or_separate_storage": False,
            "restore_tests_performed": False,
            "last_restore_test_date": None,
            "evidence_available": evidence_available,
        }

    return {
        "backups_enabled": True,
        "backup_frequency": backup_frequency,
        "offsite_or_separate_storage": offsite_or_separate_storage,
        "restore_tests_performed": restore_tests_performed,
        "last_restore_test_date": (
            _date_to_iso(last_restore_test_date)
            if restore_tests_performed
            else None
        ),
        "evidence_available": evidence_available,
    }


def build_patch_input(
    *,
    unknown: bool,
    process_defined: bool,
    vulnerability_scanning_enabled: bool,
    critical_patch_deadline_days: int | None,
    unsupported_software_present: bool,
    patch_status_reviewed: bool,
    evidence_available: bool,
) -> dict[str, Any]:
    """Build canonical patch-management input from form answers."""
    if unknown:
        return {
            "patch_process_defined": None,
            "vulnerability_scanning_enabled": None,
            "critical_patch_deadline_days": None,
            "unsupported_software_present": None,
            "patch_status_reviewed": None,
            "evidence_available": None,
        }

    if not process_defined:
        return {
            "patch_process_defined": False,
            "vulnerability_scanning_enabled": False,
            "critical_patch_deadline_days": None,
            "unsupported_software_present": False,
            "patch_status_reviewed": False,
            "evidence_available": evidence_available,
        }

    return {
        "patch_process_defined": True,
        "vulnerability_scanning_enabled": (
            vulnerability_scanning_enabled
        ),
        "critical_patch_deadline_days": (
            critical_patch_deadline_days
        ),
        "unsupported_software_present": (
            unsupported_software_present
        ),
        "patch_status_reviewed": patch_status_reviewed,
        "evidence_available": evidence_available,
    }


def build_incident_response_input(
    *,
    unknown: bool,
    plan_exists: bool,
    roles_defined: bool,
    communication_procedure_defined: bool,
    reporting_procedure_defined: bool,
    plan_tested: bool,
    last_test_date: date | str | None,
    evidence_available: bool,
) -> dict[str, Any]:
    """Build canonical incident-response input from form answers."""
    if unknown:
        return {
            "plan_exists": None,
            "roles_defined": None,
            "communication_procedure_defined": None,
            "reporting_procedure_defined": None,
            "plan_tested": None,
            "last_test_date": None,
            "evidence_available": None,
        }

    if not plan_exists:
        return {
            "plan_exists": False,
            "roles_defined": False,
            "communication_procedure_defined": False,
            "reporting_procedure_defined": False,
            "plan_tested": False,
            "last_test_date": None,
            "evidence_available": evidence_available,
        }

    return {
        "plan_exists": True,
        "roles_defined": roles_defined,
        "communication_procedure_defined": (
            communication_procedure_defined
        ),
        "reporting_procedure_defined": (
            reporting_procedure_defined
        ),
        "plan_tested": plan_tested,
        "last_test_date": (
            _date_to_iso(last_test_date)
            if plan_tested
            else None
        ),
        "evidence_available": evidence_available,
    }


def build_organization_payload(
    *,
    name: str,
    size: str,
    employees: int,
    sector: str,
    description: str | None,
    mfa: dict[str, Any],
    backup: dict[str, Any],
    patch_management: dict[str, Any],
    incident_response: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the complete canonical organization input."""
    if size not in {"micro", "small", "medium"}:
        raise FormInputError(
            "Organization size must be micro, small or medium."
        )

    if isinstance(employees, bool) or not isinstance(employees, int):
        raise FormInputError(
            "Number of employees must be an integer."
        )

    return {
        "organization": {
            "name": _clean_required_text(
                name,
                "Organization name",
            ),
            "size": size,
            "employees": employees,
            "sector": _clean_required_text(
                sector,
                "Organization sector",
            ),
            "description": _clean_optional_text(description),
        },
        "security_controls": {
            "mfa": dict(mfa),
            "backup": dict(backup),
            "patch_management": dict(patch_management),
            "incident_response": dict(incident_response),
        },
    }