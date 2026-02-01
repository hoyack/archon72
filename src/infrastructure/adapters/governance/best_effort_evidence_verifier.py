"""Best-effort evidence verifier — MVP adapter for evidence integrity.

Sprint: Evidence Integrity Verification (Best-Effort)

This adapter performs structural verification where possible:
- Local file existence check
- Checksum verification (SHA-256) when checksum is embedded in ref
- Everything else → UNVERIFIABLE

It never blocks the pipeline. If a check fails due to infrastructure
(network, permissions), the result is UNVERIFIABLE, not VERIFIED_FAILED.
VERIFIED_FAILED is reserved for definitive structural facts:
checksum mismatch, confirmed-missing file.

Best-effort policy: UNVERIFIABLE evidence counts.
Strict policy (future): flip one flag and UNVERIFIABLE stops counting.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from src.application.ports.governance.evidence_verifier_port import (
    AcceptanceTestVerificationResult,
    ArtifactVerificationResult,
    EvidenceVerifierPort,
)
from src.domain.models.aggregation import VerificationStatus

# Pattern: "path/to/file:sha256=abc123..." or "path/to/file#sha256=abc123..."
_CHECKSUM_PATTERN = re.compile(r"^(.+?)(?:[:#]sha256=([a-fA-F0-9]{64}))$")

# Patterns that indicate non-local refs (skip file existence check)
_REMOTE_PREFIXES = ("http://", "https://", "s3://", "gs://", "tar:")


class BestEffortEvidenceVerifier:
    """MVP evidence verifier with best-effort structural checks.

    Implements EvidenceVerifierPort.

    Verification logic:
    - Local file paths: check existence, verify checksum if provided
    - Remote URLs: UNVERIFIABLE (no HTTP client in MVP)
    - TAR refs: UNVERIFIABLE (structural pointer, no content check)
    - Acceptance tests: check for run_id/attestation in notes
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """Initialize verifier.

        Args:
            base_dir: Base directory for resolving relative file paths.
                If None, paths are resolved relative to cwd.
        """
        self._base_dir = base_dir or Path.cwd()

    def verify_artifact_ref(self, artifact_ref: str) -> ArtifactVerificationResult:
        """Verify a single artifact reference.

        Decision tree:
        1. Remote URL → UNVERIFIABLE (no HTTP in MVP)
        2. Has checksum → check file exists + verify hash
        3. Local path → check file exists
        4. Anything else → UNVERIFIABLE
        """
        # Remote refs: can't verify in MVP
        if any(artifact_ref.startswith(p) for p in _REMOTE_PREFIXES):
            return ArtifactVerificationResult(
                artifact_ref=artifact_ref,
                status=VerificationStatus.UNVERIFIABLE,
                reason="Remote reference; verification not available in MVP",
            )

        # Check for embedded checksum
        match = _CHECKSUM_PATTERN.match(artifact_ref)
        if match:
            file_path_str, expected_checksum = match.group(1), match.group(2)
            return self._verify_with_checksum(
                artifact_ref, file_path_str, expected_checksum
            )

        # Plain local path: check existence only
        return self._verify_file_exists(artifact_ref, artifact_ref)

    def verify_acceptance_test(
        self,
        test: str,
        passed: bool,
        notes: str,
    ) -> AcceptanceTestVerificationResult:
        """Verify a single acceptance test result.

        MVP checks:
        - If notes contain run_id or attestation marker → UNVERIFIABLE
          (we can note its presence but can't verify the CI system in MVP)
        - If no linkage metadata at all → UNVERIFIABLE
        """
        has_run_id = bool(re.search(r"run_id[=:]\s*\S+", notes))
        has_attestation = "attestation:" in notes or "signature:" in notes

        if has_run_id or has_attestation:
            return AcceptanceTestVerificationResult(
                test=test,
                status=VerificationStatus.UNVERIFIABLE,
                reason="Linkage metadata present but CI/signature verification not available in MVP",
            )

        return AcceptanceTestVerificationResult(
            test=test,
            status=VerificationStatus.UNVERIFIABLE,
            reason="No CI run_id or attestation metadata; cannot verify",
        )

    def _verify_file_exists(
        self, artifact_ref: str, file_path_str: str
    ) -> ArtifactVerificationResult:
        """Check if a local file exists."""
        try:
            resolved = self._resolve_path(file_path_str)
            if resolved.exists():
                return ArtifactVerificationResult(
                    artifact_ref=artifact_ref,
                    status=VerificationStatus.VERIFIED_OK,
                    reason=f"File exists: {resolved}",
                )
            return ArtifactVerificationResult(
                artifact_ref=artifact_ref,
                status=VerificationStatus.VERIFIED_FAILED,
                reason=f"File not found: {resolved}",
            )
        except (OSError, ValueError) as exc:
            return ArtifactVerificationResult(
                artifact_ref=artifact_ref,
                status=VerificationStatus.UNVERIFIABLE,
                reason=f"Cannot check path: {exc}",
            )

    def _verify_with_checksum(
        self,
        artifact_ref: str,
        file_path_str: str,
        expected_checksum: str,
    ) -> ArtifactVerificationResult:
        """Verify file existence + SHA-256 checksum."""
        try:
            resolved = self._resolve_path(file_path_str)
            if not resolved.exists():
                return ArtifactVerificationResult(
                    artifact_ref=artifact_ref,
                    status=VerificationStatus.VERIFIED_FAILED,
                    reason=f"File not found: {resolved}",
                )

            actual_checksum = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual_checksum == expected_checksum.lower():
                return ArtifactVerificationResult(
                    artifact_ref=artifact_ref,
                    status=VerificationStatus.VERIFIED_OK,
                    reason=f"Checksum verified: {actual_checksum[:16]}...",
                )
            return ArtifactVerificationResult(
                artifact_ref=artifact_ref,
                status=VerificationStatus.VERIFIED_FAILED,
                reason=(
                    f"Checksum mismatch: expected {expected_checksum[:16]}..., "
                    f"got {actual_checksum[:16]}..."
                ),
            )
        except (OSError, ValueError) as exc:
            return ArtifactVerificationResult(
                artifact_ref=artifact_ref,
                status=VerificationStatus.UNVERIFIABLE,
                reason=f"Cannot read file for checksum: {exc}",
            )

    def _resolve_path(self, file_path_str: str) -> Path:
        """Resolve a file path relative to base_dir."""
        p = Path(file_path_str)
        if p.is_absolute():
            return p
        return self._base_dir / p


# Ensure protocol compliance
_: EvidenceVerifierPort = BestEffortEvidenceVerifier()
