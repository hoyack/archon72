"""Port for co-sign count verification (Story 5.8, AC5).

This module defines the protocol for verifying consistency between the
co_signer_count counter column and the actual COUNT(*) of co_signs.

Constitutional Constraints:
- NFR-2.2: 100k+ co-signers supported - counter enables O(1) reads
- AC5: Periodic verification catches any drift
- CT-11: Silent failure destroys legitimacy - discrepancy must be visible
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CountVerificationResult:
    """Result of a count consistency verification.

    Attributes:
        petition_id: The petition that was verified.
        counter_value: Value from petition_submissions.co_signer_count.
        actual_count: COUNT(*) from co_signs table.
        is_consistent: True if counter_value == actual_count.
        discrepancy: Difference (counter_value - actual_count), 0 if consistent.
    """

    petition_id: UUID
    counter_value: int
    actual_count: int
    is_consistent: bool
    discrepancy: int


class CoSignCountVerificationProtocol(Protocol):
    """Protocol for co-sign count consistency verification.

    This service compares the pre-computed co_signer_count column against
    SELECT COUNT(*) FROM co_signs to detect any drift. Drift should not
    occur under normal operation, but verification provides accountability.

    Use Cases:
    - Periodic batch verification (e.g., nightly job)
    - On-demand verification for specific petitions
    - Post-incident verification after recovery
    """

    async def verify_count(self, petition_id: UUID) -> CountVerificationResult:
        """Verify count consistency for a single petition.

        Compares:
        - Counter: SELECT co_signer_count FROM petition_submissions
        - Actual: SELECT COUNT(*) FROM co_signs WHERE petition_id = ?

        On discrepancy:
        - Logs WARNING with structured details (CT-11)
        - Returns result with is_consistent=False
        - Does NOT auto-correct (requires human review)

        Args:
            petition_id: The petition to verify.

        Returns:
            CountVerificationResult with comparison details.
        """
        ...

    async def verify_batch(
        self,
        petition_ids: list[UUID],
    ) -> list[CountVerificationResult]:
        """Verify count consistency for multiple petitions.

        Useful for periodic batch verification jobs.

        Args:
            petition_ids: List of petition IDs to verify.

        Returns:
            List of CountVerificationResult, one per petition.
        """
        ...
