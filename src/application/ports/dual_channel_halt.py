"""Dual-Channel Halt Transport port (Story 3.3, ADR-3).

This port defines the contract for dual-channel halt transport.
Halt signals propagate via both Redis Streams (fast) and DB flag (durable).

ADR-3: Partition Behavior + Halt Durability
- Dual-channel halt: Redis Streams for speed + DB halt flag for safety
- Halt is **sticky** once set (clearing requires witnessed ceremony - Story 3.4)
- Every operation boundary MUST check halt
- If EITHER channel indicates halt -> component halts
- DB is canonical when channels disagree

Constitutional Constraints:
- CT-11 (Silent failure destroys legitimacy): Halt channel failures MUST be logged
- CT-12 (Witnessing creates accountability): Halt writes include crisis_event_id
- CT-13 (Integrity outranks availability): Dual-channel ensures halt cannot be missed

Red Team Hardening (RT-2):
- Halt from Redis must be confirmed against DB within 5 seconds
- Phantom halts detectable via channel mismatch analysis
- Conflict resolution is logged as an event

Developer Golden Rules:
1. HALT FIRST - Check dual-channel halt before every operation
2. DB IS CANONICAL - When Redis and DB disagree, trust DB
3. LOG CONFLICTS - Every channel mismatch must be logged
4. FAIL LOUD - Never swallow halt check errors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.domain.events.halt_cleared import HaltClearedPayload
    from src.domain.models.ceremony_evidence import CeremonyEvidence


# RT-2: Halt from Redis must be confirmed against DB within 5 seconds
CONFIRMATION_TIMEOUT_SECONDS: float = 5.0


@dataclass(frozen=True)
class HaltFlagState:
    """Immutable state of the halt flag.

    Represents the current halt state from the DB (canonical source)
    or Redis (fast propagation channel).

    Attributes:
        is_halted: Whether the system is currently halted.
        reason: Human-readable reason for the halt (e.g., "FR17: Fork detected").
        crisis_event_id: UUID of the ConstitutionalCrisisEvent that triggered halt.
                        Provides audit trail linking halt to its trigger.
    """

    is_halted: bool
    reason: str | None
    crisis_event_id: UUID | None


class DualChannelHaltTransport(ABC):
    """Abstract interface for dual-channel halt transport.

    Implements ADR-3: Partition Behavior + Halt Durability.
    Halt signals propagate via two channels:
    - Redis Streams: Fast propagation (~1ms latency)
    - DB halt flag: Durable storage (canonical source of truth)

    Constitutional Constraints:
    - FR17: System SHALL halt immediately when fork detected
    - CT-11: Silent failure destroys legitimacy -> Halt MUST be logged
    - CT-13: Integrity outranks availability -> Availability sacrificed
    - RT-2: Redis halt confirmed against DB within 5 seconds

    Dual-Channel Semantics:
    - write_halt() writes to BOTH channels atomically
    - is_halted() returns True if EITHER channel indicates halt
    - DB is canonical when channels disagree
    - Conflict resolution logs the mismatch for investigation

    Example:
        >>> # Write halt to both channels
        >>> await transport.write_halt(
        ...     reason="FR17: Fork detected - 2 conflicting events",
        ...     crisis_event_id=crisis_event_uuid,
        ... )
        >>> # Check halt state (either channel)
        >>> if await transport.is_halted():
        ...     raise SystemHaltedError("System halted")
    """

    @property
    @abstractmethod
    def confirmation_timeout_seconds(self) -> float:
        """Timeout for Redis-to-DB confirmation (RT-2).

        Per RT-2: Halt from Redis must be confirmed against DB within
        this timeout. If DB does not confirm, conflict resolution triggers.

        Returns:
            Timeout in seconds. Default: 5.0 (CONFIRMATION_TIMEOUT_SECONDS).
        """
        ...

    @abstractmethod
    async def write_halt(
        self,
        reason: str,
        crisis_event_id: UUID,
    ) -> None:
        """Write halt signal to BOTH channels (Redis + DB).

        Atomic dual-channel write: both channels must succeed.
        If either fails, the operation fails and system may be in
        inconsistent state (requires manual investigation).

        Constitutional Constraint (AC1):
        - Halt written to Redis Streams for fast propagation
        - Halt written to DB halt flag for durability
        - Both writes complete before halt is considered "sent"

        Args:
            reason: Human-readable reason for halt (e.g., "FR17: Fork detected")
            crisis_event_id: UUID of the witnessed ConstitutionalCrisisEvent.
                           Provides audit trail linking halt to its trigger.

        Raises:
            HaltWriteError: If either channel write fails.
        """
        ...

    @abstractmethod
    async def is_halted(self) -> bool:
        """Check if system is halted via EITHER channel.

        Dual-channel check: returns True if Redis OR DB indicates halt.
        This ensures halt cannot be missed even if one channel fails.

        Constitutional Constraint (AC2):
        - Checks both Redis stream consumer state AND DB halt flag
        - If EITHER indicates halt, the component halts

        Graceful Degradation (AC3):
        - If Redis is down, DB halt flag is the source of truth
        - If DB is down, system should already be halting (integrity uncertainty)

        Conflict Detection (AC4, AC5):
        - If Redis says halt but DB says not halted -> conflict detected
        - Conflict resolution runs: DB is canonical, Redis corrected
        - Conflict event is logged for investigation

        Returns:
            True if system is halted (either channel), False otherwise.
        """
        ...

    @abstractmethod
    async def get_halt_reason(self) -> str | None:
        """Get the reason for current halt state.

        Returns:
            The halt reason if halted, None if not halted.
        """
        ...

    @abstractmethod
    async def check_channels_consistent(self) -> bool:
        """Check if Redis and DB halt states are consistent.

        Compares halt state across both channels to detect drift.
        Used for monitoring and conflict detection.

        Returns:
            True if both channels agree, False if there's a mismatch.
        """
        ...

    @abstractmethod
    async def resolve_conflict(self) -> None:
        """Resolve halt channel conflict (AC4).

        When Redis and DB disagree, this method resolves the conflict:
        - DB is canonical (source of truth)
        - Redis state is corrected to match DB
        - Conflict event is logged for investigation

        Conflict Scenarios:
        1. Redis halted, DB not halted: Possible phantom halt (suspicious)
           -> Log warning, do NOT clear Redis halt (security measure)
        2. Redis not halted, DB halted: Propagation failure
           -> Propagate halt to Redis to restore consistency
        3. Both halted but different reasons: Log discrepancy
           -> Use DB reason as canonical
        """
        ...

    @abstractmethod
    async def clear_halt(
        self,
        ceremony_evidence: "CeremonyEvidence",
    ) -> "HaltClearedPayload":
        """Clear halt with proper ceremony evidence (Story 3.4, ADR-3).

        Halt is sticky once set. Clearing requires a witnessed ceremony
        with at least 2 Keeper approvers (ADR-6 Tier 1).

        Constitutional Constraints:
        - ADR-3: Halt is sticky - clearing requires witnessed ceremony
        - ADR-6: Tier 1 ceremony requires 2 Keepers
        - CT-11: Silent failure destroys legitimacy
        - CT-12: Witnessing creates accountability

        Process:
        1. Validate ceremony_evidence (>= 2 approvers, valid signatures)
        2. Create HaltClearedEvent
        3. Write HaltClearedEvent to event store (witnessed) BEFORE clear
        4. Clear DB halt flag via ceremony-authorized procedure
        5. Clear Redis halt state
        6. Return HaltClearedPayload

        Args:
            ceremony_evidence: CeremonyEvidence proving ceremony was conducted.
                              Must have >= 2 Keeper approvers.

        Returns:
            HaltClearedPayload with ceremony details.

        Raises:
            HaltClearDeniedError: If no ceremony evidence provided.
            InsufficientApproversError: If < 2 Keepers approved.
            InvalidCeremonyError: If any signature is invalid.
        """
        ...
