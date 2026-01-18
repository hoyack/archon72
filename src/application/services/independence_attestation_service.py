"""Independence Attestation Service (FR98, FR133).

Implements annual Keeper independence attestation with:
- Attestation submission with signature verification
- Deadline checking and capability suspension
- Declaration change tracking and anomaly notification
- History queries with change highlighting

Constitutional Constraints:
- FR98: Anomalous signature patterns SHALL be flagged for manual review
- FR133: Keepers SHALL annually attest independence; attestation recorded
- CT-9: Attackers are patient - aggregate erosion must be detected
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: Witnessing creates accountability -> All events witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before any operation
2. WITNESS EVERYTHING - All attestation events must be witnessed
3. FAIL LOUD - Failed event write = attestation failure
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from structlog import get_logger

from src.application.ports.anomaly_detector import AnomalyDetectorProtocol
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.independence_attestation import (
    IndependenceAttestationProtocol,
)
from src.application.services.event_writer_service import EventWriterService
from src.application.services.keeper_signature_service import KeeperSignatureService
from src.domain.errors.independence_attestation import (
    CapabilitySuspendedError,
    DuplicateIndependenceAttestationError,
    InvalidIndependenceSignatureError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.independence_attestation import (
    DECLARATION_CHANGE_DETECTED_EVENT_TYPE,
    INDEPENDENCE_ATTESTATION_EVENT_TYPE,
    KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE,
    DeclarationChangeDetectedPayload,
    IndependenceAttestationPayload,
    KeeperIndependenceSuspendedPayload,
)
from src.domain.events.override_abuse import AnomalyType
from src.domain.models.independence_attestation import (
    ConflictDeclaration,
    IndependenceAttestation,
    calculate_deadline,
    get_current_attestation_year,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Capabilities suspended when attestation overdue
SUSPENDED_CAPABILITIES: list[str] = ["override"]


@dataclass(frozen=True)
class DeclarationDiff:
    """Comparison result between consecutive attestations."""

    added_conflicts: list[ConflictDeclaration]
    removed_conflicts: list[ConflictDeclaration]
    added_organizations: list[str]
    removed_organizations: list[str]
    has_changes: bool


@dataclass(frozen=True)
class IndependenceHistoryResponse:
    """Response for independence attestation history query."""

    attestations: list[IndependenceAttestation]
    declaration_changes: list[DeclarationDiff]
    is_suspended: bool
    current_year_attested: bool


class IndependenceAttestationService:
    """Service for Keeper independence attestation operations (FR98, FR133).

    This service orchestrates annual independence attestation submission,
    deadline checking, and declaration change tracking.

    Constitutional Constraints:
    - FR133: Annual independence attestation requirement
    - CT-9: Patient attacker detection via change tracking
    - CT-11: HALT CHECK FIRST at every operation
    - CT-12: All attestation events are witnessed

    Attributes:
        repository: Independence attestation storage protocol.
        signature_service: Keeper signature verification service.
        event_writer: Event writing service for witnessing.
        halt_checker: Halt state checker.
        anomaly_detector: Anomaly detection for pattern analysis.
    """

    def __init__(
        self,
        repository: IndependenceAttestationProtocol,
        signature_service: KeeperSignatureService,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
        anomaly_detector: AnomalyDetectorProtocol | None = None,
    ) -> None:
        """Initialize the independence attestation service.

        Args:
            repository: Independence attestation storage protocol.
            signature_service: Keeper signature verification service.
            event_writer: Event writing service for witnessing.
            halt_checker: Halt state checker.
            anomaly_detector: Optional anomaly detection for pattern analysis.
        """
        self._repository = repository
        self._signature_service = signature_service
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        self._anomaly_detector = anomaly_detector

    async def submit_independence_attestation(
        self,
        keeper_id: str,
        conflicts: list[ConflictDeclaration],
        organizations: list[str],
        signature: bytes,
    ) -> IndependenceAttestation:
        """Submit an annual independence attestation (FR133).

        Args:
            keeper_id: The Keeper making the attestation.
            conflicts: List of declared conflicts of interest.
            organizations: List of affiliated organizations.
            signature: Ed25519 signature over attestation content.

        Returns:
            The recorded IndependenceAttestation.

        Raises:
            SystemHaltedError: If system is in HALT state (CT-11).
            InvalidIndependenceSignatureError: If signature verification fails.
            DuplicateIndependenceAttestationError: If already attested for year.
        """
        log = logger.bind(keeper_id=keeper_id)
        log.info("Submitting independence attestation")

        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            log.warning("Independence attestation rejected - system halted")
            raise SystemHaltedError("Cannot submit attestation during system halt")

        # Verify Keeper signature (NFR22)
        is_valid = await self._signature_service.verify_signature(
            keeper_id=keeper_id,
            message=self._build_signable_content(keeper_id, conflicts, organizations),
            signature=signature,
        )
        if not is_valid:
            log.warning("Invalid attestation signature")
            raise InvalidIndependenceSignatureError(keeper_id)

        # Get current attestation year
        current_year = get_current_attestation_year()

        # Check for duplicate attestation
        existing = await self._repository.get_attestation(keeper_id, current_year)
        if existing is not None:
            log.warning("Duplicate attestation for year", year=current_year)
            raise DuplicateIndependenceAttestationError(keeper_id, current_year)

        # Get previous attestation for comparison
        previous = await self._repository.get_latest_attestation(keeper_id)

        # Create attestation record
        now = datetime.now(timezone.utc)
        attestation = IndependenceAttestation(
            id=uuid4(),
            keeper_id=keeper_id,
            attested_at=now,
            attestation_year=current_year,
            conflict_declarations=conflicts,
            affiliated_organizations=organizations,
            signature=signature,
        )

        # Record attestation
        await self._repository.record_attestation(attestation)

        # Write witnessed event (CT-12)
        payload = IndependenceAttestationPayload(
            keeper_id=keeper_id,
            attestation_year=current_year,
            conflict_count=len(conflicts),
            organization_count=len(organizations),
            attested_at=now,
        )
        await self._event_writer.write_event(
            event_type=INDEPENDENCE_ATTESTATION_EVENT_TYPE,
            payload=payload.signable_content(),
        )

        # Check for declaration changes (FP-3)
        if previous is not None:
            diff = self._get_declaration_diff(previous, attestation)
            if diff.has_changes:
                await self._handle_declaration_change(
                    keeper_id, current_year, previous, attestation, diff
                )

        # Clear suspension if was suspended
        if await self._repository.is_keeper_suspended(keeper_id):
            await self._repository.clear_suspension(keeper_id)
            log.info("Suspension cleared after attestation")

        log.info("Independence attestation recorded", year=current_year)
        return attestation

    async def check_attestation_deadlines(self) -> list[str]:
        """Check for overdue attestations and suspend capabilities (FR133).

        This is a background task that should be run periodically
        to detect Keepers who have missed their attestation deadline.

        Returns:
            List of Keeper IDs newly suspended.

        Raises:
            SystemHaltedError: If system is in HALT state (CT-11).
        """
        log = logger.bind(operation="check_deadlines")
        log.info("Checking attestation deadlines")

        # HALT CHECK FIRST (CT-11)
        if await self._halt_checker.is_halted():
            log.warning("Deadline check skipped - system halted")
            raise SystemHaltedError("Cannot check deadlines during system halt")

        suspended_keepers: list[str] = []
        current_year = get_current_attestation_year()

        # Get all active Keepers
        keepers = await self._repository.get_all_active_keepers()

        for keeper_id in keepers:
            # Skip already suspended
            if await self._repository.is_keeper_suspended(keeper_id):
                continue

            # Check for current year attestation
            attestation = await self._repository.get_attestation(
                keeper_id, current_year
            )
            if attestation is not None:
                continue  # Has valid attestation

            # Calculate deadline based on previous attestation
            previous = await self._repository.get_latest_attestation(keeper_id)
            first_date = previous.attested_at if previous else None
            deadline = calculate_deadline(first_date, current_year)

            # Check if past deadline + grace period
            now = datetime.now(timezone.utc)
            if now > deadline:
                await self._suspend_keeper(keeper_id, deadline)
                suspended_keepers.append(keeper_id)

        log.info("Deadline check complete", suspended_count=len(suspended_keepers))
        return suspended_keepers

    async def get_keeper_independence_history(
        self, keeper_id: str
    ) -> IndependenceHistoryResponse:
        """Get independence attestation history with change tracking (AC3).

        Args:
            keeper_id: The Keeper to query.

        Returns:
            IndependenceHistoryResponse with attestations and changes.
        """
        attestations = await self._repository.get_attestation_history(keeper_id)
        is_suspended = await self._repository.is_keeper_suspended(keeper_id)

        # Calculate changes between consecutive years
        changes: list[DeclarationDiff] = []
        for i in range(1, len(attestations)):
            diff = self._get_declaration_diff(attestations[i - 1], attestations[i])
            changes.append(diff)

        # Check if current year is attested
        current_year = get_current_attestation_year()
        current_year_attested = any(
            a.attestation_year == current_year for a in attestations
        )

        return IndependenceHistoryResponse(
            attestations=attestations,
            declaration_changes=changes,
            is_suspended=is_suspended,
            current_year_attested=current_year_attested,
        )

    async def validate_keeper_can_override(self, keeper_id: str) -> bool:
        """Validate Keeper can perform override operations (FR133).

        Should be called by OverrideService before executing overrides.

        Args:
            keeper_id: The Keeper attempting override.

        Returns:
            True if Keeper can override.

        Raises:
            CapabilitySuspendedError: If Keeper is suspended.
        """
        if await self._repository.is_keeper_suspended(keeper_id):
            raise CapabilitySuspendedError(keeper_id)
        return True

    def _get_declaration_diff(
        self,
        prev: IndependenceAttestation | None,
        curr: IndependenceAttestation,
    ) -> DeclarationDiff:
        """Compare declarations between consecutive attestations.

        Args:
            prev: Previous attestation (or None if first).
            curr: Current attestation.

        Returns:
            DeclarationDiff with added/removed items.
        """
        if prev is None:
            has_changes = (
                len(curr.conflict_declarations) > 0
                or len(curr.affiliated_organizations) > 0
            )
            return DeclarationDiff(
                added_conflicts=list(curr.conflict_declarations),
                removed_conflicts=[],
                added_organizations=list(curr.affiliated_organizations),
                removed_organizations=[],
                has_changes=has_changes,
            )

        # Use tuples for hashable comparison
        prev_conflicts = set(prev.conflict_declarations)
        curr_conflicts = set(curr.conflict_declarations)
        prev_orgs = set(prev.affiliated_organizations)
        curr_orgs = set(curr.affiliated_organizations)

        added_conflicts = list(curr_conflicts - prev_conflicts)
        removed_conflicts = list(prev_conflicts - curr_conflicts)
        added_orgs = list(curr_orgs - prev_orgs)
        removed_orgs = list(prev_orgs - curr_orgs)

        has_changes = bool(
            added_conflicts or removed_conflicts or added_orgs or removed_orgs
        )

        return DeclarationDiff(
            added_conflicts=added_conflicts,
            removed_conflicts=removed_conflicts,
            added_organizations=added_orgs,
            removed_organizations=removed_orgs,
            has_changes=has_changes,
        )

    async def _handle_declaration_change(
        self,
        keeper_id: str,
        year: int,
        prev: IndependenceAttestation,
        curr: IndependenceAttestation,
        diff: DeclarationDiff,
    ) -> None:
        """Handle detected declaration changes (FP-3, ADR-7).

        Writes change event and notifies anomaly detector.

        Args:
            keeper_id: The Keeper whose declarations changed.
            year: Current attestation year.
            prev: Previous attestation.
            curr: Current attestation.
            diff: The calculated diff.
        """
        log = logger.bind(keeper_id=keeper_id, year=year)
        log.info("Declaration change detected")

        # Build change summary
        parts = []
        if diff.added_conflicts:
            parts.append(f"Added {len(diff.added_conflicts)} conflict(s)")
        if diff.removed_conflicts:
            parts.append(f"Removed {len(diff.removed_conflicts)} conflict(s)")
        if diff.added_organizations:
            parts.append(f"Added {len(diff.added_organizations)} organization(s)")
        if diff.removed_organizations:
            parts.append(f"Removed {len(diff.removed_organizations)} organization(s)")
        change_summary = "; ".join(parts) if parts else "No changes"

        # Write witnessed event (CT-12)
        now = datetime.now(timezone.utc)
        payload = DeclarationChangeDetectedPayload(
            keeper_id=keeper_id,
            attestation_year=year,
            previous_conflicts=len(prev.conflict_declarations),
            current_conflicts=len(curr.conflict_declarations),
            change_summary=change_summary,
            detected_at=now,
        )
        await self._event_writer.write_event(
            event_type=DECLARATION_CHANGE_DETECTED_EVENT_TYPE,
            payload=payload.signable_content(),
        )

        # Notify anomaly detector if available (ADR-7)
        if self._anomaly_detector is not None:
            await self._anomaly_detector.report_anomaly(
                anomaly_type=AnomalyType.PATTERN_CORRELATION,
                keeper_ids=[keeper_id],
                details=f"Independence declaration change: {change_summary}",
                confidence=0.5,  # Medium confidence for single change
            )

    async def _suspend_keeper(self, keeper_id: str, deadline: datetime) -> None:
        """Suspend a Keeper's capabilities for missed deadline.

        Args:
            keeper_id: The Keeper to suspend.
            deadline: The deadline that was missed.
        """
        log = logger.bind(keeper_id=keeper_id)
        log.warning("Suspending keeper for missed deadline", deadline=deadline)

        # Mark suspended
        await self._repository.mark_keeper_suspended(
            keeper_id, "Independence attestation deadline missed"
        )

        # Write witnessed event (CT-12)
        now = datetime.now(timezone.utc)
        payload = KeeperIndependenceSuspendedPayload(
            keeper_id=keeper_id,
            deadline_missed=deadline,
            suspended_at=now,
            capabilities_suspended=SUSPENDED_CAPABILITIES,
        )
        await self._event_writer.write_event(
            event_type=KEEPER_INDEPENDENCE_SUSPENDED_EVENT_TYPE,
            payload=payload.signable_content(),
        )

    def _build_signable_content(
        self,
        keeper_id: str,
        conflicts: list[ConflictDeclaration],
        organizations: list[str],
    ) -> bytes:
        """Build signable content for signature verification.

        Args:
            keeper_id: The Keeper identifier.
            conflicts: List of conflict declarations.
            organizations: List of organizations.

        Returns:
            Bytes to verify signature against.
        """
        import json

        return json.dumps(
            {
                "keeper_id": keeper_id,
                "conflict_count": len(conflicts),
                "organization_count": len(organizations),
                "year": get_current_attestation_year(),
            },
            sort_keys=True,
        ).encode("utf-8")
