"""Verification Port - Interface for independent ledger verification.

Story: consent-gov-9.3: Independent Verification

This port defines the interface for independently verifying ledger
integrity. All verification operations can be performed without
requiring cooperation from the system.

Constitutional Constraints:
- FR58: Any participant can independently verify ledger integrity
- NFR-AUDIT-06: Ledger export enables deterministic state derivation by replay
- AC1: Independent hash chain verification
- AC2: Independent Merkle proof verification
- AC4: Verification possible offline with exported ledger

Verification Philosophy:
- Verification requires NO system cooperation
- All needed data is in the exported ledger
- Results include detailed issue information
- Math provides guarantees - no trust required
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.governance.audit.ledger_export import LedgerExport
    from src.domain.governance.audit.verification_result import (
        DetectedIssue,
        VerificationResult,
    )


@runtime_checkable
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


@runtime_checkable
class VerificationPort(Protocol):
    """Port for independent ledger verification.

    This port provides methods for independently verifying the
    integrity of an exported ledger. All verification can be
    performed offline without any system cooperation.

    Constitutional Guarantees:
    - Verification is independent (no trusted party)
    - Works with exported ledger only
    - Offline capable (no network required)
    - Detailed results with issue information

    Verification Checks:
    1. Hash chain integrity (no tampering)
    2. Sequence completeness (no missing events)
    3. Merkle root correctness (no omissions)
    4. State replay validity (events produce expected state)
    """

    async def verify_complete(
        self,
        ledger_export: "LedgerExport",
        verifier_id: UUID | None = None,
    ) -> "VerificationResult":
        """Perform complete independent verification.

        Runs all verification checks on the exported ledger:
        1. Hash chain verification
        2. Sequence completeness check
        3. Merkle root verification (if applicable)
        4. State replay verification

        Can be run offline (event emission optional).

        Args:
            ledger_export: The exported ledger to verify.
            verifier_id: Optional verifier ID (for audit logging if online).

        Returns:
            VerificationResult with detailed results of all checks.

        Constitutional Reference:
            - FR58: Independent ledger verification
        """
        ...

    async def verify_hash_chain(
        self,
        events: list,
    ) -> tuple[bool, list["DetectedIssue"]]:
        """Verify hash chain independently.

        Checks that each event's hash correctly links to the
        previous event, proving:
        - No events were modified (hash would change)
        - No events were removed (chain would break)
        - No events were inserted (links would fail)

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (chain_valid, issues_detected).

        Constitutional Reference:
            - AC1: Independent hash chain verification
        """
        ...

    async def verify_sequence(
        self,
        events: list,
    ) -> tuple[bool, list["DetectedIssue"]]:
        """Verify sequence is complete with no gaps.

        Checks that sequence numbers are continuous from 1 to N
        with no missing numbers.

        Args:
            events: List of events to verify in sequence order.

        Returns:
            Tuple of (sequence_complete, issues_detected).

        Constitutional Reference:
            - AC7: Verification detects missing events
        """
        ...

    async def verify_merkle(
        self,
        events: list,
        expected_root: str,
    ) -> tuple[bool, list["DetectedIssue"]]:
        """Verify Merkle root matches computed root.

        Computes the Merkle root from event hashes and compares
        to the expected root from the proof.

        Args:
            events: List of events to compute root from.
            expected_root: Expected Merkle root from proof.

        Returns:
            Tuple of (merkle_valid, issues_detected).

        Constitutional Reference:
            - AC2: Independent Merkle proof verification
        """
        ...

    async def verify_state_replay(
        self,
        events: list,
    ) -> tuple[bool, list["DetectedIssue"]]:
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
        ...

    async def verify_offline(
        self,
        ledger_json: str,
    ) -> "VerificationResult":
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
        ...
