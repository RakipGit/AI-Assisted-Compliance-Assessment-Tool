"""Streamlit interface for the compliance assessment proof-of-concept."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.ai_summary import AISummaryError, generate_summary
from src.form_adapter import (
    FormInputError,
    build_backup_input,
    build_incident_response_input,
    build_mfa_input,
    build_organization_payload,
    build_patch_input,
)
from src.llm_provider import (
    call_openai,
    get_openai_model,
)
from src.report_generator import (
    ReportGenerationError,
    generate_report,
)
from src.rule_engine import (
    RuleEngineError,
    evaluate_organization,
)
from src.scoring import ScoringError, calculate_score
from src.validator import (
    JSONFileError,
    SchemaValidationError,
    load_json_file,
    load_schema,
    validate_data,
)


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")


SCENARIO_FILES = {
    "Low maturity scenario": DATA_DIR / "scenario_low.json",
    "Partial maturity scenario": DATA_DIR / "scenario_partial.json",
    "Improved maturity scenario": DATA_DIR / "scenario_improved.json",
    "Missing-data scenario": DATA_DIR / "scenario_missing_data.json",
    "Mixed realistic scenario": DATA_DIR / "scenario_mixed.json",
}

STATUS_ICONS = {
    "Satisfied": "✅",
    "Partially Satisfied": "⚠️",
    "Not Satisfied": "❌",
    "Not Assessable": "❔",
}


st.set_page_config(
    page_title="AI-Assisted Compliance Assessment",
    page_icon="🛡️",
    layout="wide",
)


def initialize_session_state() -> None:
    """Initialize Streamlit session-state values."""
    defaults = {
        "organization_data": None,
        "assessment_results": None,
        "score_summary": None,
        "assessment_summary": None,
        "report_artifact": None,
        "source_label": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_assessment_state() -> None:
    """Clear previously generated assessment output."""
    st.session_state.organization_data = None
    st.session_state.assessment_results = None
    st.session_state.score_summary = None
    st.session_state.assessment_summary = None
    st.session_state.report_artifact = None
    st.session_state.source_label = None


@st.cache_data
def load_scenario_file(file_path: str) -> dict[str, Any]:
    """Load one maintained demonstration scenario."""
    return load_json_file(file_path)


@st.cache_resource
def get_schema() -> dict[str, Any]:
    """Load and cache the organization JSON Schema."""
    return load_schema(DATA_DIR / "organization_schema.json")



def run_assessment(
    organization_data: dict[str, Any],
    source_label: str,
) -> None:
    """Validate and process one organization assessment."""
    clear_assessment_state()

    try:
        schema = get_schema()
        validate_data(organization_data, schema)

        results = evaluate_organization(organization_data)
        score = calculate_score(results)

        summary = generate_summary(
            organization=organization_data,
            results=results,
            score=score,
            text_generator=call_openai,
            model_name=get_openai_model(),
            fallback_on_error=True,
        )

        report = generate_report(
            organization=organization_data,
            results=results,
            score=score,
            summary=summary,
            write_to_disk=False,
        )

    except SchemaValidationError as exc:
        st.error("The organization file failed schema validation.")

        for error in exc.errors:
            st.write(f"- {error}")

        return

    except (
        JSONFileError,
        RuleEngineError,
        ScoringError,
        AISummaryError,
        ReportGenerationError,
    ) as exc:
        st.error(f"Assessment could not be completed: {exc}")
        return

    except Exception as exc:
        st.error(
            "An unexpected application error occurred. "
            f"Details: {exc}"
        )
        return

    st.session_state.organization_data = organization_data
    st.session_state.assessment_results = results
    st.session_state.score_summary = score
    st.session_state.assessment_summary = summary
    st.session_state.report_artifact = report
    st.session_state.source_label = source_label

    if summary.fallback_reason:
        st.warning(
            "The AI-generated explanation was temporarily unavailable. "
            "The assessment was completed using the deterministic "
            "fallback explanation."
        )

        with st.expander("Technical details"):
            st.code(summary.fallback_reason)

    st.success("Assessment completed successfully.")


def format_coverage(coverage: float | None) -> str:
    """Return coverage as a presentation string."""
    if coverage is None:
        return "Not calculable"

    return f"{coverage:.2f}%"


def render_sidebar() -> None:
    """Render navigation, methodology and AI-mode controls."""
    with st.sidebar:
        st.title("Assessment Tool")

        st.markdown(
            """
            This proof of concept (PoC) tool performs a preliminary assessment of four
            selected cybersecurity control areas:

            - Multi Factor Authentication
            - Backup and Restore Testing
            - Patch and Vulnerability Management
            - Incident Response Planning and Preparedness
            """
        )

        st.divider()

        st.subheader("Assessment model")

        st.markdown(
            """
            - Your answers are evaluated against predefined control criteria.
            - AI generates the executive explanation of the results.
            - The final score applies only to the four selected controls.
            """
        )

        

        st.divider()

        st.subheader("AI assisted reporting")

        st.markdown(
            """
    Executive explanations are generated automatically using AI.

    """ 
        )
        

        st.caption(
    f"Configured AI model: {get_openai_model()}"
)

        st.warning(
            "This tool does not provide ISO/IEC 27001 certification, "
            "NIS2 legal compliance confirmation, audit assurance or "
            "legal advice."
        )


def render_manual_entry_form() -> dict[str, Any] | None:
    """
    Render a guided form and convert its values through the form adapter.

    Streamlit collects the answers, while ``src.form_adapter`` creates the
    canonical dictionary consumed by schema validation, the deterministic
    rule engine, scoring, summary generation and report generation.
    """
    st.subheader("Organization Profile")

    size_ranges = {
        "Micro (1–9 employees)": ("micro", 1, 9),
        "Small (10–49 employees)": ("small", 10, 49),
        "Medium (50–249 employees)": ("medium", 50, 249),
    }

    name = st.text_input(
        "Organization name",
        key="form_org_name",
    )

    size_label = st.selectbox(
        "Organization size",
        options=list(size_ranges.keys()),
        key="form_org_size",
    )

    size_value, employee_minimum, employee_maximum = (
        size_ranges[size_label]
    )

    employees = st.number_input(
        "Number of employees",
        min_value=employee_minimum,
        max_value=employee_maximum,
        value=employee_minimum,
        step=1,
        key="form_org_employees",
        help=(
            f"Must be between {employee_minimum} and "
            f"{employee_maximum} for the selected size category."
        ),
    )

    sector = st.text_input(
        "Sector (e.g. retail, IT services)",
        key="form_org_sector",
    )

    description = st.text_area(
        "Optional description",
        key="form_org_description",
        height=68,
    )

    st.divider()
    st.subheader("Security Controls")

    st.caption(
        "For each control, select the insufficient-information option "
        "when the answer is unknown. The tool will then return "
        "Not Assessable instead of assuming failure."
    )

    st.caption(
        "For the remaining checkbox questions, checked means Yes and "
        "unchecked means No."
    )

    with st.expander(
        "🔐 Multi Factor Authentication",
        expanded=True,
    ):
        mfa_unknown = st.checkbox(
            "I don't have enough information about MFA",
            key="mfa_unknown",
        )

        mfa_implemented = False
        privileged_accounts_covered = False
        remote_access_covered = False
        mfa_evidence_available = False

        if not mfa_unknown:
            mfa_implemented = (
                st.radio(
                    "Is multi-factor authentication implemented?",
                    ["Yes", "No"],
                    key="mfa_implemented",
                    horizontal=True,
                )
                == "Yes"
            )

            if mfa_implemented:
                privileged_accounts_covered = st.checkbox(
                    "Covers privileged / admin accounts",
                    key="mfa_privileged",
                )

                remote_access_covered = st.checkbox(
                    "Covers remote access "
                    "(VPN, cloud login, etc.)",
                    key="mfa_remote",
                )

            mfa_evidence_available = st.checkbox(
                "I have supporting evidence "
                "(policy, screenshots, config)",
                key="mfa_evidence",
            )

        mfa_data = build_mfa_input(
            unknown=mfa_unknown,
            implemented=mfa_implemented,
            privileged_accounts_covered=(
                privileged_accounts_covered
            ),
            remote_access_covered=remote_access_covered,
            evidence_available=mfa_evidence_available,
        )

    with st.expander(
        "💾 Backup and Restore Testing",
        expanded=True,
    ):
        backup_unknown = st.checkbox(
            "I don't have enough information about backups",
            key="backup_unknown",
        )

        backups_enabled = False
        backup_frequency: str | None = None
        offsite_or_separate_storage = False
        restore_tests_performed = False
        last_restore_test_date = None
        backup_evidence_available = False

        if not backup_unknown:
            backups_enabled = (
                st.radio(
                    "Are backups enabled?",
                    ["Yes", "No"],
                    key="backup_enabled",
                    horizontal=True,
                )
                == "Yes"
            )

            if backups_enabled:
                backup_frequency = st.selectbox(
                    "Backup frequency",
                    [
                        "continuous",
                        "hourly",
                        "daily",
                        "weekly",
                        "monthly",
                        "irregular",
                    ],
                    key="backup_frequency",
                )

                offsite_or_separate_storage = st.checkbox(
                    "Stored separately / off-site from production systems",
                    key="backup_offsite",
                )

                restore_tests_performed = st.checkbox(
                    "Restore tests have been performed",
                    key="backup_restore_tested",
                )

                if restore_tests_performed:
                    last_restore_test_date = st.date_input(
                        "Date of last restore test",
                        key="backup_restore_date",
                    )

            backup_evidence_available = st.checkbox(
                "I have supporting evidence "
                "(backup logs, test reports)",
                key="backup_evidence",
            )

        backup_data = build_backup_input(
            unknown=backup_unknown,
            backups_enabled=backups_enabled,
            backup_frequency=backup_frequency,
            offsite_or_separate_storage=(
                offsite_or_separate_storage
            ),
            restore_tests_performed=restore_tests_performed,
            last_restore_test_date=last_restore_test_date,
            evidence_available=backup_evidence_available,
        )

    with st.expander(
        "🩹 Patch and Vulnerability Management",
        expanded=True,
    ):
        patch_unknown = st.checkbox(
            "I don't have enough information about patch management",
            key="patch_unknown",
        )

        patch_process_defined = False
        vulnerability_scanning_enabled = False
        critical_patch_deadline_days: int | None = None
        unsupported_software_present = False
        patch_status_reviewed = False
        patch_evidence_available = False

        if not patch_unknown:
            patch_process_defined = (
                st.radio(
                    "Is a patch-management process defined?",
                    ["Yes", "No"],
                    key="patch_process_defined",
                    horizontal=True,
                )
                == "Yes"
            )

            if patch_process_defined:
                vulnerability_scanning_enabled = st.checkbox(
                    "Vulnerability scanning is enabled",
                    key="patch_scanning",
                )

                critical_patch_deadline_days = int(
                    st.number_input(
                        "Target deadline for critical patches (days)",
                        min_value=0,
                        max_value=365,
                        value=30,
                        step=1,
                        key="patch_deadline",
                    )
                )

                unsupported_software_present = st.checkbox(
                    "Unsupported / end-of-life software is present",
                    key="patch_unsupported",
                )

                patch_status_reviewed = st.checkbox(
                    "Patch status is periodically reviewed",
                    key="patch_reviewed",
                )

            patch_evidence_available = st.checkbox(
                "I have supporting evidence "
                "(scan reports, patch logs)",
                key="patch_evidence",
            )

        patch_data = build_patch_input(
            unknown=patch_unknown,
            process_defined=patch_process_defined,
            vulnerability_scanning_enabled=(
                vulnerability_scanning_enabled
            ),
            critical_patch_deadline_days=(
                critical_patch_deadline_days
            ),
            unsupported_software_present=(
                unsupported_software_present
            ),
            patch_status_reviewed=patch_status_reviewed,
            evidence_available=patch_evidence_available,
        )

    with st.expander(
        "🚨 Incident Response Planning and Preparedness",
        expanded=True,
    ):
        incident_unknown = st.checkbox(
            "I don't have enough information about incident response",
            key="incident_unknown",
        )

        incident_plan_exists = False
        incident_roles_defined = False
        communication_procedure_defined = False
        reporting_procedure_defined = False
        incident_plan_tested = False
        last_incident_test_date = None
        incident_evidence_available = False

        if not incident_unknown:
            incident_plan_exists = (
                st.radio(
                    "Does an incident-response plan exist?",
                    ["Yes", "No"],
                    key="incident_plan_exists",
                    horizontal=True,
                )
                == "Yes"
            )

            if incident_plan_exists:
                incident_roles_defined = st.checkbox(
                    "Roles and responsibilities are defined",
                    key="incident_roles",
                )

                communication_procedure_defined = st.checkbox(
                    "Communication procedures are defined",
                    key="incident_comms",
                )

                reporting_procedure_defined = st.checkbox(
                    "Reporting procedures are defined",
                    key="incident_reporting",
                )

                incident_plan_tested = st.checkbox(
                    "The plan has been tested",
                    key="incident_tested",
                )

                if incident_plan_tested:
                    last_incident_test_date = st.date_input(
                        "Date of last test",
                        key="incident_test_date",
                    )

            incident_evidence_available = st.checkbox(
                "I have supporting evidence "
                "(exercise reports, minutes)",
                key="incident_evidence",
            )

        incident_data = build_incident_response_input(
            unknown=incident_unknown,
            plan_exists=incident_plan_exists,
            roles_defined=incident_roles_defined,
            communication_procedure_defined=(
                communication_procedure_defined
            ),
            reporting_procedure_defined=(
                reporting_procedure_defined
            ),
            plan_tested=incident_plan_tested,
            last_test_date=last_incident_test_date,
            evidence_available=incident_evidence_available,
        )

    st.divider()

    if st.button(
        "Validate and assess this organization",
        type="primary",
        key="assess_manual_form",
    ):
        try:
            return build_organization_payload(
                name=name,
                size=size_value,
                employees=int(employees),
                sector=sector,
                description=description,
                mfa=mfa_data,
                backup=backup_data,
                patch_management=patch_data,
                incident_response=incident_data,
            )
        except FormInputError as exc:
            st.error(str(exc))
            return None

    return None


def render_input_section() -> None:
    """Render manual-entry and demonstration-scenario controls."""
    st.header("1. Organization Input")

    st.write(
        "Complete the guided assessment form or use one of the "
        "maintained demonstration scenarios."
    )

    manual_tab, scenario_tab = st.tabs(
        [
            "Fill out a form",
            "Use demonstration scenario",
        ]
    )

    with manual_tab:
        organization_data = render_manual_entry_form()

        if organization_data is not None:
            run_assessment(
                organization_data=organization_data,
                source_label="Manual form entry",
            )

    with scenario_tab:
        scenario_name = st.selectbox(
            "Select a synthetic scenario",
            options=list(SCENARIO_FILES.keys()),
            index=4,
        )

        selected_path = SCENARIO_FILES[scenario_name]

        with st.expander("Preview selected scenario"):
            scenario_preview = load_scenario_file(
                str(selected_path)
            )
            st.json(scenario_preview)

        if st.button(
            "Run selected demonstration scenario",
            type="primary",
            key="assess_demo_scenario",
        ):
            scenario_data = load_scenario_file(
                str(selected_path)
            )

            run_assessment(
                organization_data=scenario_data,
                source_label=selected_path.name,
            )
            

def render_organization_profile(
    organization_data: dict[str, Any],
) -> None:
    """Render organization metadata."""
    organization = organization_data["organization"]

    st.header("2. Organization Profile")

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "Organization",
        organization["name"],
    )

    column_2.metric(
        "Employee-based size",
        str(organization["size"]).title(),
    )

    column_3.metric(
        "Employees",
        organization["employees"],
    )

    column_4.metric(
        "Sector",
        organization["sector"],
    )

    description = organization.get("description")

    if description:
        st.info(description)


def render_score_summary(score: Any) -> None:
    """Render assessment score and status distribution."""
    st.header("3. Assessment Summary")

    coverage_column, assessable_column, earned_column = st.columns(3)

    coverage_column.metric(
        "Selected-controls coverage",
        format_coverage(score.coverage_percentage),
    )

    assessable_column.metric(
        "Assessable controls",
        f"{score.assessable_controls}/{score.total_controls}",
    )

    earned_column.metric(
        "Earned score",
        f"{score.earned_score}/{score.maximum_score}",
    )

    st.caption(
        "The percentage is a researcher-defined internal indicator for "
        "the four selected controls. It is not an official ISO/IEC 27001 "
        "or NIS2 compliance score."
    )

    status_counts = score.status_counts_dict()
    status_columns = st.columns(4)

    status_columns[0].metric(
        "Satisfied",
        status_counts["Satisfied"],
    )

    status_columns[1].metric(
        "Partially Satisfied",
        status_counts["Partially Satisfied"],
    )

    status_columns[2].metric(
        "Not Satisfied",
        status_counts["Not Satisfied"],
    )

    status_columns[3].metric(
        "Not Assessable",
        status_counts["Not Assessable"],
    )

    st.info(score.interpretation)


def build_results_dataframe(results: Any) -> pd.DataFrame:
    """Convert results into a compact summary dataframe."""
    rows = []

    for result in results:
        rows.append(
            {
                "Control": result.control_name,
                "Status": result.status.value,
                "Score": (
                    result.numeric_score
                    if result.numeric_score is not None
                    else "Excluded"
                ),
                "Assessable": (
                    "Yes"
                    if result.is_assessable
                    else "No"
                ),
            }
        )

    return pd.DataFrame(rows)


def render_detailed_results(results: Any) -> None:
    """Render summary and expanded deterministic results."""
    st.header("4. Detailed Control Results")

    results_dataframe = build_results_dataframe(results)

    st.dataframe(
        results_dataframe,
        use_container_width=True,
        hide_index=True,
    )

    for result in results:
        status_icon = STATUS_ICONS.get(
            result.status.value,
            "•",
        )

        with st.expander(
            f"{status_icon} {result.control_name} "
            f"— {result.status.value}",
            expanded=True,
        ):
            st.markdown("#### Deterministic rationale")
            st.write(result.rationale)

            recommendation_column, evidence_column = st.columns(2)

            with recommendation_column:
                st.markdown("#### Recommendations")

                if result.recommendations:
                    for recommendation in result.recommendations:
                        st.write(f"- {recommendation}")
                else:
                    st.write(
                        "No additional remediation recommendation "
                        "was generated."
                    )

            with evidence_column:
                st.markdown("#### Evidence observations")

                if result.evidence:
                    for observation in result.evidence:
                        st.write(f"- {observation}")
                else:
                    st.write(
                        "No evidence observation was available."
                    )

            st.markdown("#### Framework mappings")

            mapping_rows = [
                {
                    "Framework": mapping.framework,
                    "Reference": mapping.reference,
                    "Short title": mapping.title,
                    "Role": mapping.role.title(),
                }
                for mapping in result.mappings
            ]

            if mapping_rows:
                st.dataframe(
                    pd.DataFrame(mapping_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.write(
                    "No framework mappings were available."
                )

            assessment_scope = result.metadata_dict().get(
                "assessment_scope"
            )

            if assessment_scope:
                st.markdown("#### Assessment scope")
                st.write(assessment_scope)


def render_summary(summary: Any) -> None:
    """Render AI-assisted or deterministic fallback explanation."""
    st.header("5. Executive Explanation")

    source_display = {
        "ai": "AI-generated explanation",
        "deterministic-fallback": (
            "Deterministic fallback explanation"
        ),
    }.get(summary.source, summary.source)

    st.caption(f"Summary source: {source_display}")

    if summary.model_name:
        st.caption(f"AI model: {summary.model_name}")

    if summary.fallback_reason:
        st.warning(
            "The requested AI explanation could not be generated. "
            "The explanation below was produced by the deterministic "
            "fallback mechanism."
        )

        with st.expander("Technical fallback information"):
            st.code(summary.fallback_reason)

    st.text(summary.text)
    st.warning(summary.disclaimer)


def render_report_download(report: Any) -> None:
    """Render the HTML report download action."""
    st.header("6. Download Report")

    st.write(
        "Download a standalone HTML report containing the deterministic "
        "results, coverage summary, framework mappings and explanation."
    )

    st.download_button(
        label="Download HTML assessment report",
        data=report.html.encode("utf-8"),
        file_name=report.filename,
        mime="text/html",
        type="primary",
        use_container_width=True,
    )


def render_completed_assessment() -> None:
    """Render all sections of a completed assessment."""
    organization_data = st.session_state.organization_data
    results = st.session_state.assessment_results
    score = st.session_state.score_summary
    summary = st.session_state.assessment_summary
    report = st.session_state.report_artifact

    if any(
        value is None
        for value in (
            organization_data,
            results,
            score,
            summary,
            report,
        )
    ):
        st.info(
            "Complete the assessment form or run a demonstration scenario  "
            "to begin."
        )
        return

    render_organization_profile(organization_data)
    render_score_summary(score)
    render_detailed_results(results)
    render_summary(summary)
    render_report_download(report)


def main() -> None:
    """Run the Streamlit application."""
    initialize_session_state()
    render_sidebar()

    st.title(
        "AI-Assisted Cybersecurity Compliance Assessment"
    )

    st.markdown(
        """
        This prototype supports a preliminary assessment of four selected
        cybersecurity-control areas mapped to ISO/IEC 27001:2022 and NIS2.

        The assessment statuses and score are produced by deterministic
        rules. The explanation layer does not determine or modify those
        results.
        """
    )

    st.divider()

    render_input_section()

    st.divider()

    render_completed_assessment()


if __name__ == "__main__":
    main()