"""Deterministic evaluation rules for the selected security controls."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .models import ControlResult, ControlStatus, FrameworkMapping
from .validator import load_json_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOGUE_PATH = PROJECT_ROOT / "data" / "control_catalogue.json"

# Researcher-defined threshold used only by this proof-of-concept.
CRITICAL_PATCH_DEADLINE_DAYS = 30

# Frequencies treated as regular for the limited backup assessment.
REGULAR_BACKUP_FREQUENCIES = {
    "continuous",
    "hourly",
    "daily",
    "weekly",
}


class RuleEngineError(ValueError):
    """Raised when rule-engine configuration or input is invalid."""


def load_control_catalogue(
    catalogue_path: str | Path = DEFAULT_CATALOGUE_PATH,
) -> dict[str, Any]:
    """
    Load and perform basic consistency checks on the control catalogue.
    """
    catalogue = load_json_file(catalogue_path)

    controls = catalogue.get("controls")

    if not isinstance(controls, dict):
        raise RuleEngineError(
            "The control catalogue must contain a 'controls' object."
        )

    required_control_ids = {
        "mfa",
        "backup",
        "patch_management",
        "incident_response",
    }

    missing_controls = required_control_ids - set(controls)

    if missing_controls:
        raise RuleEngineError(
            "The control catalogue is missing required controls: "
            + ", ".join(sorted(missing_controls))
        )

    for catalogue_key, control_data in controls.items():
        if not isinstance(control_data, dict):
            raise RuleEngineError(
                f"Catalogue entry '{catalogue_key}' must be an object."
            )

        if control_data.get("control_id") != catalogue_key:
            raise RuleEngineError(
                f"Catalogue key '{catalogue_key}' does not match its "
                "'control_id'."
            )

    return catalogue


def _get_catalogue_control(
    catalogue: dict[str, Any],
    control_id: str,
) -> dict[str, Any]:
    """Return one validated control entry from the catalogue."""
    controls = catalogue.get("controls", {})
    control_data = controls.get(control_id)

    if not isinstance(control_data, dict):
        raise RuleEngineError(
            f"Control '{control_id}' was not found in the catalogue."
        )

    return control_data


def _build_mappings(
    control_data: dict[str, Any],
) -> tuple[FrameworkMapping, ...]:
    """Convert catalogue mappings into FrameworkMapping objects."""
    raw_mappings = control_data.get("framework_mappings", [])

    if not isinstance(raw_mappings, list):
        raise RuleEngineError(
            "The 'framework_mappings' field must be an array."
        )

    mappings: list[FrameworkMapping] = []

    for mapping in raw_mappings:
        if not isinstance(mapping, dict):
            raise RuleEngineError(
                "Every framework mapping must be an object."
            )

        try:
            mappings.append(
                FrameworkMapping(
                    framework=mapping["framework"],
                    reference=mapping["reference"],
                    title=mapping["title"],
                    role=mapping.get("role", "primary"),
                )
            )
        except KeyError as exc:
            raise RuleEngineError(
                f"Framework mapping is missing required field: {exc.args[0]}"
            ) from exc

    return tuple(mappings)


def _evidence_observations(
    control: dict[str, Any],
) -> tuple[str, ...]:
    """
    Return evidence observations without changing the control status.

    Evidence availability is reported, but it is not used as an automatic
    gatekeeper for the deterministic assessment status.
    """
    evidence_available = control.get("evidence_available")

    if evidence_available is True:
        return ("Supporting evidence was declared available.",)

    if evidence_available is False:
        return (
          "Supporting evidence is not available because the "
          "because a vulnerability management process does not exist.",
        )

    return (
        "Supporting evidence is unknown because the user does not "
        "have enough information about incident response. ",
    )
  
def _missing_fields(
    control: dict[str, Any],
    fields: tuple[str, ...],
) -> tuple[str, ...]:
    """
    Return fields that are absent or explicitly set to null.

    dict.get() returns None for both cases, allowing the rule engine to treat
    an absent key and a JSON null value consistently.
    """
    return tuple(
        field
        for field in fields
        if control.get(field) is None
    )


def _build_result(
    *,
    control_id: str,
    control_data: dict[str, Any],
    status: ControlStatus,
    rationale: str,
    recommendations: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    additional_metadata: tuple[tuple[str, Any], ...] = (),
) -> ControlResult:
    """Build a ControlResult using metadata from the catalogue."""
    metadata = (
        ("category", control_data.get("category", "")),
        ("input_object", control_data.get("input_object", "")),
        ("assessment_scope", control_data.get("assessment_scope", "")),
    ) + additional_metadata

    return ControlResult(
        control_id=control_id,
        control_name=control_data["control_name"],
        status=status,
        rationale=rationale,
        recommendations=recommendations,
        evidence=evidence,
        mappings=_build_mappings(control_data),
        metadata=metadata,
    )


def evaluate_mfa(
    control: dict[str, Any],
    catalogue: dict[str, Any],
) -> ControlResult:
    """Evaluate multi factor authentication implementation."""
    control_id = "mfa"
    control_data = _get_catalogue_control(catalogue, control_id)
    evidence = _evidence_observations(control)

    implemented = control.get("implemented")

    if implemented is None:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "MFA implementation could not be assessed because the "
                "'implemented' value was not provided."
            ),
            recommendations=(
                "Confirm whether multi factor authentication is implemented.",
                "Document the systems and account categories covered by MFA.",
            ),
            evidence=evidence,
        )

    if implemented is False:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_SATISFIED,
            rationale=(
                "Multi factor authentication was explicitly reported as "
                "not implemented."
            ),
            recommendations=(
                "Implement MFA for privileged accounts.",
                "Implement MFA for remote access services.",
                "Retain configuration or policy evidence demonstrating deployment.",
            ),
            evidence=evidence,
        )

    required_scope_fields = (
        "privileged_accounts_covered",
        "remote_access_covered",
    )
    missing = _missing_fields(control, required_scope_fields)

    if missing:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "MFA was reported as implemented, but its deployment scope "
                f"could not be assessed because the following data is missing: "
                f"{', '.join(missing)}."
            ),
            recommendations=(
                "Confirm whether MFA covers privileged accounts.",
                "Confirm whether MFA covers remote access services.",
            ),
            evidence=evidence,
            additional_metadata=(("missing_fields", ", ".join(missing)),),
        )

    privileged_covered = control.get("privileged_accounts_covered") is True
    remote_covered = control.get("remote_access_covered") is True

    if privileged_covered and remote_covered:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.SATISFIED,
            rationale=(
                "MFA is implemented and covers both privileged accounts "
                "and remote access services."
            ),
            recommendations=(
                "Periodically review MFA coverage and authentication logs.",
            ),
            evidence=evidence,
        )

    uncovered_areas: list[str] = []

    if not privileged_covered:
        uncovered_areas.append("privileged accounts")

    if not remote_covered:
        uncovered_areas.append("remote access")

    return _build_result(
        control_id=control_id,
        control_data=control_data,
        status=ControlStatus.PARTIALLY_SATISFIED,
        rationale=(
            "MFA is implemented, but it does not cover all assessed areas. "
            f"Coverage is missing for: {', '.join(uncovered_areas)}."
        ),
        recommendations=tuple(
            f"Extend MFA coverage to {area}."
            for area in uncovered_areas
        ),
        evidence=evidence,
        additional_metadata=(
            ("uncovered_areas", ", ".join(uncovered_areas)),
        ),
    )


def evaluate_backup(
    control: dict[str, Any],
    catalogue: dict[str, Any],
) -> ControlResult:
    """Evaluate backup implementation and restoration testing."""
    control_id = "backup"
    control_data = _get_catalogue_control(catalogue, control_id)
    evidence = _evidence_observations(control)

    backups_enabled = control.get("backups_enabled")

    if backups_enabled is None:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "Backup implementation could not be assessed because the "
                "'backups_enabled' value was not provided."
            ),
            recommendations=(
                "Confirm whether organizational information is backed up.",
                "Document backup frequency, storage and restoration testing.",
            ),
            evidence=evidence,
        )

    if backups_enabled is False:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_SATISFIED,
            rationale="Information backups were explicitly reported as disabled.",
            recommendations=(
                "Implement scheduled backups for critical information and systems.",
                "Store backup copies separately from production systems.",
                "Establish and document restoration tests.",
            ),
            evidence=evidence,
        )

    critical_fields = (
        "backup_frequency",
        "offsite_or_separate_storage",
        "restore_tests_performed",
    )
    missing = _missing_fields(control, critical_fields)

    if missing:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "Backups were reported as enabled, but the control could not "
                "be assessed because the following data is missing: "
                f"{', '.join(missing)}."
            ),
            recommendations=(
                "Document the backup frequency.",
                "Confirm whether backup copies are stored separately.",
                "Confirm whether restoration tests are performed.",
            ),
            evidence=evidence,
            additional_metadata=(("missing_fields", ", ".join(missing)),),
        )

    backup_frequency = control.get("backup_frequency")
    separate_storage = (
        control.get("offsite_or_separate_storage") is True
    )
    restore_tests = control.get("restore_tests_performed") is True
    last_restore_test_date = control.get("last_restore_test_date")

    frequency_is_regular = (
        backup_frequency in REGULAR_BACKUP_FREQUENCIES
    )
    restore_test_is_documented = (
        restore_tests and last_restore_test_date is not None
    )

    all_requirements_met = (
        frequency_is_regular
        and separate_storage
        and restore_tests
        and restore_test_is_documented
    )

    if all_requirements_met:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.SATISFIED,
            rationale=(
                "Backups are enabled, performed on a regular schedule, stored "
                "separately and supported by a documented restoration test."
            ),
            recommendations=(
                "Continue periodic restoration testing and retain test records.",
            ),
            evidence=evidence,
            additional_metadata=(
                ("backup_frequency", backup_frequency),
                ("last_restore_test_date", last_restore_test_date),
            ),
        )

    gaps: list[str] = []
    recommendations: list[str] = []

    if not frequency_is_regular:
        gaps.append("backup frequency is not considered regular")
        recommendations.append(
            "Adopt a regular backup frequency appropriate to business needs."
        )

    if not separate_storage:
        gaps.append("separate or off-site storage is not used")
        recommendations.append(
            "Store backup copies separately from production systems."
        )

    if not restore_tests:
        gaps.append("restoration tests are not performed")
        recommendations.append(
            "Perform and document periodic backup restoration tests."
        )
    elif last_restore_test_date is None:
        gaps.append("the restoration-test date is not documented")
        recommendations.append(
            "Record the date and outcome of restoration tests."
        )

    return _build_result(
        control_id=control_id,
        control_data=control_data,
        status=ControlStatus.PARTIALLY_SATISFIED,
        rationale=(
            "Backups are enabled, but the assessed backup process is "
            f"incomplete: {'; '.join(gaps)}."
        ),
        recommendations=tuple(recommendations),
        evidence=evidence,
        additional_metadata=(
            ("backup_frequency", backup_frequency),
            ("identified_gaps", "; ".join(gaps)),
        ),
    )


def evaluate_patch_management(
    control: dict[str, Any],
    catalogue: dict[str, Any],
) -> ControlResult:
    """Evaluate patch and technical vulnerability management."""
    control_id = "patch_management"
    control_data = _get_catalogue_control(catalogue, control_id)
    evidence = _evidence_observations(control)

    process_defined = control.get("patch_process_defined")

    if process_defined is None:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "Patch management could not be assessed because the "
                "'patch_process_defined' value was not provided."
            ),
            recommendations=(
                "Confirm whether a documented patch-management process exists.",
                "Document vulnerability identification and remediation practices.",
            ),
            evidence=evidence,
        )

    if process_defined is False:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_SATISFIED,
            rationale=(
                "A defined vulnerability management process was explicitly reported "
                "as absent."
            ),
            recommendations=(
                "Establish a documented patch management process.",
                "Assign ownership and remediation timelines.",
                "Introduce vulnerability scanning and patch status reviews.",
                "Identify and replace unsupported software.",
            ),
            evidence=evidence,
        )

    critical_fields = (
        "vulnerability_scanning_enabled",
        "critical_patch_deadline_days",
        "unsupported_software_present",
        "patch_status_reviewed",
    )
    missing = _missing_fields(control, critical_fields)

    if missing:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "A patch-management process was reported, but the control "
                "could not be assessed because the following data is missing: "
                f"{', '.join(missing)}."
            ),
            recommendations=(
                "Document vulnerability-scanning practices.",
                "Define the remediation deadline for critical patches.",
                "Confirm whether unsupported software is present.",
                "Document periodic patch-status reviews.",
            ),
            evidence=evidence,
            additional_metadata=(("missing_fields", ", ".join(missing)),),
        )

    scanning_enabled = (
        control.get("vulnerability_scanning_enabled") is True
    )
    deadline_days = control.get("critical_patch_deadline_days")
    unsupported_present = (
        control.get("unsupported_software_present") is True
    )
    patch_status_reviewed = (
        control.get("patch_status_reviewed") is True
    )

    deadline_is_acceptable = (
        isinstance(deadline_days, int)
        and deadline_days <= CRITICAL_PATCH_DEADLINE_DAYS
    )

    all_requirements_met = (
        scanning_enabled
        and deadline_is_acceptable
        and not unsupported_present
        and patch_status_reviewed
    )

    if all_requirements_met:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.SATISFIED,
            rationale=(
                "A patch management process is defined, vulnerability "
                "scanning is enabled, critical patches are targeted within "
                f"{CRITICAL_PATCH_DEADLINE_DAYS} days, unsupported software "
                "is not reported and patch status is reviewed."
            ),
            recommendations=(
                "Continue monitoring remediation performance and review the "
                "patch deadline when risk conditions change.",
            ),
            evidence=evidence,
            additional_metadata=(
                ("critical_patch_deadline_days", deadline_days),
                (
                    "prototype_deadline_threshold_days",
                    CRITICAL_PATCH_DEADLINE_DAYS,
                ),
            ),
        )

    gaps: list[str] = []
    recommendations: list[str] = []

    if not scanning_enabled:
        gaps.append("vulnerability scanning is not enabled")
        recommendations.append(
            "Introduce periodic vulnerability scanning."
        )

    if not deadline_is_acceptable:
        gaps.append(
            "the critical patch deadline exceeds the prototype threshold "
            f"of {CRITICAL_PATCH_DEADLINE_DAYS} days"
        )
        recommendations.append(
            "Reduce the remediation deadline for critical patches to "
            f"{CRITICAL_PATCH_DEADLINE_DAYS} days or less."
        )

    if unsupported_present:
        gaps.append("unsupported software is present")
        recommendations.append(
            "Replace, upgrade or formally isolate unsupported software."
        )

    if not patch_status_reviewed:
        gaps.append("patch status is not periodically reviewed")
        recommendations.append(
            "Introduce periodic patch status and remediation reviews."
        )

    return _build_result(
        control_id=control_id,
        control_data=control_data,
        status=ControlStatus.PARTIALLY_SATISFIED,
        rationale=(
            "A patch management process exists, but the assessed process "
            f"contains gaps: {'; '.join(gaps)}."
        ),
        recommendations=tuple(recommendations),
        evidence=evidence,
        additional_metadata=(
            ("critical_patch_deadline_days", deadline_days),
            (
                "prototype_deadline_threshold_days",
                CRITICAL_PATCH_DEADLINE_DAYS,
            ),
            ("identified_gaps", "; ".join(gaps)),
        ),
    )


def evaluate_incident_response(
    control: dict[str, Any],
    catalogue: dict[str, Any],
) -> ControlResult:
    """Evaluate incident response planning and preparedness."""
    control_id = "incident_response"
    control_data = _get_catalogue_control(catalogue, control_id)
    evidence = _evidence_observations(control)

    plan_exists = control.get("plan_exists")

    if plan_exists is None:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "Incident response preparedness could not be assessed "
                "because the 'plan_exists' value was not provided."
            ),
            recommendations=(
                "Confirm whether an incident response plan exists.",
                "Document incident roles, communications, reporting and testing.",
            ),
            evidence=evidence,
        )

    if plan_exists is False:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_SATISFIED,
            rationale=(
                "An incident response plan was explicitly reported as absent."
            ),
            recommendations=(
                "Develop and approve an incident response plan.",
                "Assign incident response roles and responsibilities.",
                "Define internal communication and external reporting procedures.",
                "Test the plan through exercises or simulations.",
            ),
            evidence=evidence,
        )

    critical_fields = (
        "roles_defined",
        "communication_procedure_defined",
        "reporting_procedure_defined",
        "plan_tested",
    )
    missing = _missing_fields(control, critical_fields)

    if missing:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.NOT_ASSESSABLE,
            rationale=(
                "An incident response plan was reported, but preparedness "
                "could not be assessed because the following data is missing: "
                f"{', '.join(missing)}."
            ),
            recommendations=(
                "Confirm assigned incident response roles.",
                "Document communication and reporting procedures.",
                "Confirm whether the plan has been tested.",
            ),
            evidence=evidence,
            additional_metadata=(("missing_fields", ", ".join(missing)),),
        )

    roles_defined = control.get("roles_defined") is True
    communication_defined = (
        control.get("communication_procedure_defined") is True
    )
    reporting_defined = (
        control.get("reporting_procedure_defined") is True
    )
    plan_tested = control.get("plan_tested") is True
    last_test_date = control.get("last_test_date")

    test_is_documented = (
        plan_tested and last_test_date is not None
    )

    all_requirements_met = (
        roles_defined
        and communication_defined
        and reporting_defined
        and plan_tested
        and test_is_documented
    )

    if all_requirements_met:
        return _build_result(
            control_id=control_id,
            control_data=control_data,
            status=ControlStatus.SATISFIED,
            rationale=(
                "An incident response plan exists, roles are assigned, "
                "communication and reporting procedures are defined and "
                "a documented test has been performed."
            ),
            recommendations=(
                "Continue periodic incident response exercises and update "
                "the plan based on lessons identified.",
            ),
            evidence=evidence,
            additional_metadata=(
                ("last_test_date", last_test_date),
            ),
        )

    gaps: list[str] = []
    recommendations: list[str] = []

    if not roles_defined:
        gaps.append("incident response roles are not defined")
        recommendations.append(
            "Assign incident response roles and responsibilities."
        )

    if not communication_defined:
        gaps.append("communication procedures are not defined")
        recommendations.append(
            "Document internal and external incident communication procedures."
        )

    if not reporting_defined:
        gaps.append("reporting procedures are not defined")
        recommendations.append(
            "Document regulatory and stakeholder reporting procedures."
        )

    if not plan_tested:
        gaps.append("the incident response plan has not been tested")
        recommendations.append(
            "Test the incident response plan through an exercise or simulation."
        )
    elif last_test_date is None:
        gaps.append("the incident response test date is not documented")
        recommendations.append(
            "Record the date and outcome of incident response exercises."
        )

    return _build_result(
        control_id=control_id,
        control_data=control_data,
        status=ControlStatus.PARTIALLY_SATISFIED,
        rationale=(
            "An incident response plan exists, but preparedness is "
            f"incomplete: {'; '.join(gaps)}."
        ),
        recommendations=tuple(recommendations),
        evidence=evidence,
        additional_metadata=(
            ("identified_gaps", "; ".join(gaps)),
        ),
    )


EVALUATORS: dict[
    str,
    Callable[[dict[str, Any], dict[str, Any]], ControlResult],
] = {
    "mfa": evaluate_mfa,
    "backup": evaluate_backup,
    "patch_management": evaluate_patch_management,
    "incident_response": evaluate_incident_response,
}


def evaluate_security_controls(
    security_controls: dict[str, Any],
    catalogue: dict[str, Any] | None = None,
) -> tuple[ControlResult, ...]:
    """
    Evaluate all selected controls in a stable order.

    The returned tuple cannot be resized or reordered accidentally.
    """
    if not isinstance(security_controls, dict):
        raise RuleEngineError(
            "The 'security_controls' value must be an object."
        )

    active_catalogue = (
        catalogue
        if catalogue is not None
        else load_control_catalogue()
    )

    results: list[ControlResult] = []

    for control_id, evaluator in EVALUATORS.items():
        control_input = security_controls.get(control_id)

        if not isinstance(control_input, dict):
            raise RuleEngineError(
                f"Security-control input '{control_id}' must be an object."
            )

        results.append(
            evaluator(control_input, active_catalogue)
        )

    return tuple(results)


def evaluate_organization(
    organization_data: dict[str, Any],
    catalogue: dict[str, Any] | None = None,
) -> tuple[ControlResult, ...]:
    """
    Evaluate a validated organization-data dictionary.

    Schema validation must occur before this function is called.
    """
    if not isinstance(organization_data, dict):
        raise RuleEngineError(
            "Organization data must be an object."
        )

    security_controls = organization_data.get("security_controls")

    if not isinstance(security_controls, dict):
        raise RuleEngineError(
            "Organization data must contain a 'security_controls' object."
        )

    return evaluate_security_controls(
        security_controls=security_controls,
        catalogue=catalogue,
    )
