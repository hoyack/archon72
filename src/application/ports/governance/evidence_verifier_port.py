"""Evidence Verifier Port — hexagonal seam for evidence integrity checks.

Sprint: Evidence Integrity Verification (Best-Effort)

This port defines the interface for verifying evidence integrity
without introducing quality judgment. Verification is structural:

- Does this file exist?
- Does this checksum match?
- Is this attestation signature valid?

The port allows swapping verification strategies:
- Best-effort (MVP): verify when possible, UNVERIFIABLE otherwise
- Strict (future): UNVERIFIABLE does not count as evidence

Constitutional Constraints:
- Verification is structural, not qualitative
- "Can't verify" is uncertainty; "failed verification" is a fact
- No evidence item is silently discarded — status is always recorded
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.domain.models.aggregation import VerificationStatus


@dataclass(frozen=True)
class ArtifactVerificationResult:
    """Result of verifying a single artifact reference.

    Attributes:
        artifact_ref: The artifact reference that was checked.
        status: Verification outcome.
        reason: Human-readable explanation of the outcome.
    """

    artifact_ref: str
    status: VerificationStatus
    reason: str = ""


@dataclass(frozen=True)
class AcceptanceTestVerificationResult:
    """Result of verifying a single acceptance test result.

    Attributes:
        test: The test description that was checked.
        status: Verification outcome.
        reason: Human-readable explanation.
    """

    test: str
    status: VerificationStatus
    reason: str = ""


@runtime_checkable
class EvidenceVerifierPort(Protocol):
    """Port for evidence integrity verification.

    Implementations check evidence items and return per-item
    verification status. The aggregation service uses these
    results to set RequirementEvidence.verification_status.
    """

    def verify_artifact_ref(self, artifact_ref: str) -> ArtifactVerificationResult:
        """Verify a single artifact reference.

        Checks may include:
        - File existence (for local paths)
        - Checksum validation (if checksum embedded in ref)
        - URL reachability (best-effort)

        Args:
            artifact_ref: The artifact reference to verify.

        Returns:
            ArtifactVerificationResult with status and reason.
        """
        ...

    def verify_acceptance_test(
        self,
        test: str,
        passed: bool,
        notes: str,
    ) -> AcceptanceTestVerificationResult:
        """Verify a single acceptance test result.

        Checks may include:
        - CI run ID existence (if extractable from notes)
        - Attestation signature validity
        - Transcript hash verification

        Args:
            test: Test description.
            passed: Whether the test claims to have passed.
            notes: Additional notes (may contain run_id, signature, etc.).

        Returns:
            AcceptanceTestVerificationResult with status and reason.
        """
        ...
