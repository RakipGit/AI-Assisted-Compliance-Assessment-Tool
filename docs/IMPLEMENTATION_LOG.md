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
