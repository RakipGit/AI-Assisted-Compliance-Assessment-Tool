from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "data" / "organization_schema.json"


class JSONFileError(ValueError):
    """Raised when a JSON file cannot be read or parsed."""


class SchemaValidationError(ValueError):
    """Raised when input data does not conform to the JSON Schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_json_file(file_path: str | Path) -> dict[str, Any]:
    """
    Load and parse a JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        JSONFileError: If the file is not valid JSON or its root is not an object.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise JSONFileError(f"Path is not a file: {path}")

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise JSONFileError(
            f"Invalid JSON in '{path}': "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise JSONFileError(f"Could not read '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise JSONFileError(
            f"The root value of '{path}' must be a JSON object."
        )

    return data


def load_schema(
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """
    Load the JSON Schema and verify that the schema itself is valid.

    The validator implementation is selected from the schema's '$schema'
    declaration rather than being hardcoded.
    """
    schema = load_json_file(schema_path)

    validator_class = validator_for(schema)

    try:
        validator_class.check_schema(schema)
    except SchemaError as exc:
        raise JSONFileError(
            f"Invalid JSON Schema in '{schema_path}': {exc.message}"
        ) from exc

    return schema


def format_error_path(error_path: Any) -> str:
    """
    Convert a jsonschema error path into a readable dotted path.

    Example:
        security_controls.backup.backups_enabled
    """
    parts = [str(part) for part in error_path]

    if not parts:
        return "<root>"

    return ".".join(parts)


def collect_validation_errors(
    instance: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """
    Validate an input dictionary and return all detected errors.

    An empty list means that the input is valid.
    """
    validator_class = validator_for(schema)

    validator = validator_class(
        schema,
        format_checker=FormatChecker(),
    )

    validation_errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (
            list(error.absolute_path),
            error.message,
        ),
    )

    formatted_errors: list[str] = []

    for error in validation_errors:
        path = format_error_path(error.absolute_path)
        formatted_errors.append(f"{path}: {error.message}")

    return formatted_errors


def validate_data(
    instance: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    """
    Validate already-loaded input data.

    Raises:
        SchemaValidationError: If one or more validation errors are found.
    """
    errors = collect_validation_errors(instance, schema)

    if errors:
        raise SchemaValidationError(errors)


def validate_file(
    input_path: str | Path,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> None:
    """
    Load and validate one organization scenario file.

    Raises:
        FileNotFoundError
        JSONFileError
        SchemaValidationError
    """
    schema = load_schema(schema_path)
    instance = load_json_file(input_path)
    validate_data(instance, schema)


def discover_scenario_files() -> list[Path]:
    """Return all scenario JSON files from the data directory."""
    data_directory = PROJECT_ROOT / "data"

    return sorted(data_directory.glob("scenario_*.json"))


def run_validation(input_paths: list[Path]) -> int:
    """
    Validate multiple scenario files.

    Returns:
        0 when all files pass.
        1 when at least one file fails.
    """
    try:
        schema = load_schema()
    except (FileNotFoundError, JSONFileError) as exc:
        print(f"[SCHEMA ERROR] {exc}")
        return 1

    print(f"Schema valid: {DEFAULT_SCHEMA_PATH.name}")
    print()

    failed_files = 0

    for input_path in input_paths:
        try:
            instance = load_json_file(input_path)
            validate_data(instance, schema)

            print(f"[VALID] {input_path.name}")

        except FileNotFoundError as exc:
            failed_files += 1
            print(f"[FILE ERROR] {input_path.name}")
            print(f"  - {exc}")

        except JSONFileError as exc:
            failed_files += 1
            print(f"[JSON ERROR] {input_path.name}")
            print(f"  - {exc}")

        except SchemaValidationError as exc:
            failed_files += 1
            print(f"[INVALID] {input_path.name}")

            for error in exc.errors:
                print(f"  - {error}")

    print()

    if failed_files == 0:
        print(f"Validation completed: {len(input_paths)} file(s) passed.")
        return 0

    print(
        f"Validation completed: {failed_files} of "
        f"{len(input_paths)} file(s) failed."
    )
    return 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate organization scenario JSON files against "
            "organization_schema.json."
        )
    )

    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help=(
            "Scenario JSON files to validate. "
            "When omitted, all data/scenario_*.json files are validated."
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    input_paths = (
        arguments.files
        if arguments.files
        else discover_scenario_files()
    )

    if not input_paths:
        print("No scenario JSON files were found.")
        return 1

    return run_validation(input_paths)


if __name__ == "__main__":
    sys.exit(main())