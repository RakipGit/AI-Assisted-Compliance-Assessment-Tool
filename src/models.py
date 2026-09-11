"""Internal data models used by the compliance assessment tool."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ControlStatus(str, Enum):
    """Possible assessment outcomes for a security control."""

    SATISFIED = "Satisfied"
    PARTIALLY_SATISFIED = "Partially Satisfied"
    NOT_SATISFIED = "Not Satisfied"
    NOT_ASSESSABLE = "Not Assessable"


@dataclass(frozen=True)
class FrameworkMapping:
    """
    Reference from an assessed control to a framework requirement.

    Attributes:
        framework:
            Framework name, such as ISO/IEC 27001:2022 or NIS2.

        reference:
            Exact control or article reference, such as A.8.5 or
            Article 21(2)(j).

        title:
            Short title of the referenced control or requirement.

        role:
            Relationship of the mapping to the assessed control.
            Expected values are typically "primary" or "supporting".
    """

    framework: str
    reference: str
    title: str
    role: str = "primary"

    def __post_init__(self) -> None:
        """Validate the mapping after object creation."""
        allowed_roles = {"primary", "supporting"}

        if not self.framework.strip():
            raise ValueError("Framework name must not be empty.")

        if not self.reference.strip():
            raise ValueError("Framework reference must not be empty.")

        if not self.title.strip():
            raise ValueError("Framework mapping title must not be empty.")

        if self.role not in allowed_roles:
            raise ValueError(
                "Framework mapping role must be either "
                "'primary' or 'supporting'."
            )


@dataclass(frozen=True)
class ControlResult:
    """
    Immutable assessment result for one security control.

    Attributes:
        control_id:
            Stable internal identifier, such as "mfa".

        control_name:
            Human-readable name, such as
            "Multi Factor Authentication".

        status:
            Deterministically assigned ControlStatus.

        rationale:
            Explanation of why the status was assigned.

        recommendations:
            Remediation or improvement actions.

        evidence:
            Evidence-related observations derived from the input.

        mappings:
            ISO/IEC 27001 and NIS2 framework references.

        metadata:
            Additional non-decisional information that may be used
            for reporting or diagnostics.
    """

    control_id: str
    control_name: str
    status: ControlStatus
    rationale: str
    recommendations: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    mappings: tuple[FrameworkMapping, ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        """Validate the control result after object creation."""
        if not self.control_id.strip():
            raise ValueError("Control ID must not be empty.")

        if not self.control_name.strip():
            raise ValueError("Control name must not be empty.")

        if not isinstance(self.status, ControlStatus):
            raise TypeError("Status must be an instance of ControlStatus.")

        if not self.rationale.strip():
            raise ValueError("Control-result rationale must not be empty.")

        if not all(
            isinstance(item, str) and item.strip()
            for item in self.recommendations
        ):
            raise ValueError(
                "Every recommendation must be a non-empty string."
            )

        if not all(
            isinstance(item, str) and item.strip()
            for item in self.evidence
        ):
            raise ValueError(
                "Every evidence entry must be a non-empty string."
            )

        if not all(
            isinstance(mapping, FrameworkMapping)
            for mapping in self.mappings
        ):
            raise TypeError(
                "Every mapping must be a FrameworkMapping instance."
            )

        if not all(
            isinstance(item, tuple) and len(item) == 2
            for item in self.metadata
        ):
            raise TypeError(
                "Metadata must contain key-value tuples."
            )

    @property
    def is_assessable(self) -> bool:
        """Return True when the control participates in scoring."""
        return self.status is not ControlStatus.NOT_ASSESSABLE

    @property
    def numeric_score(self) -> float | None:
        """
        Return the prototype scoring value for this control.

        Returns:
            1.0 for Satisfied.
            0.5 for Partially Satisfied.
            0.0 for Not Satisfied.
            None for Not Assessable.
        """
        scores: dict[ControlStatus, float | None] = {
            ControlStatus.SATISFIED: 1.0,
            ControlStatus.PARTIALLY_SATISFIED: 0.5,
            ControlStatus.NOT_SATISFIED: 0.0,
            ControlStatus.NOT_ASSESSABLE: None,
        }

        return scores[self.status]

    def metadata_dict(self) -> dict[str, Any]:
        """Return metadata as a new dictionary."""
        return dict(self.metadata)