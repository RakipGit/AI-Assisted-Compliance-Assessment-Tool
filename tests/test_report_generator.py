"""Tests for HTML assessment report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ai_summary import generate_summary
from src.report_generator import (
    ReportGenerationError,
    generate_report,
)
from src.rule_engine import evaluate_organization
from src.scoring import calculate_score
from src.validator import load_json_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture
def mixed_report_inputs():
    """Return complete report inputs for the mixed scenario."""
    organization = load_json_file(
        DATA_DIR / "scenario_mixed.json"
    )
    results = evaluate_organization(organization)
    score = calculate_score(results)

    summary = generate_summary(
        organization=organization,
        results=results,
        score=score,
    )

    return organization, results, score, summary


def test_report_contains_expected_assessment_content(
    mixed_report_inputs,
) -> None:
    """The report must include the fixed scenario results."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    report = generate_report(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        write_to_disk=False,
        generated_at=datetime(
            2026,
            7,
            21,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert report.path is None
    assert "62.50%" in report.html
    assert "Mediterranean Business Solutions" in report.html
    assert "Multi-Factor Authentication" in report.html
    assert "Backup and Restore Testing" in report.html
    assert "Patch and Vulnerability Management" in report.html
    assert (
        "Incident Response Planning and Preparedness"
        in report.html
    )
    assert "Article 21(2)(j)" in report.html
    assert "A.8.5" in report.html


def test_report_does_not_change_deterministic_results(
    mixed_report_inputs,
) -> None:
    """Report rendering must not modify statuses or scores."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    statuses_before = tuple(
        result.status
        for result in results
    )
    coverage_before = score.coverage_percentage

    generate_report(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        write_to_disk=False,
    )

    statuses_after = tuple(
        result.status
        for result in results
    )

    assert statuses_after == statuses_before
    assert score.coverage_percentage == coverage_before


def test_report_escapes_user_controlled_html(
    mixed_report_inputs,
) -> None:
    """User-provided HTML must be escaped rather than executed."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    organization["organization"]["name"] = (
        "<script>alert('test')</script>"
    )

    report = generate_report(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        write_to_disk=False,
    )

    assert "<script>" not in report.html
    assert "&lt;script&gt;" in report.html


def test_report_can_be_written_to_disk(
    mixed_report_inputs,
    tmp_path: Path,
) -> None:
    """The report generator must produce a UTF-8 HTML file."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    report = generate_report(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        output_directory=tmp_path,
        filename="assessment-test.html",
    )

    assert report.path == tmp_path / "assessment-test.html"
    assert report.path.exists()
    assert report.path.read_text(
        encoding="utf-8"
    ) == report.html


def test_duplicate_report_results_are_rejected(
    mixed_report_inputs,
) -> None:
    """The same control must not be rendered twice."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    with pytest.raises(
        ReportGenerationError,
        match="Duplicate control results",
    ):
        generate_report(
            organization=organization,
            results=(results[0], results[0]),
            score=score,
            summary=summary,
            write_to_disk=False,
        )


def test_report_filename_is_sanitized(
    mixed_report_inputs,
) -> None:
    """Generated filenames must not use unsafe organization characters."""
    organization, results, score, summary = (
        mixed_report_inputs
    )

    organization["organization"]["name"] = (
        "Example / Organization: Test"
    )

    report = generate_report(
        organization=organization,
        results=results,
        score=score,
        summary=summary,
        write_to_disk=False,
        generated_at=datetime(
            2026,
            7,
            21,
            12,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert report.filename == (
        "example-organization-test-"
        "assessment-20260721-123000.html"
    )