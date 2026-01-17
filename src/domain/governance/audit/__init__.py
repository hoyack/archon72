"""Audit domain models for consent-based governance system.

Stories:
- consent-gov-9.1: Ledger Export
- consent-gov-9.2: Cryptographic Proof Generation
- consent-gov-9.3: Independent Verification
- consent-gov-9.4: State Transition Logging

This package contains domain models for audit and verification operations
including ledger export, cryptographic proof functionality, independent
verification results, and state transition logging.

Constitutional Requirements:
- FR56: Any participant can export complete ledger
- FR57: System can provide cryptographic proof of ledger completeness
- FR58: Any participant can independently verify ledger integrity
- FR59: System can log all state transitions with timestamp and actor
- FR60: System can prevent ledger modification (append-only enforcement)
- NFR-CONST-03: Partial export is impossible
- NFR-AUDIT-04: Transitions include triggering event reference
- NFR-AUDIT-05: Export format is machine-readable (JSON) and human-auditable
- NFR-AUDIT-06: External verification possible
- NFR-INT-02: Ledger contains no PII; publicly readable by design

Key Design Decisions:
- Export ALWAYS includes ALL events from genesis to latest
- NO partial export methods exist (by design, not oversight)
- JSON format for universal readability and tooling
- Hash chain preserved for independent verification
- Merkle proofs enable light verification
- UUIDs only for attribution (no PII)
- Verification produces detailed results with issues list
- Transition logs are append-only (no update/delete methods)
- All entity types use consistent TransitionLog structure
"""

from src.domain.governance.audit.ledger_export import (
    ExportMetadata,
    LedgerExport,
    VerificationInfo,
)
from src.domain.governance.audit.errors import (
    PartialExportError,
    PIIDetectedError,
    ExportValidationError,
)
from src.domain.governance.audit.completeness_proof import (
    CompletenessProof,
    HashChainProof,
    ProofGenerationError,
    InvalidProofError,
    IncompleteChainError,
    DEFAULT_VERIFICATION_INSTRUCTIONS,
)
from src.domain.governance.audit.verification_result import (
    VerificationStatus,
    IssueType,
    DetectedIssue,
    VerificationResult,
    VerificationFailedError,
)
from src.domain.governance.audit.transition_log import (
    EntityType,
    TransitionLog,
    TransitionQuery,
    TransitionLogError,
    TransitionLogModificationError,
    TransitionLogNotFoundError,
)

__all__ = [
    # Ledger Export
    "ExportMetadata",
    "LedgerExport",
    "VerificationInfo",
    # Export Errors
    "PartialExportError",
    "PIIDetectedError",
    "ExportValidationError",
    # Completeness Proofs
    "CompletenessProof",
    "HashChainProof",
    "ProofGenerationError",
    "InvalidProofError",
    "IncompleteChainError",
    "DEFAULT_VERIFICATION_INSTRUCTIONS",
    # Verification Results
    "VerificationStatus",
    "IssueType",
    "DetectedIssue",
    "VerificationResult",
    "VerificationFailedError",
    # Transition Logging
    "EntityType",
    "TransitionLog",
    "TransitionQuery",
    "TransitionLogError",
    "TransitionLogModificationError",
    "TransitionLogNotFoundError",
]
