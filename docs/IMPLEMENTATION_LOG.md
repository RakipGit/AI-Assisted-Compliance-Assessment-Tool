## Decision — Cross-field validation between size and employees

### Decision

The `organization_schema.json` uses three `if/then` validation rules inside an `allOf` block to ensure that the declared organization-size category is consistent with the number of employees:

- micro: 1–9 employees
- small: 10–49 employees
- medium: 50–249 employees

### Rationale

Without cross-field validation, the schema could accept contradictory input, such as `"size": "micro"` together with `"employees": 200`.

The staff-headcount thresholds follow the employee thresholds used in the European Commission SME definition.

### Scope limitation

The classification implemented by the tool is based only on staff headcount. It does not constitute a complete legal determination of SME status, because the European SME definition also considers financial thresholds and enterprise relationships.

### Consequences

- Contradictory combinations of `size` and `employees` are rejected during input validation.
- The rule engine receives structurally and semantically more consistent organization data.
- The change affects only input validation and does not alter the security-control evaluation rules.


## Decision — Schema-driven input validation

### Decision

Organization scenario files are validated against
`organization_schema.json` before being processed by the deterministic
rule engine.

The Python validator dynamically selects the appropriate validator
implementation from the schema's `$schema` declaration by using
`jsonschema.validators.validator_for()`.

### Rationale

Schema-driven validation separates structural input verification from
security-control evaluation. The validator checks the organization-file
structure, required fields, data types, allowed values, date formats and
cross-field consistency between organization size and employee count.

The rule engine remains responsible for determining whether the available
security-control information is sufficient for an assessment and for
assigning the corresponding control status.

### Error handling

Validation collects and reports all detected schema violations together
with their input paths, rather than stopping after the first error.

Examples of reported paths include:

- `organization.employees`
- `security_controls.backup.last_restore_test_date`
- `security_controls.mfa.implemented`

### Consequences

- Invalid or contradictory input is rejected before rule evaluation.
- Structurally valid but incomplete control data remains acceptable and
  may later produce the `Not Assessable` status.
- Date-format validation is explicitly enabled through
  `jsonschema.FormatChecker`.
- The validation process is deterministic and independently testable.


## Decision — Immutable internal assessment models

### Decision

The internal assessment output is represented through three explicit
Python data models:

- `ControlStatus`
- `FrameworkMapping`
- `ControlResult`

The two result-related models are implemented as frozen dataclasses.

### Rationale

Explicit internal models provide a stable contract between the
deterministic rule engine, the scoring component, the AI-assisted
explanation layer and the report generator.

Framework mappings are stored as structured objects rather than flattened
strings so that framework name, reference, title and mapping role can be
processed independently.

### Immutability approach

Result collections such as recommendations, evidence observations and
framework mappings are stored as tuples. This reduces the risk of
accidental modification after deterministic evaluation.

The frozen dataclass mechanism provides shallow immutability. It does not
guarantee deep immutability for arbitrary nested Python objects; therefore,
mutable collections are not used in the core result fields.

### Scoring representation

Each assessable status exposes an internal prototype score:

- `Satisfied`: 1.0
- `Partially Satisfied`: 0.5
- `Not Satisfied`: 0.0
- `Not Assessable`: excluded from scoring through a `None` value

These values form a researcher-defined coverage indicator for the selected
controls and do not represent an official ISO/IEC 27001 or NIS2 compliance
score.

### Consequences

- The deterministic result cannot be reassigned after creation.
- The AI-assisted layer can consume results without changing their status.
- The scoring and reporting components receive a consistent data structure.
- Primary and supporting framework mappings remain distinguishable.


## Decision — Deterministic security-control rule engine

### Decision

The four selected security controls are evaluated through explicit,
deterministic Python functions:

- `evaluate_mfa`
- `evaluate_backup`
- `evaluate_patch_management`
- `evaluate_incident_response`

The rule engine does not use an LLM, probabilistic model or external AI
service to assign assessment statuses.

### Status logic

The engine distinguishes explicitly between:

- `True`: a positively declared condition
- `False`: a negatively declared condition
- `None` or an absent key: unavailable assessment information

Missing critical information results in `Not Assessable` rather than being
treated as `Not Satisfied`.

### Evidence handling

The `evidence_available` field produces an evidence observation but does not
automatically determine the control status. The prototype therefore remains
a preliminary self-assessment tool based on user-provided information rather
than an audit-verification system.

### Researcher-defined rules

The control rules and thresholds are transparent design decisions adopted
for the proof-of-concept.

In particular, the 30-day critical-patch deadline is a prototype threshold
and must not be interpreted as an official ISO/IEC 27001 or NIS2 requirement.

### Catalogue integration

Control names, categories, assessment scopes and framework mappings are
loaded from `control_catalogue.json`. The rule engine contains only
evaluation logic and does not duplicate framework metadata.

### Consequences

- Identical input produces identical assessment results.
- The assigned status is reproducible and independently testable.
- Missing data is not silently interpreted as control failure.
- AI-generated explanations cannot determine or modify the underlying
  assessment status.
- Framework mappings can be maintained independently from rule logic.

## Decision — Prototype selected-controls coverage score

### Decision

The scoring component converts deterministic control statuses into the
following internal values:

- `Satisfied`: 1.0
- `Partially Satisfied`: 0.5
- `Not Satisfied`: 0.0
- `Not Assessable`: excluded from the calculation

The selected-controls coverage percentage is calculated as:

`earned score / maximum score of assessable controls × 100`

### Rationale

The scoring method provides a simple, transparent and reproducible summary
of the four selected control assessments.

A `Not Assessable` result is excluded from the denominator because it
represents insufficient information rather than confirmed control failure.

When no selected control is assessable, the scoring component returns no
percentage instead of reporting zero coverage.

### Interpretation limitation

The resulting percentage is a researcher-defined internal indicator for the
selected controls of the proof-of-concept.

It must not be interpreted as:

- an official ISO/IEC 27001 compliance score,
- a NIS2 compliance percentage,
- certification readiness,
- audit assurance,
- or a legal compliance determination.

### Error handling

The scoring component rejects:

- empty result collections,
- non-`ControlResult` inputs,
- duplicate control identifiers.

### Consequences

- Missing information does not artificially reduce the score.
- The denominator remains visible through the assessable-control count.
- A completely unavailable assessment is distinguished from a confirmed
  zero-coverage result.
- The same deterministic results always produce the same coverage summary.

