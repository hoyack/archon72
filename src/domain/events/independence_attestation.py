"""Independence attestation event payloads (FR98, FR133).

This module defines event payloads for annual Keeper independence attestation:
- IndependenceAttestationPayload: When a Keeper submits annual attestation
- KeeperIndependenceSuspendedPayload: When override capability is suspended
- DeclarationChangeDetectedPayload: When declarations change from previous year

Constitutional Constraints:
- FR98: Anomalous signature patterns SHALL be flagged for manual review
- FR133: Keepers SHALL annually attest independence; attestation recorded
- CT-11: Silent failure destroys legitimacy -> Attestations must be logged
- CT-12: Witnessing creates accountability -> All attestation events MUST be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before attestation
2. WITNESS EVERYTHING - All attestation events must be witnessed
3. FAIL LOUD - Failed event write = attestation failure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

# Event type constants for independence attestation
INDEPENDENCE_ATTESTATION_EVENT_TYPE: str = "keeper.independence_attestation"
KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE: str = "keeper.independence_suspended"
DECLARATION_CHANGE_DETECTED_EVENT_TYPE: str = "keeper.declaration_change_detected"


@dataclass(frozen=True, eq=True)
class IndependenceAttestationPayload:
    """Payload for annual independence attestation events (FR133).

    An IndependenceAttestationPayload is created when a Keeper submits
    their annual independence attestation declaring conflicts of interest
    and organizational affiliations. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR133: Annual independence attestation requirement
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper making the attestation.
        attestation_year: The year this attestation covers.
        conflict_count: Number of conflict declarations submitted.
        organization_count: Number of affiliated organizations declared.
        attested_at: When the attestation was submitted (UTC).
    """

    keeper_id: str
    attestation_year: int
    conflict_count: int
    organization_count: int
    attested_at: datetime

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
        return json.dumps(
            {
                "event_type": "IndependenceAttestation",
                "keeper_id": self.keeper_id,
                "attestation_year": self.attestation_year,
                "conflict_count": self.conflict_count,
                "organization_count": self.organization_count,
                "attested_at": self.attested_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True, eq=True)
class KeeperIndependenceSuspendedPayload:
    """Payload for independence suspension events (FR133).

    A KeeperIndependenceSuspendedPayload is created when a Keeper's
    override capability is suspended due to missing their annual
    independence attestation deadline. This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR133: Keepers SHALL annually attest independence
    - CT-11: Silent failure destroys legitimacy
    - CT-12: Witnessing creates accountability

    Attributes:
        keeper_id: ID of the Keeper whose capability is suspended.
        deadline_missed: The attestation deadline that was missed.
        suspended_at: When the suspension became effective (UTC).
        capabilities_suspended: List of suspended capabilities (e.g., ["override"]).
    """

    keeper_id: str
    deadline_missed: datetime
    suspended_at: datetime
    capabilities_suspended: list[str]

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
        return json.dumps(
            {
                "event_type": "KeeperIndependenceSuspended",
                "keeper_id": self.keeper_id,
                "deadline_missed": self.deadline_missed.isoformat(),
                "suspended_at": self.suspended_at.isoformat(),
                "capabilities_suspended": self.capabilities_suspended,
            },
            sort_keys=True,
        ).encode("utf-8")


@dataclass(frozen=True, eq=True)
class DeclarationChangeDetectedPayload:
    """Payload for declaration change events (FR133, ADR-7).

    A DeclarationChangeDetectedPayload is created when a Keeper's
    independence declarations change from the previous year. This
    supports ADR-7 Aggregate Anomaly Detection for pattern analysis.
    This event MUST be witnessed (CT-12).

    Constitutional Constraints:
    - FR133: Changes in declarations are highlighted for review
    - CT-9: Attackers are patient - aggregate patterns must be tracked
    - CT-12: Witnessing creates accountability

    ADR-7 Context:
    Declaration changes are tracked to detect potential coordination:
    - Multiple Keepers declaring similar new affiliations
    - Patterns suggesting undisclosed relationships
    - Sudden removal of previously declared conflicts

    Attributes:
        keeper_id: ID of the Keeper whose declarations changed.
        attestation_year: The year of the new attestation.
        previous_conflicts: Number of conflicts in previous year's attestation.
        current_conflicts: Number of conflicts in current attestation.
        change_summary: Human-readable summary of changes.
        detected_at: When the change was detected (UTC).
    """

    keeper_id: str
    attestation_year: int
    previous_conflicts: int
    current_conflicts: int
    change_summary: str
    detected_at: datetime

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
        return json.dumps(
            {
                "event_type": "DeclarationChangeDetected",
                "keeper_id": self.keeper_id,
                "attestation_year": self.attestation_year,
                "previous_conflicts": self.previous_conflicts,
                "current_conflicts": self.current_conflicts,
                "change_summary": self.change_summary,
                "detected_at": self.detected_at.isoformat(),
            },
            sort_keys=True,
        ).encode("utf-8")
