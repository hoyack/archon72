"""Verifiable witness selection service (FR59, FR60, FR61, FR116).

Provides verifiable witness selection with external entropy,
hash chain binding, pair rotation enforcement, and anomaly detection.

Constitutional Constraints:
- FR59: Verifiable randomness seeded from hash chain
- FR60: No witness pair appears twice in 24 hours
- FR61: External entropy source required
- FR116: Skip pairs excluded due to anomaly detection
- FR117: Witness pool minimum enforcement
- NFR57: Halt on entropy failure (not weak randomness)
- CT-11: HALT CHECK FIRST at every operation
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from src.application.ports.entropy_source import EntropySourceProtocol
from src.application.ports.event_store import EventStorePort
from src.application.ports.halt_checker import HaltChecker
from src.application.ports.witness_anomaly_detector import (
    WitnessAnomalyDetectorProtocol,
)
from src.application.ports.witness_pair_history import WitnessPairHistoryProtocol
from src.application.ports.witness_pool import WitnessPoolProtocol
from src.domain.errors.witness_selection import (
    AllWitnessesPairExhaustedError,
    EntropyUnavailableError,
    InsufficientWitnessPoolError,
    WitnessSelectionVerificationError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.witness_selection import (
    WitnessSelectionEventPayload,
)
from src.domain.models.witness_pair import WitnessPair
from src.domain.models.witness_selection import (
    SELECTION_ALGORITHM_VERSION,
    WitnessSelectionRecord,
    WitnessSelectionSeed,
    deterministic_select,
)

# System agent ID for witness selection service
WITNESS_SELECTION_SYSTEM_AGENT_ID = "SYSTEM:witness_selection_service"

# Default minimum witnesses for standard operations
DEFAULT_MINIMUM_WITNESSES = 6

# Minimum witnesses for high-stakes operations (FR117)
HIGH_STAKES_MINIMUM_WITNESSES = 12


class VerifiableWitnessSelectionService:
    """Service for verifiable witness selection (FR59, FR60, FR61, FR116).

    Provides witness selection with:
    1. External entropy (FR61) - from EntropySourceProtocol
    2. Hash chain binding (FR59) - from EventStorePort
    3. Deterministic algorithm - reproducible by observers
    4. Pair rotation enforcement (FR60) - via WitnessPairHistoryProtocol
    5. Anomaly-excluded pair skipping (FR116) - via WitnessAnomalyDetectorProtocol

    Constitutional Constraints:
    - CT-11: HALT CHECK FIRST at every public operation
    - FR59: Selection uses hash chain state + external entropy
    - FR60: No pair appears twice in 24 hours
    - FR61: External entropy required
    - FR116: Skip pairs excluded due to anomaly detection
    - FR117: Pool minimum enforcement
    - NFR57: Halt on entropy failure

    Example:
        service = VerifiableWitnessSelectionService(
            halt_checker=halt_checker,
            witness_pool=pool,
            entropy_source=entropy,
            event_store=store,
            pair_history=history,
            anomaly_detector=detector,  # Optional for FR116
        )

        # Select a witness (automatically skips excluded pairs)
        record = await service.select_witness()

        # Verify the selection
        is_valid = await service.verify_selection(record)
    """

    def __init__(
        self,
        halt_checker: HaltChecker,
        witness_pool: WitnessPoolProtocol,
        entropy_source: EntropySourceProtocol,
        event_store: EventStorePort,
        pair_history: WitnessPairHistoryProtocol,
        previous_witness_id: str | None = None,
        minimum_witnesses: int = DEFAULT_MINIMUM_WITNESSES,
        anomaly_detector: WitnessAnomalyDetectorProtocol | None = None,
    ) -> None:
        """Initialize the verifiable witness selection service.

        Args:
            halt_checker: For CT-11 halt check before operations
            witness_pool: For getting available witnesses
            entropy_source: For external entropy (FR61)
            event_store: For getting latest hash chain value (FR59)
            pair_history: For pair rotation tracking (FR60)
            previous_witness_id: ID of the previous event's witness
            minimum_witnesses: Minimum required witnesses (default 6)
            anomaly_detector: For FR116 anomaly-excluded pair checking (optional)
        """
        self._halt_checker = halt_checker
        self._witness_pool = witness_pool
        self._entropy_source = entropy_source
        self._event_store = event_store
        self._pair_history = pair_history
        self._previous_witness_id = previous_witness_id
        self._minimum_witnesses = minimum_witnesses
        self._anomaly_detector = anomaly_detector

    async def select_witness(
        self,
        high_stakes: bool = False,
    ) -> WitnessSelectionRecord:
        """Select a witness using verifiable randomness (FR59, FR61, FR116).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Get external entropy (FR61)
        3. Get hash chain state (FR59)
        4. Combine into deterministic seed
        5. Check pool size (FR117)
        6. Select witness deterministically
        7. Check pair rotation (FR60)
        8. Check anomaly exclusion (FR116)
        9. Retry if pair constraint violated or pair excluded

        Args:
            high_stakes: If True, requires 12 witnesses minimum (FR117)

        Returns:
            WitnessSelectionRecord with full audit trail for verification.

        Raises:
            SystemHaltedError: If system is halted (CT-11)
            EntropyUnavailableError: If entropy unavailable (FR61, NFR57)
            InsufficientWitnessPoolError: If pool too small (FR117)
            AllWitnessesPairExhaustedError: If all witnesses violate FR60 or FR116
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - witness selection blocked")

        # FR61: Get external entropy (NFR57: halt if unavailable)
        try:
            external_entropy = await self._entropy_source.get_entropy()
            entropy_source_id = await self._entropy_source.get_source_identifier()
        except Exception as e:
            raise EntropyUnavailableError(
                source_identifier="unknown",
                reason=str(e),
            ) from e

        # FR59: Get latest hash chain value
        latest_event = await self._event_store.get_latest_event()
        chain_hash = latest_event.content_hash if latest_event else "genesis"

        # Combine entropy sources for deterministic seed
        seed = WitnessSelectionSeed.combine(external_entropy, chain_hash)
        seed_source = f"external:{entropy_source_id}+chain:{chain_hash[:16]}"

        # Get ordered pool snapshot
        pool_snapshot = await self._get_ordered_witness_pool()

        # FR117: Check pool size
        required = (
            HIGH_STAKES_MINIMUM_WITNESSES if high_stakes else self._minimum_witnesses
        )
        if len(pool_snapshot) < required:
            raise InsufficientWitnessPoolError(
                available=len(pool_snapshot),
                minimum_required=required,
                operation_type="high-stakes" if high_stakes else "standard",
            )

        # Select witness with FR60 rotation enforcement
        selected_witness_id, attempts = await self._select_with_rotation_check(
            seed=seed.combined_seed,
            pool=pool_snapshot,
        )

        # Record the selection
        record = WitnessSelectionRecord(
            random_seed=seed.combined_seed,
            seed_source=seed_source,
            selected_witness_id=selected_witness_id,
            pool_snapshot=pool_snapshot,
            algorithm_version=SELECTION_ALGORITHM_VERSION,
            selected_at=datetime.now(timezone.utc),
        )

        # Record the pair for rotation tracking
        if self._previous_witness_id:
            pair = WitnessPair(
                witness_a_id=self._previous_witness_id,
                witness_b_id=selected_witness_id,
            )
            await self._pair_history.record_pair(pair)

        # Update previous witness for next selection
        self._previous_witness_id = selected_witness_id

        return record

    async def verify_selection(
        self,
        record: WitnessSelectionRecord,
    ) -> bool:
        """Verify that a selection record is valid (FR59).

        Re-runs the deterministic selection algorithm with the recorded
        seed and pool snapshot, verifying the result matches.

        Args:
            record: The selection record to verify.

        Returns:
            True if the selection is valid.

        Raises:
            WitnessSelectionVerificationError: If verification fails.
            ValueError: If record has empty pool.
        """
        # CT-11: HALT CHECK FIRST
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted - verification blocked")

        # Use the record's built-in verification
        if not record.verify_selection():
            # Compute what the selection should be
            computed = deterministic_select(record.random_seed, record.pool_snapshot)
            raise WitnessSelectionVerificationError(
                expected_witness=record.selected_witness_id,
                computed_witness=computed,
            )

        return True

    async def create_selection_event_payload(
        self,
        record: WitnessSelectionRecord,
    ) -> WitnessSelectionEventPayload:
        """Create an event payload for the selection record.

        Args:
            record: The selection record to create event for.

        Returns:
            WitnessSelectionEventPayload for event writing.
        """
        return WitnessSelectionEventPayload.from_seed_bytes(
            seed=record.random_seed,
            seed_source=record.seed_source,
            selected_witness_id=record.selected_witness_id,
            pool_size=len(record.pool_snapshot),
            algorithm_version=record.algorithm_version,
            selected_at=record.selected_at,
        )

    def set_previous_witness(self, witness_id: str) -> None:
        """Set the previous witness for pair rotation tracking.

        Call this when starting a new sequence of selections to
        establish the context for FR60 rotation tracking.

        Args:
            witness_id: The ID of the previous event's witness.
        """
        self._previous_witness_id = witness_id

    async def _get_ordered_witness_pool(self) -> tuple[str, ...]:
        """Get ordered list of active witness IDs.

        Returns witnesses sorted by ID for deterministic ordering.

        Returns:
            Tuple of witness IDs, sorted for determinism.
        """
        return await self._witness_pool.get_ordered_active_witnesses()

    async def _select_with_rotation_check(
        self,
        seed: bytes,
        pool: tuple[str, ...],
    ) -> tuple[str, int]:
        """Select witness with FR60 rotation and FR116 anomaly check.

        Attempts to select a witness that doesn't violate the
        pair rotation constraint (FR60) and is not excluded due to
        anomaly detection (FR116). If the primary selection violates
        either constraint, tries subsequent witnesses in a deterministic order.

        Args:
            seed: The combined selection seed
            pool: Ordered pool of witness IDs

        Returns:
            Tuple of (selected_witness_id, attempts_made)

        Raises:
            AllWitnessesPairExhaustedError: If all witnesses violate FR60 or FR116
        """
        attempts = 0
        pool_size = len(pool)

        # Try each witness in deterministic order
        for offset in range(pool_size):
            attempts += 1

            # Compute modified seed for this attempt
            if offset == 0:
                current_seed = seed
            else:
                # Deterministic modification for retry
                current_seed = hashlib.sha256(seed + offset.to_bytes(4, "big")).digest()

            # Select candidate
            candidate = deterministic_select(current_seed, pool)

            # Check FR60 rotation constraint
            if self._previous_witness_id:
                pair = WitnessPair(
                    witness_a_id=self._previous_witness_id,
                    witness_b_id=candidate,
                )
                if await self._pair_history.has_appeared_in_24h(pair):
                    continue  # Try next candidate

                # FR116: Check anomaly exclusion if detector available
                if self._anomaly_detector:
                    pair_key = pair.canonical_key()
                    if await self._anomaly_detector.is_pair_excluded(pair_key):
                        continue  # Skip excluded pair

            # Found a valid witness
            return (candidate, attempts)

        # All witnesses violate rotation or are excluded
        raise AllWitnessesPairExhaustedError(
            pool_size=pool_size,
            attempts_made=attempts,
        )

    async def is_pair_excluded_by_anomaly(self, pair_key: str) -> bool:
        """Check if a pair is excluded due to anomaly detection (FR116).

        Convenience method to check pair exclusion without full selection.

        Args:
            pair_key: Canonical pair key to check.

        Returns:
            True if pair is excluded, False if not or no detector configured.
        """
        if not self._anomaly_detector:
            return False
        return await self._anomaly_detector.is_pair_excluded(pair_key)
