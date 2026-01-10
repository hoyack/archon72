"""Integrity Case Artifact domain models (Story 7.10, FR144).

This module defines the domain model for the Integrity Case Artifact,
which documents all constitutional guarantees, their enforcement mechanisms,
and invalidation conditions.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact
- FR42: Public read access without authentication
- FR50: Versioned schema documentation
- CT-11: Silent failure destroys legitimacy -> All guarantees must be visible
- CT-12: Witnessing creates accountability -> Updates must be witnessed
- CT-13: Integrity outranks availability -> Must survive cessation

Developer Golden Rules:
1. COMPLETE COVERAGE - Every CT and FR with a guarantee MUST be in the artifact
2. MACHINE-READABLE - JSON with JSON-LD context for semantic interoperability
3. IMMUTABLE HISTORY - Version history preserved, never overwritten
4. POST-CESSATION - MUST be accessible after system ceases (read-only)
5. WITNESSED UPDATES - Amendment synchronization creates witnessed event

Usage:
    from src.domain.models.integrity_case import (
        IntegrityGuarantee,
        IntegrityCaseArtifact,
        GuaranteeCategory,
    )

    # Create a single guarantee
    guarantee = IntegrityGuarantee(
        guarantee_id="ct-1-audit-trail",
        category=GuaranteeCategory.CONSTITUTIONAL,
        name="Append-Only Audit Trail",
        description="All events are append-only, hash-linked, and witnessed",
        fr_reference="FR1, FR2, FR3",
        ct_reference="CT-1",
        mechanism="Hash chain with witness signatures",
        invalidation_conditions=["Database tampering", "HSM compromise"],
        is_constitutional=True,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class GuaranteeCategory(Enum):
    """Category of an integrity guarantee.

    Constitutional guarantees cannot be waived (unless CT-15 explicitly allows).
    Functional guarantees are enforced by specific FRs.
    Operational guarantees relate to system behavior.
    """

    CONSTITUTIONAL = "constitutional"
    """CT-1 through CT-15: Core constitutional constraints that cannot be waived."""

    FUNCTIONAL = "functional"
    """FR-based guarantees enforced by specific functional requirements."""

    OPERATIONAL = "operational"
    """ADR-based guarantees for system behavior and architecture decisions."""


@dataclass(frozen=True, eq=True)
class IntegrityGuarantee:
    """A single integrity guarantee with enforcement details (FR144).

    Represents one guarantee that the system makes, including how it's
    enforced and what conditions would invalidate it.

    Constitutional Constraint (FR144):
    The Integrity Case Artifact SHALL include all guarantees claimed,
    the mechanisms enforcing them, and conditions that would invalidate them.

    Attributes:
        guarantee_id: Unique identifier (e.g., "ct-1-audit-trail").
        category: Constitutional, functional, or operational.
        name: Human-readable name for the guarantee.
        description: What the system guarantees.
        fr_reference: Functional requirement reference(s) (e.g., "FR1, FR2").
        ct_reference: Constitutional constraint reference if applicable (e.g., "CT-1").
        mechanism: How the guarantee is enforced (implementation details).
        invalidation_conditions: Conditions that would break the guarantee.
        is_constitutional: True if this guarantee cannot be waived.
        adr_reference: ADR reference if applicable (e.g., "ADR-1").

    Example:
        >>> guarantee = IntegrityGuarantee(
        ...     guarantee_id="ct-1-audit-trail",
        ...     category=GuaranteeCategory.CONSTITUTIONAL,
        ...     name="Append-Only Audit Trail",
        ...     description="All events are append-only, hash-linked, and witnessed",
        ...     fr_reference="FR1, FR2, FR3",
        ...     ct_reference="CT-1",
        ...     mechanism="Hash chain with witness signatures",
        ...     invalidation_conditions=["Database tampering", "HSM compromise"],
        ...     is_constitutional=True,
        ... )
        >>> guarantee.guarantee_id
        'ct-1-audit-trail'
    """

    guarantee_id: str
    category: GuaranteeCategory
    name: str
    description: str
    fr_reference: str
    mechanism: str
    invalidation_conditions: tuple[str, ...]
    is_constitutional: bool
    ct_reference: Optional[str] = None
    adr_reference: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate guarantee completeness."""
        if not self.guarantee_id:
            raise ValueError("guarantee_id must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.description:
            raise ValueError("description must be non-empty")
        if not self.mechanism:
            raise ValueError("mechanism must be non-empty")
        if not self.invalidation_conditions:
            raise ValueError("invalidation_conditions must have at least one condition")
        if self.category == GuaranteeCategory.CONSTITUTIONAL and not self.ct_reference:
            raise ValueError("Constitutional guarantees require ct_reference")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with all guarantee fields formatted for API response.
        """
        result: dict[str, Any] = {
            "guarantee_id": self.guarantee_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "fr_reference": self.fr_reference,
            "mechanism": self.mechanism,
            "invalidation_conditions": list(self.invalidation_conditions),
            "is_constitutional": self.is_constitutional,
        }
        if self.ct_reference:
            result["ct_reference"] = self.ct_reference
        if self.adr_reference:
            result["adr_reference"] = self.adr_reference
        return result

    def to_json_ld(self) -> dict[str, Any]:
        """Convert to JSON-LD format for semantic interoperability (FR144, FR50).

        Returns:
            Dict with JSON-LD type and guarantee fields.
        """
        result = self.to_dict()
        result["@type"] = "integrity:Guarantee"
        return result


# JSON-LD context for semantic interoperability (FR144, FR50)
INTEGRITY_CASE_JSON_LD_CONTEXT: dict[str, Any] = {
    "@context": {
        "integrity": "https://archon72.org/schema/integrity#",
        "guarantee_id": "integrity:guaranteeId",
        "category": "integrity:category",
        "name": "integrity:name",
        "description": "integrity:description",
        "fr_reference": "integrity:functionalRequirement",
        "ct_reference": "integrity:constitutionalConstraint",
        "adr_reference": "integrity:architecturalDecision",
        "mechanism": "integrity:enforcementMechanism",
        "invalidation_conditions": "integrity:invalidationConditions",
        "is_constitutional": "integrity:isConstitutional",
        "Guarantee": "integrity:Guarantee",
        "IntegrityCaseArtifact": "integrity:IntegrityCaseArtifact",
    }
}


@dataclass(frozen=True)
class IntegrityCaseArtifact:
    """Complete Integrity Case Artifact documenting all guarantees (FR144).

    Contains all integrity guarantees the system makes, with their
    enforcement mechanisms and invalidation conditions. This artifact
    is publicly accessible and must remain accessible after cessation.

    Constitutional Constraints:
    - FR144: System SHALL maintain published Integrity Case Artifact
    - FR42: Public read access without authentication
    - FR50: Versioned schema documentation
    - CT-13: Must survive cessation (read-only access indefinitely)

    Attributes:
        guarantees: Tuple of all integrity guarantees.
        version: Artifact version (semantic versioning).
        schema_version: API schema version.
        constitution_version: Constitutional rules version.
        created_at: When the artifact was first created.
        last_updated: When the artifact was last updated.
        amendment_event_id: ID of the last amendment that updated this artifact.

    Example:
        >>> artifact = IntegrityCaseArtifact.from_registry()
        >>> len(artifact.guarantees) >= 15  # At least 15 CTs
        True
    """

    guarantees: tuple[IntegrityGuarantee, ...]
    version: str = field(default="1.0.0")
    schema_version: str = field(default="1.0.0")
    constitution_version: str = field(default="1.0.0")
    created_at: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    amendment_event_id: Optional[str] = None

    def get_guarantee(self, guarantee_id: str) -> Optional[IntegrityGuarantee]:
        """Get a specific guarantee by ID.

        Args:
            guarantee_id: The guarantee_id to look up.

        Returns:
            The IntegrityGuarantee if found, None otherwise.
        """
        for guarantee in self.guarantees:
            if guarantee.guarantee_id == guarantee_id:
                return guarantee
        return None

    def get_by_category(
        self, category: GuaranteeCategory
    ) -> tuple[IntegrityGuarantee, ...]:
        """Get all guarantees of a specific category.

        Args:
            category: The category to filter by.

        Returns:
            Tuple of guarantees matching the category.
        """
        return tuple(g for g in self.guarantees if g.category == category)

    def get_constitutional(self) -> tuple[IntegrityGuarantee, ...]:
        """Get all constitutional (non-waivable) guarantees.

        Returns:
            Tuple of guarantees where is_constitutional is True.
        """
        return tuple(g for g in self.guarantees if g.is_constitutional)

    def validate_completeness(
        self,
        required_ct_refs: tuple[str, ...],
    ) -> list[str]:
        """Validate that all required constitutional constraints are covered.

        Args:
            required_ct_refs: Required CT references (e.g., ("CT-1", "CT-2", ...)).

        Returns:
            List of missing CT references. Empty if complete.
        """
        covered = {g.ct_reference for g in self.guarantees if g.ct_reference}
        missing = [ct for ct in required_ct_refs if ct not in covered]
        return missing

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (FR144).

        Returns:
            Dict with version metadata and all guarantees.
        """
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "constitution_version": self.constitution_version,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "amendment_event_id": self.amendment_event_id,
            "guarantee_count": len(self.guarantees),
            "guarantees": [g.to_dict() for g in self.guarantees],
        }

    def to_json_ld(self) -> dict[str, Any]:
        """Convert to JSON-LD format for semantic interoperability (FR144, FR50).

        Returns:
            Dict with JSON-LD context and all guarantees.
        """
        result = self.to_dict()
        result["@context"] = INTEGRITY_CASE_JSON_LD_CONTEXT["@context"]
        result["@type"] = "integrity:IntegrityCaseArtifact"
        result["guarantees"] = [g.to_json_ld() for g in self.guarantees]
        return result

    def __len__(self) -> int:
        """Return number of guarantees."""
        return len(self.guarantees)

    def __iter__(self):
        """Iterate over guarantees."""
        return iter(self.guarantees)


# All required CT references that must be documented
REQUIRED_CT_REFERENCES: tuple[str, ...] = (
    "CT-1",
    "CT-2",
    "CT-3",
    "CT-4",
    "CT-5",
    "CT-6",
    "CT-7",
    "CT-8",
    "CT-9",
    "CT-10",
    "CT-11",
    "CT-12",
    "CT-13",
    "CT-14",
    "CT-15",
)
"""All 15 constitutional constraints that must be documented in the artifact."""
