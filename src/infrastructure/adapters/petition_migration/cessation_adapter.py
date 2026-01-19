"""Cessation petition adapter (Story 0.3, AC1, FR-9.1, ADR-P7).

This module provides bidirectional conversion between Story 7.2's Petition model
and Story 0.2's PetitionSubmission model for cessation petitions.

Constitutional Constraints:
- CT-11: Silent failure destroys legitimacy → All conversions must preserve data
- CT-12: Witnessing creates accountability → All changes logged
- FR-9.4: Petition ID preservation is MANDATORY

State Mapping:
- PetitionStatus.OPEN → PetitionState.RECEIVED
- PetitionStatus.THRESHOLD_MET → PetitionState.ESCALATED
- PetitionStatus.CLOSED → PetitionState.ACKNOWLEDGED

Note: DELIBERATING and REFERRED states are not used for cessation petitions
since they bypass Three Fates deliberation and go directly to escalation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

from src.domain.events.petition import PetitionStatus
from src.domain.models.petition import CoSigner, Petition
from src.domain.models.petition_submission import (
    PetitionState,
    PetitionSubmission,
    PetitionType,
)

# Hardcoded realm for cessation petitions (AC1)
CESSATION_REALM: Final[str] = "cessation-realm"

# Status to State mapping (Story 7.2 → Story 0.2)
STATUS_TO_STATE_MAP: Final[dict[PetitionStatus, PetitionState]] = {
    PetitionStatus.OPEN: PetitionState.RECEIVED,
    PetitionStatus.THRESHOLD_MET: PetitionState.ESCALATED,
    PetitionStatus.CLOSED: PetitionState.ACKNOWLEDGED,
}

# State to Status mapping (Story 0.2 → Story 7.2) for reverse conversion
STATE_TO_STATUS_MAP: Final[dict[PetitionState, PetitionStatus]] = {
    PetitionState.RECEIVED: PetitionStatus.OPEN,
    PetitionState.ESCALATED: PetitionStatus.THRESHOLD_MET,
    PetitionState.ACKNOWLEDGED: PetitionStatus.CLOSED,
    # Note: DELIBERATING and REFERRED map to OPEN since cessation petitions
    # don't use these states, but we need a fallback for completeness
    PetitionState.DELIBERATING: PetitionStatus.OPEN,
    PetitionState.REFERRED: PetitionStatus.OPEN,
}


class CessationPetitionAdapter:
    """Adapter for converting between Petition and PetitionSubmission.

    This adapter provides bidirectional conversion for cessation petitions
    during the Story 7.2 migration period.

    Constitutional Compliance:
    - FR-9.1: Migrates Story 7.2 cessation_petition to CESSATION type
    - FR-9.4: Preserves petition_id exactly (MANDATORY)

    Usage:
        # Convert to new schema
        submission = CessationPetitionAdapter.to_submission(petition)

        # Convert back to legacy schema (for reads)
        petition = CessationPetitionAdapter.from_submission(
            submission, cosigners, submitter_public_key, submitter_signature
        )
    """

    @staticmethod
    def to_submission(petition: Petition) -> PetitionSubmission:
        """Convert a Story 7.2 Petition to Story 0.2 PetitionSubmission.

        FR-9.4: The petition_id is preserved exactly as submission.id.

        Args:
            petition: The Story 7.2 Petition to convert.

        Returns:
            A PetitionSubmission with:
            - id = petition.petition_id (preserved exactly, FR-9.4)
            - text = petition.petition_content
            - type = CESSATION
            - state = mapped from petition.status
            - realm = "cessation-realm"
            - created_at = petition.created_timestamp
            - updated_at = current time
        """
        return PetitionSubmission(
            id=petition.petition_id,  # FR-9.4: Preserve ID exactly
            type=PetitionType.CESSATION,
            text=petition.petition_content,
            state=STATUS_TO_STATE_MAP[petition.status],
            submitter_id=None,  # Story 7.2 uses public_key, not UUID
            content_hash=None,  # Set by Story 0.5 Blake3 hashing service
            realm=CESSATION_REALM,
            created_at=petition.created_timestamp,
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def from_submission(
        submission: PetitionSubmission,
        cosigners: tuple[CoSigner, ...],
        submitter_public_key: str,
        submitter_signature: str,
        threshold_met_at: datetime | None = None,
    ) -> Petition:
        """Convert a Story 0.2 PetitionSubmission back to Story 7.2 Petition.

        This is used for reading petitions during the migration period when
        the legacy repository is the source of truth.

        FR-9.4: The submission.id is preserved as petition_id.

        Args:
            submission: The Story 0.2 PetitionSubmission to convert.
            cosigners: Co-signers from legacy storage (not in PetitionSubmission).
            submitter_public_key: Submitter's Ed25519 public key from legacy.
            submitter_signature: Submitter's signature from legacy.
            threshold_met_at: When threshold was met (for ESCALATED state).

        Returns:
            A Petition with:
            - petition_id = submission.id (preserved exactly, FR-9.4)
            - petition_content = submission.text
            - status = mapped from submission.state
            - cosigners = provided cosigners
            - created_timestamp = submission.created_at
        """
        status = STATE_TO_STATUS_MAP.get(submission.state, PetitionStatus.OPEN)

        return Petition(
            petition_id=submission.id,  # FR-9.4: Preserve ID exactly
            submitter_public_key=submitter_public_key,
            submitter_signature=submitter_signature,
            petition_content=submission.text,
            created_timestamp=submission.created_at,
            status=status,
            cosigners=cosigners,
            threshold_met_at=threshold_met_at,
        )
