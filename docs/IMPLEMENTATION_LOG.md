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

