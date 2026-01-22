"""Escalation Decision Package Service (Story 6.2, FR-5.4).

This service provides comprehensive decision packages for King adoption/acknowledgment
decisions. It aggregates petition data, co-signer information, and escalation context.

Constitutional Constraints:
- FR-5.4: King SHALL receive complete context for escalation decisions [P0]
- RULING-2: Tiered transcript access (mediated summaries for Kings, not raw transcripts)
- RULING-3: Realm-scoped data access (Kings see only their realm's escalations)
- NFR-1.2: Endpoint latency p99 < 200ms

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before service operations
2. WITNESS EVERYTHING - All data access requires attribution
3. FAIL LOUD - Never silently swallow errors
4. READS DURING HALT - Decision package queries work during halt (CT-13)
"""

from __future__ import annotations

import hashlib
import structlog
from datetime import datetime
from uuid import UUID

from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.errors.petition import PetitionSubmissionNotFoundError
from src.domain.models.petition_submission import PetitionSubmission

logger = structlog.get_logger(__name__)


class EscalationDecisionPackageService:
    """Service for fetching escalation decision packages (Story 6.2).

    Aggregates petition data, co-signer information, and escalation history
    to provide Kings with comprehensive context for adoption/acknowledgment decisions.

    Constitutional Constraints:
    - FR-5.4: Complete escalation context for King decisions
    - RULING-2: Mediated deliberation summaries (not raw transcripts)
    - RULING-3: Realm-scoped access (verify King's realm matches)
    """

    def __init__(
        self,
        petition_repository: PetitionSubmissionRepositoryProtocol,
    ) -> None:
        """Initialize the escalation decision package service.

        Args:
            petition_repository: Repository for petition submission access.
        """
        self._petition_repository = petition_repository

    async def get_decision_package(
        self,
        petition_id: UUID,
        king_realm: str,
    ) -> DecisionPackageData:
        """Fetch escalation decision package for a petition (Story 6.2, AC1-AC2).

        Retrieves complete context for King adoption/acknowledgment decision:
        - Petition core data (text, type, submitter metadata)
        - Co-signer information (paginated list with total count)
        - Escalation history (source, deliberation summary, or Knight recommendation)

        Constitutional Constraints:
        - RULING-3: Verify King's realm matches escalated_to_realm
        - RULING-2: Provide mediated summaries, not raw transcripts
        - FR-5.4: Complete decision context

        Args:
            petition_id: UUID of the escalated petition.
            king_realm: Realm of the requesting King (for authorization).

        Returns:
            DecisionPackageData with complete escalation context.

        Raises:
            PetitionSubmissionNotFoundError: If petition doesn't exist.
            EscalationNotFoundError: If petition is not escalated.
            RealmMismatchError: If King's realm doesn't match escalation realm.
        """
        logger.info(
            "fetching_decision_package",
            petition_id=str(petition_id),
            king_realm=king_realm,
        )

        # Fetch petition submission
        submission = await self._petition_repository.get(petition_id)
        if submission is None:
            raise PetitionSubmissionNotFoundError(petition_id=petition_id)

        # Verify petition is escalated
        if submission.escalated_at is None:
            raise EscalationNotFoundError(
                petition_id=petition_id,
                message=f"Petition {petition_id} is not escalated",
            )

        # Verify realm match (RULING-3: realm-scoped access)
        if submission.escalated_to_realm != king_realm:
            raise RealmMismatchError(
                petition_id=petition_id,
                expected_realm=king_realm,
                actual_realm=submission.escalated_to_realm or "none",
            )

        # Build decision package data
        package = await self._build_package(submission)

        logger.info(
            "decision_package_fetched",
            petition_id=str(petition_id),
            escalation_source=submission.escalation_source,
            co_signer_count=submission.co_signer_count,
        )

        return package

    async def _build_package(
        self,
        submission: PetitionSubmission,
    ) -> DecisionPackageData:
        """Build decision package from petition submission.

        Args:
            submission: The escalated petition submission.

        Returns:
            DecisionPackageData with complete context.
        """
        # Anonymize submitter (hash public key)
        submitter_hash = self._hash_public_key(
            submission.submitter_id or UUID(int=0)
        )

        # Build co-signer data (for now, return empty list - Epic 5 will add full support)
        co_signers = CoSignerListData(
            items=[],
            total_count=submission.co_signer_count,
            next_cursor=None,
            has_more=False,
        )

        # Build escalation history
        escalation_history = EscalationHistoryData(
            escalation_source=submission.escalation_source or "UNKNOWN",
            escalated_at=submission.escalated_at or datetime.utcnow(),
            co_signer_count_at_escalation=submission.co_signer_count,
            deliberation_summary=None,  # TODO: Story 6.2+ - fetch from deliberation service
            knight_recommendation=None,  # TODO: Story 6.2+ - fetch from Knight service
        )

        return DecisionPackageData(
            petition_id=submission.id,
            petition_type=submission.type.value,
            petition_content=submission.text,
            submitter_metadata=SubmitterMetadataData(
                public_key_hash=submitter_hash,
                submitted_at=submission.created_at,
            ),
            co_signers=co_signers,
            escalation_history=escalation_history,
        )

    def _hash_public_key(self, key: UUID) -> str:
        """Hash a public key (UUID) for anonymization.

        Args:
            key: The public key UUID to hash.

        Returns:
            SHA-256 hash of the key (hex string).
        """
        return hashlib.sha256(str(key).encode()).hexdigest()


# Data transfer objects (DTOs)


class SubmitterMetadataData:
    """Anonymized submitter metadata."""

    def __init__(self, public_key_hash: str, submitted_at: datetime) -> None:
        self.public_key_hash = public_key_hash
        self.submitted_at = submitted_at


class CoSignerData:
    """Co-signer information."""

    def __init__(
        self, public_key_hash: str, signed_at: datetime, sequence: int
    ) -> None:
        self.public_key_hash = public_key_hash
        self.signed_at = signed_at
        self.sequence = sequence


class CoSignerListData:
    """Paginated co-signer list."""

    def __init__(
        self,
        items: list[CoSignerData],
        total_count: int,
        next_cursor: str | None,
        has_more: bool,
    ) -> None:
        self.items = items
        self.total_count = total_count
        self.next_cursor = next_cursor
        self.has_more = has_more


class DeliberationSummaryData:
    """Mediated deliberation summary (RULING-2)."""

    def __init__(
        self,
        vote_breakdown: str,
        has_dissent: bool,
        decision_outcome: str,
        transcript_hash: str,
    ) -> None:
        self.vote_breakdown = vote_breakdown
        self.has_dissent = has_dissent
        self.decision_outcome = decision_outcome
        self.transcript_hash = transcript_hash


class KnightRecommendationData:
    """Knight recommendation details."""

    def __init__(
        self,
        knight_id: UUID,
        recommendation_text: str,
        recommended_at: datetime,
    ) -> None:
        self.knight_id = knight_id
        self.recommendation_text = recommendation_text
        self.recommended_at = recommended_at


class EscalationHistoryData:
    """Escalation history context."""

    def __init__(
        self,
        escalation_source: str,
        escalated_at: datetime,
        co_signer_count_at_escalation: int,
        deliberation_summary: DeliberationSummaryData | None,
        knight_recommendation: KnightRecommendationData | None,
    ) -> None:
        self.escalation_source = escalation_source
        self.escalated_at = escalated_at
        self.co_signer_count_at_escalation = co_signer_count_at_escalation
        self.deliberation_summary = deliberation_summary
        self.knight_recommendation = knight_recommendation


class DecisionPackageData:
    """Complete decision package data."""

    def __init__(
        self,
        petition_id: UUID,
        petition_type: str,
        petition_content: str,
        submitter_metadata: SubmitterMetadataData,
        co_signers: CoSignerListData,
        escalation_history: EscalationHistoryData,
    ) -> None:
        self.petition_id = petition_id
        self.petition_type = petition_type
        self.petition_content = petition_content
        self.submitter_metadata = submitter_metadata
        self.co_signers = co_signers
        self.escalation_history = escalation_history


# Custom errors


class EscalationNotFoundError(Exception):
    """Raised when petition is not escalated."""

    def __init__(self, petition_id: UUID, message: str) -> None:
        self.petition_id = petition_id
        super().__init__(message)


class RealmMismatchError(Exception):
    """Raised when King's realm doesn't match escalation realm."""

    def __init__(
        self, petition_id: UUID, expected_realm: str, actual_realm: str
    ) -> None:
        self.petition_id = petition_id
        self.expected_realm = expected_realm
        self.actual_realm = actual_realm
        super().__init__(
            f"Realm mismatch for petition {petition_id}: "
            f"expected {expected_realm}, got {actual_realm}"
        )
