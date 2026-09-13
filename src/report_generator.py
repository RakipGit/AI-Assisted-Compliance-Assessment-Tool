"""HTML report generation for completed organization assessments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Sequence

from jinja2 import (
    Environment,
    FileSystemLoader,
    TemplateError,
    select_autoescape,
)

from .ai_summary import AISummary
from .models import ControlResult
from .scoring import ScoreSummary


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE_DIR = PROJECT_ROOT / "templates"
DEFAULT_TEMPLATE_NAME = "report_template.html"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"


class ReportGenerationError(RuntimeError):
    """Raised when an assessment report cannot be generated safely."""


@dataclass(frozen=True)
class ReportArtifact:
    """
    Immutable representation of a generated HTML report.

    Attributes:
        filename:
            Generated report filename.

        path:
            Full local path when the report has been written to disk.
            None when only the HTML string was generated.

        html:
            Complete HTML report content.

        generated_at:
            UTC generation timestamp.
    """

    filename: str
    path: Path | None
    html: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if not self.filename.strip():
            raise ValueError("Report filename must not be empty.")

        if not self.html.strip():
            raise ValueError("Report HTML must not be empty.")

        if self.generated_at.tzinfo is None:
            raise ValueError(
                "Report generation timestamp must be timezone-aware."
            )


def _normalize_results(
    results: Sequence[ControlResult],
) -> tuple[ControlResult, ...]:
    """Validate and normalize deterministic control results."""
    normalized_results = tuple(results)

    if not normalized_results:
        raise ReportGenerationError(
            "At least one ControlResult is required to generate a report."
        )

    if not all(
        isinstance(result, ControlResult)
        for result in normalized_results
    ):
        raise ReportGenerationError(
            "Every report result must be a ControlResult instance."
        )

    control_ids = [
        result.control_id
        for result in normalized_results
    ]

    duplicate_ids = sorted({
        control_id
        for control_id in control_ids
        if control_ids.count(control_id) > 1
    })

    if duplicate_ids:
        raise ReportGenerationError(
            "Duplicate control results were provided: "
            + ", ".join(duplicate_ids)
        )

    return normalized_results


def _extract_organization_metadata(
    organization: dict[str, Any],
) -> dict[str, Any]:
    """
    Return validated organization metadata.

    Both the complete scenario dictionary and the inner organization object
    are accepted.
    """
    if not isinstance(organization, dict):
        raise ReportGenerationError(
            "Organization report input must be an object."
        )

    organization_data = organization.get(
        "organization",
        organization,
    )

    if not isinstance(organization_data, dict):
        raise ReportGenerationError(
            "Organization metadata must be an object."
        )

    return {
        "name": organization_data.get(
            "name",
            "Unnamed organization",
        ),
        "size": organization_data.get(
            "size",
            "Not specified",
        ),
        "employees": organization_data.get(
            "employees",
            "Not specified",
        ),
        "sector": organization_data.get(
            "sector",
            "Not specified",
        ),
        "description": organization_data.get(
            "description",
        ),
    }


def _slugify(value: str) -> str:
    """Convert an organization name into a safe filename component."""
    normalized = value.strip().lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "-",
        normalized,
    )

    normalized = normalized.strip("-")

    return normalized or "organization"


def _format_coverage(
    score: ScoreSummary,
) -> str:
    """Return the coverage value in presentation format."""
    if score.coverage_percentage is None:
        return "Not calculable"

    return f"{score.coverage_percentage:.2f}%"


def _status_css_class(status_value: str) -> str:
    """Map a human-readable status to a CSS class."""
    status_classes = {
        "Satisfied": "status-satisfied",
        "Partially Satisfied": "status-partial",
        "Not Satisfied": "status-not-satisfied",
        "Not Assessable": "status-not-assessable",
    }

    return status_classes.get(
        status_value,
        "status-not-assessable",
    )


def _serialize_results(
    results: tuple[ControlResult, ...],
) -> tuple[dict[str, Any], ...]:
    """Convert immutable result objects into template-safe dictionaries."""
    serialized_results: list[dict[str, Any]] = []

    for result in results:
        serialized_results.append(
            {
                "control_id": result.control_id,
                "control_name": result.control_name,
                "status": result.status.value,
                "status_css_class": _status_css_class(
                    result.status.value
                ),
                "numeric_score": result.numeric_score,
                "is_assessable": result.is_assessable,
                "rationale": result.rationale,
                "recommendations": result.recommendations,
                "evidence": result.evidence,
                "mappings": tuple(
                    {
                        "framework": mapping.framework,
                        "reference": mapping.reference,
                        "title": mapping.title,
                        "role": mapping.role,
                    }
                    for mapping in result.mappings
                ),
                "metadata": result.metadata_dict(),
            }
        )

    return tuple(serialized_results)


def _build_template_environment(
    template_directory: str | Path = DEFAULT_TEMPLATE_DIR,
) -> Environment:
    """Create the Jinja2 environment used for HTML reports."""
    template_path = Path(template_directory)

    if not template_path.exists():
        raise ReportGenerationError(
            f"Template directory was not found: {template_path}"
        )

    if not template_path.is_dir():
        raise ReportGenerationError(
            f"Template path is not a directory: {template_path}"
        )

    return Environment(
        loader=FileSystemLoader(str(template_path)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=True,
            default=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_report_html(
    *,
    organization: dict[str, Any],
    results: Sequence[ControlResult],
    score: ScoreSummary,
    summary: AISummary,
    template_directory: str | Path = DEFAULT_TEMPLATE_DIR,
    template_name: str = DEFAULT_TEMPLATE_NAME,
    generated_at: datetime | None = None,
) -> tuple[str, datetime]:
    """
    Render the complete HTML report without writing it to disk.

    The report uses only already computed deterministic results and score
    information. It does not perform control evaluation or scoring.
    """
    normalized_results = _normalize_results(results)
    organization_metadata = _extract_organization_metadata(
        organization
    )

    if not isinstance(score, ScoreSummary):
        raise ReportGenerationError(
            "The report score must be a ScoreSummary instance."
        )

    if not isinstance(summary, AISummary):
        raise ReportGenerationError(
            "The report summary must be an AISummary instance."
        )

    report_timestamp = (
        generated_at
        if generated_at is not None
        else datetime.now(ZoneInfo("Europe/Athens"))
    )

    if report_timestamp.tzinfo is None:
        raise ReportGenerationError(
            "The report generation timestamp must be timezone-aware."
        )

    environment = _build_template_environment(
        template_directory
    )

    try:
        template = environment.get_template(template_name)
    except TemplateError as exc:
        raise ReportGenerationError(
            f"Could not load report template '{template_name}': {exc}"
        ) from exc

    template_context = {
        "report_title": (
            "AI Assisted Cybersecurity Compliance "
            "Assessment"
        ),
        "organization": organization_metadata,
        "results": _serialize_results(normalized_results),
        "score": {
            "coverage_display": _format_coverage(score),
            "coverage_percentage": score.coverage_percentage,
            "earned_score": score.earned_score,
            "maximum_score": score.maximum_score,
            "total_controls": score.total_controls,
            "assessable_controls": score.assessable_controls,
            "not_assessable_controls": (
                score.not_assessable_controls
            ),
            "status_counts": score.status_counts_dict(),
            "interpretation": score.interpretation,
        },
        "summary": {
            "text": summary.text,
            "source": summary.source,
            "model_name": summary.model_name,
            "disclaimer": summary.disclaimer,
        },
        "generated_at": report_timestamp.strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        ),
    }

    try:
        html = template.render(**template_context)
    except TemplateError as exc:
        raise ReportGenerationError(
            f"Could not render the report template: {exc}"
        ) from exc

    if not html.strip():
        raise ReportGenerationError(
            "The report template produced empty HTML."
        )

    return html, report_timestamp


def generate_report(
    *,
    organization: dict[str, Any],
    results: Sequence[ControlResult],
    score: ScoreSummary,
    summary: AISummary,
    output_directory: str | Path = DEFAULT_REPORTS_DIR,
    template_directory: str | Path = DEFAULT_TEMPLATE_DIR,
    template_name: str = DEFAULT_TEMPLATE_NAME,
    filename: str | None = None,
    write_to_disk: bool = True,
    generated_at: datetime | None = None,
) -> ReportArtifact:
    """
    Generate an HTML report and optionally write it to disk.

    When filename is omitted, a safe filename is derived from the
    organization name and the UTC generation timestamp.
    """
    organization_metadata = _extract_organization_metadata(
        organization
    )

    html, report_timestamp = render_report_html(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        template_directory=template_directory,
        template_name=template_name,
        generated_at=generated_at,
    )

    if filename is None:
        organization_slug = _slugify(
            str(organization_metadata["name"])
        )
        timestamp = report_timestamp.strftime(
            "%Y%m%d-%H%M%S"
        )

        report_filename = (
            f"{organization_slug}-assessment-{timestamp}.html"
        )
    else:
        report_filename = Path(filename).name

        if not report_filename.lower().endswith(".html"):
            report_filename += ".html"

    report_path: Path | None = None

    if write_to_disk:
        output_path = Path(output_directory)

        try:
            output_path.mkdir(
                parents=True,
                exist_ok=True,
            )

            report_path = output_path / report_filename
            report_path.write_text(
                html,
                encoding="utf-8",
            )
        except OSError as exc:
            raise ReportGenerationError(
                f"Could not write report '{report_filename}': {exc}"
            ) from exc

    return ReportArtifact(
        filename=report_filename,
        path=report_path,
        html=html,
        generated_at=report_timestamp,
    )