"""Compliance documentation event payloads (Story 9.9, NFR31-34).

This module defines event payloads for regulatory compliance documentation:
- ComplianceDocumentedEventPayload: When a compliance assessment is documented

Constitutional Constraints:
- NFR31: Personal data SHALL be stored separately from constitutional events (GDPR)
- NFR32: Retention policy SHALL be published and immutable
- NFR33: System SHALL provide structured audit export in standard format
- NFR34: Third-party attestation interface SHALL be available
- CT-12: Witnessing creates accountability -> All compliance events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before creating compliance events
2. WITNESS EVERYTHING - All compliance events must be witnessed
3. FAIL LOUD - Never silently swallow compliance operations
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# Event type constant for compliance documentation
COMPLIANCE_DOCUMENTED_EVENT_TYPE: str = "compliance.documented"

# System agent ID for compliance documentation events
COMPLIANCE_SYSTEM_AGENT_ID: str = "system:compliance-documentation"


class ComplianceFramework(Enum):
    """Regulatory compliance frameworks (NFR31-34).

    Each framework represents a regulatory or standards body
    whose requirements must be documented and tracked.
    """

    EU_AI_ACT = "EU_AI_ACT"
    """European Union AI Act (2024/1689)."""

    NIST_AI_RMF = "NIST_AI_RMF"
    """NIST AI Risk Management Framework."""

    IEEE_7001 = "IEEE_7001"
    """IEEE 7001 Transparency Standard."""

    GDPR = "GDPR"
    """General Data Protection Regulation."""

    MAESTRO = "MAESTRO"
    """CSA MAESTRO Framework for Agentic AI."""


class ComplianceStatus(Enum):
    """Status of compliance assessment (NFR31-34).

    Each status represents the compliance posture for a framework.
    """

    COMPLIANT = "COMPLIANT"
    """Full compliance with all requirements."""

    PARTIAL = "PARTIAL"
    """Partial compliance - some requirements met."""

    GAP_IDENTIFIED = "GAP_IDENTIFIED"
    """Gaps identified that require remediation."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    """Framework requirements do not apply."""


@dataclass(frozen=True, eq=True)
class ComplianceDocumentedEventPayload:
    """Payload for compliance documentation events (NFR31-34).

    A ComplianceDocumentedEventPayload is created when a compliance assessment
    is documented. This event MUST be witnessed (CT-12) and is immutable
    after creation.

    Constitutional Constraints:
    - NFR31-34: Regulatory compliance requirements
    - CT-12: Witnessing creates accountability -> Must be witnessed

    Attributes:
        compliance_id: Unique identifier (e.g., "NFR31-34-EU-AI-ACT-2026-01").
        framework: Compliance framework being assessed.
        framework_version: Version of the standard (e.g., "2024/1689").
        assessment_date: When assessment was performed (UTC).
        status: Compliance status result.
        findings: Key findings from assessment.
        remediation_plan: Plan for addressing gaps (if any).
        next_review_date: Scheduled next review (optional).
        documented_by: Agent/system that documented compliance.
    """

    compliance_id: str
    framework: ComplianceFramework
    framework_version: str
    assessment_date: datetime
    status: ComplianceStatus
    findings: tuple[str, ...] = field(default_factory=tuple)
    remediation_plan: Optional[str] = None
    next_review_date: Optional[datetime] = None
    documented_by: str = COMPLIANCE_SYSTEM_AGENT_ID

    def __post_init__(self) -> None:
        """Validate compliance payload fields."""
        if not self.compliance_id:
            raise ValueError("compliance_id is required")
        if not self.framework_version:
            raise ValueError("framework_version is required")
        if not self.documented_by:
            raise ValueError("documented_by is required")

    def to_dict(self) -> dict[str, Any]:
        """Convert payload to dictionary for serialization.

        Returns:
            Dictionary representation of the compliance payload.
        """
        result: dict[str, Any] = {
            "compliance_id": self.compliance_id,
            "framework": self.framework.value,
            "framework_version": self.framework_version,
            "assessment_date": self.assessment_date.isoformat(),
            "status": self.status.value,
            "findings": list(self.findings),
            "remediation_plan": self.remediation_plan,
            "next_review_date": (
                self.next_review_date.isoformat() if self.next_review_date else None
            ),
            "documented_by": self.documented_by,
        }
        return result

    def signable_content(self) -> bytes:
        """Return canonical content for witnessing (CT-12).

        Constitutional Constraint (CT-12):
        Witnessing creates accountability. This method provides
        the canonical bytes to sign for witness verification.

        The content is JSON-serialized with sorted keys to ensure
        deterministic output regardless of Python dict ordering.

        Returns:
            UTF-8 encoded bytes of canonical JSON representation.
        """
        content: dict[str, Any] = {
            "compliance_id": self.compliance_id,
            "framework": self.framework.value,
            "framework_version": self.framework_version,
            "assessment_date": self.assessment_date.isoformat(),
            "status": self.status.value,
            "findings": list(self.findings),
            "remediation_plan": self.remediation_plan,
            "next_review_date": (
                self.next_review_date.isoformat() if self.next_review_date else None
            ),
            "documented_by": self.documented_by,
        }

        return json.dumps(content, sort_keys=True).encode("utf-8")
