"""AI-assisted explanation layer for deterministic assessment results.

This module does not evaluate security controls and does not calculate
coverage scores. It receives immutable deterministic results and may use
an external text-generation function only to explain those results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .models import ControlResult
from .scoring import ScoreSummary


TextGenerator = Callable[[str], str]


class AISummaryError(ValueError):
    """Raised when an AI-assisted summary cannot be generated safely."""


class AIIntegrityError(RuntimeError):
    """Raised if deterministic results change during summary generation."""


@dataclass(frozen=True)
class AISummary:
    """Immutable textual summary of a deterministic assessment."""

    text: str
    source: str
    model_name: str | None
    disclaimer: str
    fallback_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("AI summary text must not be empty.")

        if self.source not in {"ai", "deterministic-fallback"}:
            raise ValueError(
                "Summary source must be either 'ai' or "
                "'deterministic-fallback'."
            )

        if self.model_name is not None:
            if (
                not isinstance(self.model_name, str)
                or not self.model_name.strip()
            ):
                raise ValueError(
                    "Model name must be None or a non-empty string."
                )

        if (
            not isinstance(self.disclaimer, str)
            or not self.disclaimer.strip()
        ):
            raise ValueError(
                "AI summary disclaimer must not be empty."
            )

        if self.fallback_reason is not None:
            if (
                not isinstance(self.fallback_reason, str)
                or not self.fallback_reason.strip()
            ):
                raise ValueError(
                    "Fallback reason must be None or non-empty text."
                )

        if self.source == "ai" and self.fallback_reason is not None:
            raise ValueError(
                "An AI-generated summary cannot contain a fallback reason."
            )


SUMMARY_DISCLAIMER = (
    "This explanation is based on deterministic prototype results and "
    "self-reported input. It does not constitute ISO/IEC 27001 "
    "certification, NIS2 legal compliance confirmation, audit assurance "
    "or legal advice."
)


def _result_fingerprint(
    results: Sequence[ControlResult],
) -> tuple[tuple[Any, ...], ...]:
    """Create a stable snapshot of deterministic assessment results."""
    return tuple(
        (
            result.control_id,
            result.control_name,
            result.status,
            result.rationale,
            result.recommendations,
            result.evidence,
            result.mappings,
            result.metadata,
            result.numeric_score,
            result.is_assessable,
        )
        for result in results
    )


def _validate_results(
    results: tuple[ControlResult, ...] | list[ControlResult],
) -> tuple[ControlResult, ...]:
    """Validate and normalize deterministic assessment results."""
    normalized_results = tuple(results)

    if not normalized_results:
        raise AISummaryError(
            "At least one ControlResult is required to generate a summary."
        )

    if not all(
        isinstance(result, ControlResult)
        for result in normalized_results
    ):
        raise AISummaryError(
            "Every summary input must be a ControlResult instance."
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
        raise AISummaryError(
            "Duplicate control results were provided: "
            + ", ".join(duplicate_ids)
        )

    return normalized_results


def _format_coverage(score: ScoreSummary) -> str:
    """Return a safe textual representation of coverage."""
    if score.coverage_percentage is None:
        return "Not calculable"

    return f"{score.coverage_percentage:.2f}%"


def _format_mapping_references(result: ControlResult) -> str:
    """Return framework mappings as concise references."""
    if not result.mappings:
        return "No mappings available"

    return ", ".join(
        f"{mapping.framework} {mapping.reference}"
        for mapping in result.mappings
    )


def build_ai_prompt(
    *,
    organization: dict[str, Any],
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
) -> str:
    """
    Build a constrained executive-level prompt from deterministic
    cybersecurity compliance assessment results.
    """
    normalized_results = _validate_results(results)

    organization_data = organization.get(
        "organization",
        organization,
    )

    if not isinstance(organization_data, dict):
        raise AISummaryError(
            "Organization metadata must be provided as an object."
        )

    organization_name = organization_data.get(
        "name",
        "Unnamed organization",
    )
    organization_size = organization_data.get(
        "size",
        "Not specified",
    )
    employees = organization_data.get(
        "employees",
        "Not specified",
    )
    sector = organization_data.get(
        "sector",
        "Not specified",
    )

    result_sections: list[str] = []

    for result in normalized_results:
        recommendations = (
            "\n".join(
                f"- {recommendation}"
                for recommendation in result.recommendations
            )
            if result.recommendations
            else "- No additional recommendation was generated."
        )

        evidence = (
            "\n".join(
                f"- {observation}"
                for observation in result.evidence
            )
            if result.evidence
            else "- No evidence observation is available."
        )

        framework_mappings = (
            "\n".join(
                (
                    f"- {mapping.framework} {mapping.reference}: "
                    f"{mapping.title}"
                    + (
                        f" ({mapping.role} mapping)"
                        if mapping.role
                        else ""
                    )
                )
                for mapping in result.mappings
            )
            if result.mappings
            else "- No framework mapping is available."
        )

        assessment_scope = (
            result.metadata_dict().get("assessment_scope")
            or "No additional scope statement is available."
        )

        result_sections.append(
            "\n".join(
                (
                    f"Control area: {result.control_name}",
                    f"Assessment status: {result.status.value}",
                    f"Assessment finding: {result.rationale}",
                    "",
                    "Supported recommendations:",
                    recommendations,
                    "",
                    "Evidence information:",
                    evidence,
                    "",
                    "Framework context:",
                    framework_mappings,
                    "",
                    f"Assessment scope: {assessment_scope}",
                )
            )
        )

    controls_text = "\n\n---\n\n".join(result_sections)

    return f"""
You are a senior cybersecurity compliance and GRC professional with
expertise in ISO/IEC 27001:2022 and the NIS2 Directive.

You are preparing the executive explanation for a proof-of-concept
cybersecurity compliance assessment tool intended to provide management
with a concise, professional interpretation of selected cybersecurity
control findings.

The tool evaluates the following four selected cybersecurity control areas:

- Multi Factor Authentication
- Backup and Restore Testing
- Vulnerability Management
- Incident Response Planning and Preparedness

These control areas are mapped to relevant requirements of
ISO/IEC 27001:2022 and Directive (EU) 2022/2555 (NIS2).

The assessment intentionally covers only these four selected areas.
It does not assess the complete scope of ISO/IEC 27001:2022 or NIS2,
and the supplied mappings represent the interpretation adopted by this
proof-of-concept rather than an official ISO/IEC-NIS2 crosswalk.

The cybersecurity assessment itself has already been completed using
predefined assessment criteria. You are not performing a new assessment.
Your role is to interpret, synthesize and communicate the supplied results
in a clear management-level explanation.

Your writing should resemble a concise executive advisory note prepared
by an experienced cybersecurity compliance or GRC professional. It should
be coherent, natural and professionally written, with clear progression
between sentences and sections. Avoid mechanical, checklist-like or
formulaic writing.


STYLE AND COHERENCE RULES:

- Write in natural, human-sounding professional prose.

- Prefer smooth, connected sentences with clear transitions between ideas.

- Never use the semicolon character ";" anywhere in the generated report
content, including the Overview, Management Interpretation, Priority
Actions and Information Gap sections. When separating related ideas or
multiple information items, use commas, conjunctions or separate
sentences instead. Also do not use em dashes.

- When a sentence contains multiple distinct ideas, either connect them
  naturally if the sentence remains clear, or divide them into separate
  sentences in a way that preserves flow and coherence.

- Avoid choppy writing made up of many short standalone sentences. Each
  paragraph should read as one unified piece of professional writing with
  a clear beginning, logical development and natural conclusion.

- Do not sacrifice readability for brevity. A slightly longer,
  well-structured sentence is preferable to several abrupt sentences
  that sound mechanical or generated.

- Use natural transitional language where appropriate so that one idea
  leads logically into the next.

- Avoid mechanical phrases such as "highest-priority finding",
  "Not Satisfied finding", "as recommended" or similar wording that
  exposes the assessment mechanics.

- Avoid unnecessary repetition of the same control name, concept or
  keyword within the same paragraph or adjacent sentences.

- When multiple recommendations belong to the same control area, combine
  them into one coherent management action where this improves clarity.

- Prefer a small number of strong, well-developed priority actions over
  weak, repetitive or artificially created actions.

- Do not invent sequencing such as delaying one action until another is
  underway unless the supplied recommendations explicitly require that.

- Avoid unsupported concepts such as recovery objectives, maturity levels
  or effectiveness claims unless they are directly supported by the
  supplied assessment findings.

- Use status wording naturally inside prose. For example, write
  "not assessable" within a sentence rather than mechanically reproducing
  title-case status labels.

- Use concise but meaningful professional language. Avoid vague,
  unnecessarily abstract or overly corporate expressions when a clearer
  formulation is available.

- Do not use ISO/IEC 27001 or NIS2 references as filler language.

- Do not describe the assessment inside the executive explanation using
  expressions such as "limited NIS2/ISO context", "specific NIS2 and ISO
  context considered", "narrow scope", "restricted context" or similar
  wording that unnecessarily weakens the presentation of the assessment.

- The scope and methodological limitations are documented elsewhere in
  the report. Within the executive explanation, mention ISO/IEC 27001:2022
  or NIS2 only when the reference adds clear professional value to the
  interpretation of the supplied findings.


NON-NEGOTIABLE RULES:

1. Treat every supplied assessment status, finding and score as
   authoritative and final.

2. Do not change, reinterpret, override or recalculate any assessment
   status, score or finding.

3. Do not independently assess controls or determine whether requirements
   have been satisfied beyond the supplied findings.

4. A Not Assessable result means that sufficient information was not
   available to assess that control area. It must never be presented as
   evidence of control failure.

5. Do not claim that the organization is ISO/IEC 27001 compliant,
   NIS2 compliant, certified, audit-ready or legally compliant.

6. Do not infer overall framework compliance from the assessment score or
   from the status of the four selected controls.

7. Do not invent or assume evidence, policies, technologies, procedures,
   incidents, risks, controls, organizational practices or implementation
   details that are not contained in the supplied assessment information.

8. Do not create new remediation requirements or recommendations.
   Priority actions must be based only on the supplied recommendations.

9. You may consolidate, prioritize and professionally rephrase the
   supplied recommendations, provided that their original meaning is
   preserved.

10. For Satisfied controls, use only the supplied maintenance
    recommendations. Do not introduce new optimization advice, additional
    safeguards or changes to existing thresholds, targets, frequencies or
    control design unless those changes are explicitly contained in the
    supplied recommendations.

11. When all assessed controls are Satisfied, do not invent a deficiency,
    limitation, shortfall or improvement requirement merely to create
    contrast in the executive explanation. Present the positive assessment
    picture and focus any Priority Actions on the supplied maintenance
    recommendations.

12. When all controls are Not Assessable, do not infer missing documents,
    artifacts, evidence-collection processes, governance failures or
    control deficiencies. State only that sufficient information was not
    available to assess the selected control areas. Do not convert this
    lack of information into evidence that the underlying controls,
    processes, ownership or documentation are absent.

13. When all controls are Not Assessable, do not generate remediation-style
    Priority Actions merely to make the report appear actionable. In this
    scenario, the Information Gap section should carry the main guidance
    and should describe only additional information explicitly supported
    by the supplied findings or recommendations.

14. You may use your knowledge of ISO/IEC 27001:2022 and NIS2 only to
    improve professional terminology, context and explanation. Do not use
    external framework knowledge to introduce additional findings,
    obligations, deficiencies or legal conclusions.

15. Use the supplied framework mappings only as contextual references.
    Do not infer additional framework coverage or compliance conclusions
    from those mappings.

16. Respect the supplied assessment scope for each control. Do not imply
    that a control assessment covers broader areas of ISO/IEC 27001:2022
    or NIS2 than those explicitly described.

17. Do not display, mention or infer internal control identifiers,
    backend keys, variable names or implementation details.

18. Do not use terms such as "deterministic", "rule engine",
    "fixed status", "fixed score", "control ID", "backend" or similar
    implementation terminology in the executive explanation.

19. Do not repeat the Detailed Control Results section. The executive
    explanation must synthesize the findings and add management-level
    interpretation rather than restating every individual result.

20. Evidence availability in this assessment is based on the information
    provided by the user. Do not state or imply that evidence was
    independently reviewed, validated or verified.

21. Avoid unsupported statements about organizational risk, maturity,
    readiness or effectiveness. If such concepts are discussed, they must
    follow directly and cautiously from the supplied findings.

22. For a Not Assessable control, do not infer which documents,
    evidence, procedures, practices or implementation elements are absent.
    State only that sufficient information was not available unless the
    supplied assessment finding explicitly identifies a specific missing
    item.

23. Do not infer control ownership, delegation, operational effectiveness,
    proven outcomes, risk reduction or organizational readiness unless
    those conclusions are directly supported by the supplied assessment
    findings.

24. Do not infer the organization's size, operating model or organizational
    structure from the number of employees. If organizational size is
    mentioned, use only the explicitly supplied Organization size value.
    The employee count may be used only as factual context and must not be
    translated into labels such as "small IT operation", "small company"
    or similar descriptions unless that characterization is explicitly
    supplied.

25. Use the assessment score only as supporting context if it materially
    helps the explanation. Do not describe the score as a percentage of
    ISO/IEC 27001 compliance, NIS2 compliance or overall cybersecurity
    maturity.

26. Avoid repetition between sections. Each section must provide a
    distinct purpose and add new value.

27. Maintain logical continuity. The Overview should establish the
    overall picture, the Management Interpretation should explain its
    significance, and the Priority Actions should follow naturally from
    that interpretation when Priority Actions are appropriate.

28. Write in professional, fluent English suitable for inclusion in a
    university thesis proof-of-concept report and for presentation to
    organizational management.

29. Keep the complete executive explanation concise, normally around
    300 to 450 words depending on the number of assessable controls and
    whether an Information Gap section is required.

30. Produce only the requested report content. Do not explain your
    instructions, your reasoning process or how the text was generated.


ORGANIZATION CONTEXT:

Organization: {organization_name}
Organization size: {organization_size}
Number of employees: {employees}
Sector: {sector}


ASSESSMENT SUMMARY:

Selected-control assessment score: {_format_coverage(score)}
Earned points: {score.earned_score} out of {score.maximum_score}
Total selected controls: {score.total_controls}
Assessable controls: {score.assessable_controls}
Not Assessable controls: {score.not_assessable_controls}


AUTHORITATIVE ASSESSMENT FINDINGS:

{controls_text}


REQUIRED OUTPUT STRUCTURE:

Overview

Write one coherent paragraph of approximately 90 to 120 words.

Present the overall picture emerging from the assessment in management
language.

When at least one control is assessable, identify the strongest assessed
area and, only when the supplied findings contain an actual gap, describe
the most significant improvement area or information limitation.

If all assessed controls are Satisfied, do not invent a shortfall,
limitation or broader scope concern. Instead, summarize the established
strengths and the overall consistency of the assessed controls.

If all controls are Not Assessable, do not identify a strongest or weakest
area. Explain that sufficient information was not available to form
control-level conclusions and make clear that this is an information
limitation rather than evidence of control failure.

Do not simply list the four control statuses. Connect the findings into a
natural narrative that allows a manager to understand the overall position
of the organization within the assessment scope.

A broader interpretation of the organization's security position is
acceptable when it follows logically from the supplied findings, but it
must remain clearly grounded in the four assessed control areas.


Management Interpretation

Write one coherent paragraph of approximately 90 to 120 words.

This section must add interpretation rather than repeat the Overview.

Explain what the combined findings mean from a cybersecurity governance,
control management and compliance assessment perspective.

Where supported by the supplied findings, discuss implications for
management oversight, ownership, documented processes, consistency of
control operation and verification activities. Do not introduce any of
these concepts when the supplied findings do not support them.

Use individual control results as supporting context for this
interpretation rather than simply describing their statuses again.

Explain the relationship between established controls, identified gaps
and incomplete assurance where such gaps exist. If all assessed controls
are Satisfied, focus instead on the significance of maintaining the
established controls and verification activities without inventing a new
weakness.

If all controls are Not Assessable, focus on the limitation created by
insufficient information. Do not infer that documentation, ownership,
evidence collection, governance processes or control activities are
missing. Explain only that the available information does not support a
reliable assessment of implementation or operation.

The paragraph should provide a clear management takeaway. It should help
the reader understand why the combination of findings matters and what
type of governance or control-management attention is appropriate.

Avoid vague or unnecessarily abstract expressions such as "selective
maturity", "lifecycle controls" or similar terminology unless the meaning
is clear, specific and directly supported by the findings.

Where useful, use the supplied ISO/IEC 27001:2022 and NIS2 mappings to
provide accurate professional context, but do not turn this section into a
framework-by-framework analysis and do not make additional compliance
claims.

Do not use phrases such as "limited NIS2/ISO context", "specific NIS2 and
ISO context considered" or similar framework-related filler. If a
framework reference does not add substantive value to the management
interpretation, omit it.


Priority Actions

Provide up to three priority actions based on the supplied remediation
or maintenance recommendations. Use fewer than three actions when the
assessment does not contain enough distinct findings or maintenance
recommendations to justify three meaningful actions. Do not create an
action merely to reach a target number.

If all controls are Not Assessable, omit the Priority Actions section
unless a supplied recommendation clearly represents a distinct management
action that can be presented without implying that a control has failed.
In the normal all-Not-Assessable case, use the Information Gap section
instead of creating remediation actions.

Prioritize actions according to the seriousness of the supplied findings.
Controls marked Not Satisfied should normally receive the greatest
attention, followed by relevant gaps in Partially Satisfied controls.

When all assessed controls are Satisfied, Priority Actions must be
maintenance-oriented and derived only from the supplied maintenance
recommendations. Do not create new improvement requirements or advise
changes to existing thresholds, targets, frequencies or control design
unless the supplied recommendations explicitly state them.

When several recommendations relate to the same control area, combine
them into one coherent action rather than splitting them into multiple
similar actions.

A Not Assessable control must be treated as an information gap, not as a
remediation failure.

Do not use a Not Assessable control as a remediation Priority Action.
Address missing information for such controls in the Information Gap
section instead. A Not Assessable control may only be mentioned in
Priority Actions if the supplied recommendation itself represents a
distinct management action and can be presented without implying that the
control has failed.

Each numbered action must contain:
- a short professional action heading; and
- one coherent paragraph of one or two connected sentences.

Each action should read as a short piece of professional management
guidance rather than as a compressed list of commands.

Use complete, naturally connected sentences. Explain what should be
addressed, how the supplied recommendations relate to that objective and
why the action matters within the assessed scope.

Do not use semicolons to connect separate ideas. Where necessary, use a
natural transition or a separate sentence while preserving the flow of
the paragraph.

Base every action strictly on the supplied recommendations. Do not invent
additional activities, dependencies, timelines, sequencing or objectives.

Avoid mechanical phrases such as "this addresses the Not Satisfied
finding" or "as recommended". Communicate the significance of the action
naturally instead.

Do not end priority actions with generic references such as "within the
NIS2 and ISO context", "in line with the mapped frameworks" or similar
phrasing. Mention a framework only when a specific supplied mapping adds
direct and meaningful context to that action.

Where a Satisfied control has an explicit maintenance recommendation, it
may appear as a lower-priority maintenance action if appropriate.


Information Gap

Include this section only when at least one control is not assessable.

Write one short, coherent and natural explanatory paragraph using the
human-readable control name or names.

Explain what additional information would help provide a more complete
assessment of that area, based only on the supplied findings and
recommendations.

For a Not Assessable control, do not assume that specific documents,
evidence, procedures or practices are absent unless the supplied finding
explicitly says so. Describe the issue as insufficient information and
refer only to additional information that is supported by the supplied
recommendation.

When all controls are Not Assessable, this section should contain the main
practical guidance. Keep the guidance focused on obtaining sufficient
information for future assessment. Do not prescribe new policies,
inventories, signed documents, evidence-collection programs, testing
artifacts or governance processes unless they are explicitly supported by
the supplied recommendations.

Describe the missing information in a way that is useful to management,
rather than as a rigid procedural requirement.

Do not use wording such as "this information is required to complete the
assessment". Prefer natural language explaining that additional
information would allow a more complete or better-supported assessment
of the affected area.

Make clear that the absence of sufficient information limits the level of
assurance that can be drawn from the assessment, but does not constitute
evidence of control failure.

Write this as a normal professional paragraph with connected ideas.
Do not use semicolons, em dashes or mechanical status-label phrasing.


Do not add a separate Scope Limitation, Disclaimer, Methodology,
Framework Mapping, Evidence or Conclusion section. Those elements are
already represented elsewhere in the report.
""".strip()

def generate_deterministic_fallback(
    *,
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
) -> str:
    """
    Generate a structured non-AI executive explanation from the
    deterministic assessment results.
    """
    normalized_results = _validate_results(results)

    satisfied = [
        result
        for result in normalized_results
        if result.status.value == "Satisfied"
    ]

    partially_satisfied = [
        result
        for result in normalized_results
        if result.status.value == "Partially Satisfied"
    ]

    not_satisfied = [
        result
        for result in normalized_results
        if result.status.value == "Not Satisfied"
    ]

    not_assessable = [
        result
        for result in normalized_results
        if result.status.value == "Not Assessable"
    ]

    lines: list[str] = [
        "Overview",
    ]

    overview_parts: list[str] = []

    if satisfied:
        satisfied_names = ", ".join(
            result.control_name
            for result in satisfied
        )
        overview_parts.append(
            "The assessment identified established controls in "
            f"{satisfied_names}."
        )

    if not_satisfied:
        not_satisfied_names = ", ".join(
            result.control_name
            for result in not_satisfied
        )
        overview_parts.append(
            "The most significant improvement requirement concerns "
            f"{not_satisfied_names}, where the assessed criteria were "
            "not satisfied."
        )

    if partially_satisfied:
        partial_names = ", ".join(
            result.control_name
            for result in partially_satisfied
        )
        overview_parts.append(
            f"{partial_names} was assessed as partially satisfied, "
            "indicating that some required elements are present but "
            "additional improvement is needed."
        )

    if not_assessable:
        not_assessable_names = ", ".join(
            result.control_name
            for result in not_assessable
        )
        overview_parts.append(
            "The assessment of "
            f"{not_assessable_names} could not be completed because "
            "sufficient information was not available."
        )

    if not overview_parts:
        overview_parts.append(
            "The assessment did not produce sufficient information for "
            "a broader executive interpretation."
        )

    lines.append(" ".join(overview_parts))

    lines.extend(
        (
            "",
            "Management Interpretation",
        )
    )

    interpretation_parts: list[str] = []

    if not_satisfied:
        interpretation_parts.append(
            "The identified control failure represents the primary area "
            "requiring management attention within the selected "
            "assessment scope."
        )

    if partially_satisfied:
        interpretation_parts.append(
            "Partially satisfied controls indicate that relevant "
            "practices are present but are not yet complete against the "
            "assessment criteria."
        )

    if satisfied:
        interpretation_parts.append(
            "Satisfied controls provide a positive foundation that should "
            "be maintained through periodic review and continued control "
            "operation."
        )

    if not_assessable:
        interpretation_parts.append(
            "The unavailable information also limits the completeness of "
            "the assessment and should be resolved before broader "
            "assurance is drawn from the results."
        )

    if not interpretation_parts:
        interpretation_parts.append(
            "Management interpretation is limited because the selected "
            "controls did not produce sufficient assessable findings."
        )

    lines.append(" ".join(interpretation_parts))

    lines.extend(
        (
            "",
            "Priority Actions",
        )
    )

    priority_results = (
        not_satisfied
        + partially_satisfied
        + satisfied
    )

    action_number = 1

    for result in priority_results:
        if not result.recommendations:
            continue

        if result.status.value == "Satisfied":
            heading = f"Maintain {result.control_name}"
        else:
            heading = f"Address {result.control_name}"

        recommendation_text = " ".join(
            result.recommendations
        )

        lines.append(
            f"{action_number}. {heading}. {recommendation_text}"
        )

        action_number += 1

        if action_number > 4:
            break

    if action_number == 1:
        lines.append(
            "1. Continue monitoring the selected controls and repeat the "
            "assessment when additional information becomes available."
        )

    if not_assessable:
        lines.extend(
            (
                "",
                "Information Gap",
            )
        )

        gap_sentences = []

        for result in not_assessable:
            recommendation_text = " ".join(
                result.recommendations
            )

            gap_sentences.append(
                f"{result.control_name} remains Not Assessable because "
                "sufficient information was not available. "
                f"{recommendation_text}"
            )

        gap_sentences.append(
            "The absence of sufficient information is an assessment "
            "limitation and does not constitute evidence that the "
            "affected control has failed."
        )

        lines.append(" ".join(gap_sentences))

    return "\n".join(lines)


def generate_summary(
    *,
    organization: dict[str, Any],
    results: tuple[ControlResult, ...] | list[ControlResult],
    score: ScoreSummary,
    text_generator: TextGenerator | None = None,
    model_name: str | None = None,
    fallback_on_error: bool = False,
) -> AISummary:
    """
    Generate an AI-assisted or deterministic fallback explanation.

    When ``fallback_on_error`` is True, provider failures, invalid return
    types and empty output result in a deterministic fallback instead of
    terminating the assessment.
    """
    normalized_results = _validate_results(results)
    before_fingerprint = _result_fingerprint(normalized_results)

    source = "deterministic-fallback"
    effective_model_name: str | None = None
    fallback_reason: str | None = None

    if text_generator is None:
        generated_text = generate_deterministic_fallback(
            results=normalized_results,
            score=score,
        )
    else:
        prompt = build_ai_prompt(
            organization=organization,
            results=normalized_results,
            score=score,
        )

        try:
            candidate_text = text_generator(prompt)

            if not isinstance(candidate_text, str):
                raise AISummaryError(
                    "The text generator must return a string."
                )

            if not candidate_text.strip():
                raise AISummaryError(
                    "The text generator returned an empty summary."
                )

            generated_text = candidate_text.strip()
            source = "ai"
            effective_model_name = model_name

        except Exception as exc:
            if not fallback_on_error:
                if isinstance(exc, AISummaryError):
                    raise

                raise AISummaryError(
                    f"Text generation failed: {exc}"
                ) from exc

            fallback_reason = str(exc).strip() or (
                exc.__class__.__name__
            )

            generated_text = generate_deterministic_fallback(
                results=normalized_results,
                score=score,
            )

    after_fingerprint = _result_fingerprint(normalized_results)

    if before_fingerprint != after_fingerprint:
        raise AIIntegrityError(
            "Deterministic assessment results changed during "
            "summary generation."
        )

    return AISummary(
        text=generated_text.strip(),
        source=source,
        model_name=effective_model_name,
        disclaimer=SUMMARY_DISCLAIMER,
        fallback_reason=fallback_reason,
    )