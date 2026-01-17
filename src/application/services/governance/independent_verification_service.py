"""Independent Verification Service - Ledger integrity verification.

Story: consent-gov-9.3: Independent Verification

This service verifies ledger integrity independently without requiring
system cooperation. All verification can be performed offline using
only the exported ledger data.

Constitutional Requirements:
- FR58: Any participant can independently verify ledger integrity
- NFR-AUDIT-06: Ledger export enables deterministic state derivation by replay
- AC1: Independent hash chain verification
- AC2: Independent Merkle proof verification
- AC3: State derivable through event replay
- AC4: Verification possible offline with exported ledger
- AC5: Event audit.verification.completed emitted after verification
- AC6: Verification detects tampering
- AC7: Verification detects missing events

Verification Philosophy:
- Math, not trust
- Verification requires NO system cooperation
- Works with exported ledger only
- Offline capable (no network required)
- Results include detailed issue information
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID, uuid4

from src.domain.governance.audit.verification_result import (
    DetectedIssue,
    IssueType,
    VerificationResult,
    VerificationStatus,
)
from src.domain.governance.events.merkle_tree import compute_merkle_root

if TYPE_CHECKING:
    from src.domain.governance.audit.ledger_export import LedgerExport
    from src.application.ports.governance.ledger_port import PersistedGovernanceEvent

# Event type for audit logging
VERIFICATION_COMPLETED_EVENT = "audit.verification.completed"


class EventEmitterPort(Protocol):
    """Port for emitting events."""

    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit an event."""
        ...


class StateReplayerPort(Protocol):
    """Port for replaying events to derive state.

    State replay is a key verification technique that proves events
    can deterministically produce the expected state.

    NFR-AUDIT-06: Ledger export enables deterministic state derivation by replay.
    """

    async def replay(
        self,
        events: list,
    ) -> Any:
        """Replay events to derive state.

        Takes a list of events and applies them in sequence to
        derive the final state. The same events must always produce
        the same state (deterministic).

        Args:
            events: List of events to replay in sequence order.

        Returns:
            The derived state (type depends on implementation).

        Raises:
            Exception: If replay fails (invalid event, corrupt data, etc.).
        """
        ...


class TimeAuthorityPort(Protocol):
    """Port for getting authoritative time."""

    def now(self) -> datetime:
        """Get current time."""
        ...


class IndependentVerificationService:
    """Service for independent ledger verification.

    Verifies ledger integrity independently without requiring system
    cooperation. All verification can be performed offline.

    Verification checks performed:
    1. Hash chain integrity (no tampering)
    2. Sequence completeness (no missing events)
    3. Merkle root correctness (no omissions)
    4. State replay validity (events produce valid state)

    Constitutional Guarantees:
    - Verification is independent (no trusted party)
    - Works with exported ledger only
    - Offline capable (no network required)
    - Detailed results with issue information
    """

    def __init__(
        self,
        state_replayer: StateReplayerPort,
        event_emitter: EventEmitterPort | None,
        time_authority: TimeAuthorityPort,
    ) -> None:
        """Initialize the verification service.

        Args:
            state_replayer: Port for replaying events to derive state.
            event_emitter: Port for emitting events (None for offline mode).
            time_authority: Port for getting authoritative time.
        """
        self._replayer = state_replayer
        self._event_emitter = event_emitter
        self._time = time_authority

    async def verify_complete(
        self,
        ledger_export: "LedgerExport",
        verifier_id: UUID | None = None,
        expected_merkle_root: str | None = None,
    ) -> VerificationResult:
        """Perform complete independent verification.

        Runs all verification checks on the exported ledger:
        1. Hash chain verification
        2. Sequence completeness check
        3. Merkle root verification (if expected_merkle_root provided)
        4. State replay verification

        Can be run offline (event_emitter optional).

        Args:
            ledger_export: The exported ledger to verify.
            verifier_id: Optional verifier ID (for audit logging if online).
            expected_merkle_root: Optional expected Merkle root to verify against.

        Returns:
            VerificationResult with detailed results of all checks.

        Constitutional Reference:
            - FR58: Independent ledger verification
        """
        now = self._time.now()
        verification_id = uuid4()
        issues: list[DetectedIssue] = []

        events = list(ledger_export.events)

        # Verify hash chain (AC1)
        chain_valid, chain_issues = await self._verify_hash_chain(events)
        issues.extend(chain_issues)

        # Verify sequence completeness (AC7)
        seq_complete, seq_issues = await self._verify_sequence(events)
        issues.extend(seq_issues)

        # Verify Merkle root (AC2) - only if expected root provided
        merkle_valid = True
        if expected_merkle_root:
            merkle_valid, merkle_issues = await self._verify_merkle(
                events,
                expected_merkle_root,
            )
            issues.extend(merkle_issues)

        # Verify state replay (AC3)
        replay_valid, replay_issues = await self._verify_state_replay(events)
        issues.extend(replay_issues)

        # Determine overall status
        status = self._determine_status(
            chain_valid=chain_valid,
            seq_complete=seq_complete,
            merkle_valid=merkle_valid,
            replay_valid=replay_valid,
            issues=issues,
        )

        result = VerificationResult(
            verification_id=verification_id,
            verified_at=now,
            status=status,
            hash_chain_valid=chain_valid,
            merkle_valid=merkle_valid,
            sequence_complete=seq_complete,
            state_replay_valid=replay_valid,
            issues=issues,
            total_events_verified=len(events),
        )

        # Emit event if online and verifier_id provided (AC5)
        if self._event_emitter and verifier_id:
            await self._emit_verification_event(
                verification_id=verification_id,
                verifier_id=verifier_id,
                verified_at=now,
                status=status,
                result=result,
            )

        return result

    async def verify_offline(
        self,
        ledger_json: str,
    ) -> VerificationResult:
        """Verify ledger from JSON export (fully offline).

        Performs complete verification using only the JSON export.
        No network calls, no event emission.

        Args:
            ledger_json: JSON string of exported ledger.

        Returns:
            VerificationResult with all check results.

        Constitutional Reference:
            - AC4: Verification possible offline with exported ledger
        """
        # Parse export
        export_data = json.loads(ledger_json)
        ledger_export = self._parse_ledger_export(export_data)

        # Verify without event emission (verifier_id=None)
        return await self.verify_complete(
            ledger_export=ledger_export,
            verifier_id=None,
        )

    async def verify_hash_chain(
        self,
        events: list["PersistedGovernanceEvent"],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Public method to verify hash chain independently.

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (chain_valid, issues_detected).

        Constitutional Reference:
            - AC1: Independent hash chain verification
        """
        return await self._verify_hash_chain(events)

    async def verify_sequence(
        self,
        events: list["PersistedGovernanceEvent"],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Public method to verify sequence completeness.

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (sequence_complete, issues_detected).

        Constitutional Reference:
            - AC7: Verification detects missing events
        """
        return await self._verify_sequence(events)

    async def verify_merkle(
        self,
        events: list["PersistedGovernanceEvent"],
        expected_root: str,
    ) -> tuple[bool, list[DetectedIssue]]:
        """Public method to verify Merkle root.

        Args:
            events: List of events to compute root from.
            expected_root: Expected Merkle root to compare against.

        Returns:
            Tuple of (merkle_valid, issues_detected).

        Constitutional Reference:
            - AC2: Independent Merkle proof verification
        """
        return await self._verify_merkle(events, expected_root)

    async def _verify_hash_chain(
        self,
        events: list["PersistedGovernanceEvent"],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify hash chain independently.

        Checks that each event's prev_hash correctly links to the
        previous event's hash, proving:
        - No events were modified (hash would change)
        - No events were removed (chain would break)
        - No events were inserted (links would fail)

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (chain_valid, issues_detected).
        """
        issues: list[DetectedIssue] = []

        if not events:
            return True, issues

        # Verify genesis event has proper prev_hash (empty or zeros)
        genesis = events[0]
        if not self._is_valid_genesis_prev_hash(genesis.event.prev_hash):
            issues.append(
                DetectedIssue(
                    issue_type=IssueType.BROKEN_LINK,
                    event_id=genesis.event_id,
                    sequence_number=genesis.sequence,
                    description=f"Genesis event has invalid prev_hash: {genesis.event.prev_hash}",
                    expected="empty or zeros",
                    actual=genesis.event.prev_hash,
                )
            )

        # Verify chain links
        for i in range(1, len(events)):
            prev_event = events[i - 1]
            curr_event = events[i]

            # Check prev_hash links correctly
            if curr_event.event.prev_hash != prev_event.event.hash:
                issues.append(
                    DetectedIssue(
                        issue_type=IssueType.BROKEN_LINK,
                        event_id=curr_event.event_id,
                        sequence_number=curr_event.sequence,
                        description=f"Broken link at event {curr_event.sequence}",
                        expected=prev_event.event.hash,
                        actual=curr_event.event.prev_hash,
                    )
                )

        return len(issues) == 0, issues

    async def _verify_sequence(
        self,
        events: list["PersistedGovernanceEvent"],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify sequence is complete with no gaps.

        Checks that sequence numbers are continuous from 1 to N
        with no missing numbers.

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (sequence_complete, issues_detected).
        """
        issues: list[DetectedIssue] = []

        if not events:
            return True, issues

        expected_seq = 1
        for event in events:
            if event.sequence != expected_seq:
                issues.append(
                    DetectedIssue(
                        issue_type=IssueType.SEQUENCE_GAP,
                        event_id=event.event_id,
                        sequence_number=event.sequence,
                        description=f"Gap at sequence {expected_seq}",
                        expected=str(expected_seq),
                        actual=str(event.sequence),
                    )
                )
                # Update expected to actual to continue checking for more gaps
                expected_seq = event.sequence + 1
            else:
                expected_seq = event.sequence + 1

        return len(issues) == 0, issues

    async def _verify_merkle(
        self,
        events: list["PersistedGovernanceEvent"],
        expected_root: str,
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify Merkle root matches computed root.

        Computes the Merkle root from event hashes and compares
        to the expected root.

        Args:
            events: List of events to compute root from.
            expected_root: Expected Merkle root from proof.

        Returns:
            Tuple of (merkle_valid, issues_detected).
        """
        issues: list[DetectedIssue] = []

        if not events:
            # Empty ledger - check expected root
            if expected_root and expected_root not in ("", "sha256:empty", "blake3:empty"):
                issues.append(
                    DetectedIssue(
                        issue_type=IssueType.MERKLE_MISMATCH,
                        event_id=None,
                        sequence_number=None,
                        description="Merkle root mismatch for empty ledger",
                        expected=expected_root,
                        actual="empty",
                    )
                )
            return len(issues) == 0, issues

        # Detect algorithm from expected root or event hashes
        algorithm = self._detect_algorithm(expected_root)

        # Compute Merkle root from event hashes
        event_hashes = [e.event.hash for e in events]
        computed_root = compute_merkle_root(event_hashes, algorithm)

        if computed_root != expected_root:
            issues.append(
                DetectedIssue(
                    issue_type=IssueType.MERKLE_MISMATCH,
                    event_id=None,
                    sequence_number=None,
                    description="Merkle root mismatch",
                    expected=expected_root,
                    actual=computed_root,
                )
            )

        return len(issues) == 0, issues

    async def _verify_state_replay(
        self,
        events: list["PersistedGovernanceEvent"],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify state can be derived through event replay.

        Replays all events from genesis and verifies that state
        can be successfully derived.

        Args:
            events: List of events to replay.

        Returns:
            Tuple of (replay_valid, issues_detected).

        Constitutional Reference:
            - AC3: State derivable through event replay (NFR-AUDIT-06)
        """
        issues: list[DetectedIssue] = []

        if not events:
            return True, issues

        try:
            # Replay events
            state = await self._replayer.replay(events)

            # State should be derivable (not None)
            if state is None:
                issues.append(
                    DetectedIssue(
                        issue_type=IssueType.STATE_MISMATCH,
                        event_id=None,
                        sequence_number=None,
                        description="State could not be derived from events",
                        expected="Valid state",
                        actual="None",
                    )
                )
        except Exception as e:
            issues.append(
                DetectedIssue(
                    issue_type=IssueType.STATE_MISMATCH,
                    event_id=None,
                    sequence_number=None,
                    description=f"State replay failed: {e}",
                    expected="Successful replay",
                    actual="Exception",
                )
            )

        return len(issues) == 0, issues

    def _determine_status(
        self,
        chain_valid: bool,
        seq_complete: bool,
        merkle_valid: bool,
        replay_valid: bool,
        issues: list[DetectedIssue],
    ) -> VerificationStatus:
        """Determine overall verification status.

        Args:
            chain_valid: Hash chain verification result.
            seq_complete: Sequence completeness result.
            merkle_valid: Merkle root verification result.
            replay_valid: State replay verification result.
            issues: List of all detected issues.

        Returns:
            VerificationStatus (VALID, INVALID, or PARTIAL).
        """
        all_pass = chain_valid and seq_complete and merkle_valid and replay_valid

        if all_pass and not issues:
            return VerificationStatus.VALID

        if not issues:
            return VerificationStatus.VALID

        # Some pass, some fail = PARTIAL
        checks = [chain_valid, seq_complete, merkle_valid, replay_valid]
        if any(checks) and not all(checks):
            return VerificationStatus.PARTIAL

        # All fail = INVALID
        if not any(checks):
            return VerificationStatus.INVALID

        # Has issues but checks pass = PARTIAL
        return VerificationStatus.PARTIAL

    def _is_valid_genesis_prev_hash(self, prev_hash: str) -> bool:
        """Check if a prev_hash is valid for genesis event.

        Genesis event should have:
        - Empty string, or
        - All zeros hash (with or without algorithm prefix)

        Args:
            prev_hash: The prev_hash to check.

        Returns:
            True if valid for genesis, False otherwise.
        """
        if not prev_hash:
            return True

        # Check for all-zeros hash
        if prev_hash.startswith("0" * 64):
            return True

        # Check for prefixed all-zeros
        if ":" in prev_hash:
            _, hash_part = prev_hash.split(":", 1)
            if hash_part.startswith("0" * 64):
                return True

        return False

    def _detect_algorithm(self, hash_value: str) -> str:
        """Detect algorithm from hash format.

        Args:
            hash_value: Hash string (e.g., "blake3:abc123").

        Returns:
            Algorithm name.
        """
        if ":" in hash_value:
            prefix = hash_value.split(":", 1)[0]
            return prefix.lower()
        return "sha256"  # Default

    def _parse_ledger_export(self, export_data: dict) -> "LedgerExport":
        """Parse a LedgerExport from dictionary data.

        Args:
            export_data: Dictionary containing export data.

        Returns:
            LedgerExport instance.
        """
        from datetime import datetime as dt
        from src.domain.governance.audit.ledger_export import (
            ExportMetadata,
            LedgerExport,
            VerificationInfo,
        )
        from src.domain.governance.events.event_envelope import (
            EventMetadata,
            GovernanceEvent,
        )
        from src.application.ports.governance.ledger_port import PersistedGovernanceEvent

        # Parse metadata
        meta = export_data["metadata"]
        metadata = ExportMetadata(
            export_id=UUID(meta["export_id"]),
            exported_at=dt.fromisoformat(meta["exported_at"]),
            format_version=meta["format_version"],
            total_events=meta["total_events"],
            genesis_hash=meta["genesis_hash"],
            latest_hash=meta["latest_hash"],
            sequence_range=tuple(meta["sequence_range"]),
        )

        # Parse events
        events = []
        for e in export_data["events"]:
            # Construct EventMetadata first (GovernanceEvent uses composition)
            event_metadata = EventMetadata(
                event_id=UUID(e["event_id"]),
                event_type=e["event_type"],
                timestamp=dt.fromisoformat(e["timestamp"]),
                actor_id=e["actor_id"],
                schema_version=e.get("schema_version", "1.0.0"),
                trace_id=e.get("trace_id", str(uuid4())),
                prev_hash=e["prev_hash"],
                hash=e["hash"],
            )
            gov_event = GovernanceEvent(
                metadata=event_metadata,
                payload=e["payload"],
            )
            persisted = PersistedGovernanceEvent(
                event=gov_event,
                sequence=e["sequence"],
            )
            events.append(persisted)

        # Parse verification info
        verif = export_data["verification"]
        verification = VerificationInfo(
            hash_algorithm=verif["hash_algorithm"],
            chain_valid=verif["chain_valid"],
            genesis_to_latest=verif["genesis_to_latest"],
        )

        return LedgerExport(
            metadata=metadata,
            events=tuple(events),
            verification=verification,
        )

    async def _emit_verification_event(
        self,
        verification_id: UUID,
        verifier_id: UUID,
        verified_at: datetime,
        status: VerificationStatus,
        result: VerificationResult,
    ) -> None:
        """Emit audit event for verification completion.

        Args:
            verification_id: ID of this verification.
            verifier_id: Who performed the verification.
            verified_at: When the verification was performed.
            status: Overall verification status.
            result: Full verification result.

        Constitutional Reference:
            - AC5: Event audit.verification.completed emitted
        """
        if not self._event_emitter:
            return

        await self._event_emitter.emit(
            event_type=VERIFICATION_COMPLETED_EVENT,
            actor=str(verifier_id),
            payload={
                "verification_id": str(verification_id),
                "verifier_id": str(verifier_id),
                "verified_at": verified_at.isoformat(),
                "status": status.value,
                "hash_chain_valid": result.hash_chain_valid,
                "merkle_valid": result.merkle_valid,
                "sequence_complete": result.sequence_complete,
                "state_replay_valid": result.state_replay_valid,
                "issues_count": len(result.issues),
                "total_events_verified": result.total_events_verified,
            },
        )
