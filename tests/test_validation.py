"""Tests for JSON Schema validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.validator import (
    SchemaValidationError,
    load_json_file,
    load_schema,
    validate_data,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

SCENARIO_FILES = (
    "scenario_low.json",
    "scenario_partial.json",
    "scenario_improved.json",
    "scenario_missing_data.json",
    "scenario_mixed.json",
)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    """Load the organization schema once for this test module."""
    return load_schema(DATA_DIR / "organization_schema.json")


@pytest.fixture
def valid_scenario() -> dict[str, Any]:
    """Return a valid scenario that individual tests may modify."""
    return load_json_file(DATA_DIR / "scenario_improved.json")


@pytest.mark.parametrize("scenario_filename", SCENARIO_FILES)
def test_official_scenarios_are_schema_valid(
    scenario_filename: str,
    schema: dict[str, Any],
) -> None:
    """All five maintained scenarios must conform to the schema."""
    scenario = load_json_file(DATA_DIR / scenario_filename)

    validate_data(scenario, schema)


def test_inconsistent_size_and_employee_count_is_rejected(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """A micro organization cannot declare 200 employees."""
    invalid_scenario = deepcopy(valid_scenario)
    invalid_scenario["organization"]["size"] = "micro"
    invalid_scenario["organization"]["employees"] = 200

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_data(invalid_scenario, schema)

    assert any(
        "organization.employees" in error
        and "greater than the maximum of 9" in error
        for error in exc_info.value.errors
    )


def test_non_integer_employee_count_is_rejected(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """The employee count must be an integer."""
    invalid_scenario = deepcopy(valid_scenario)
    invalid_scenario["organization"]["size"] = "small"
    invalid_scenario["organization"]["employees"] = "twenty"

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_data(invalid_scenario, schema)

    assert any(
        "organization.employees" in error
        and "is not of type 'integer'" in error
        for error in exc_info.value.errors
    )


def test_invalid_date_is_rejected(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """FormatChecker must reject an impossible calendar date."""
    invalid_scenario = deepcopy(valid_scenario)
    invalid_scenario["security_controls"]["backup"][
        "last_restore_test_date"
    ] = "2026-99-45"

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_data(invalid_scenario, schema)

    assert any(
        "security_controls.backup.last_restore_test_date" in error
        and "is not a 'date'" in error
        for error in exc_info.value.errors
    )


def test_unknown_control_property_is_rejected(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Typos must be rejected because additionalProperties is false."""
    invalid_scenario = deepcopy(valid_scenario)
    invalid_scenario["security_controls"]["backup"][
        "backups_enabeld"
    ] = True

    with pytest.raises(SchemaValidationError) as exc_info:
        validate_data(invalid_scenario, schema)

    assert any(
        "security_controls.backup" in error
        and "Additional properties are not allowed" in error
        and "backups_enabeld" in error
        for error in exc_info.value.errors
    )


def test_incomplete_control_object_is_structurally_valid(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """
    Missing internal control fields remain valid at schema level.

    The rule engine is responsible for returning Not Assessable.
    """
    incomplete_scenario = deepcopy(valid_scenario)
    incomplete_scenario["security_controls"]["mfa"] = {}

    validate_data(incomplete_scenario, schema)


def test_null_control_value_is_structurally_valid(
    valid_scenario: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """Explicit null values are accepted for incomplete assessment data."""
    incomplete_scenario = deepcopy(valid_scenario)
    incomplete_scenario["security_controls"]["mfa"] = {
        "implemented": None,
        "evidence_available": False,
    }

    validate_data(incomplete_scenario, schema)