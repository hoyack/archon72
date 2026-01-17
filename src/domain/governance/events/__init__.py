"""Governance events module.

This module provides the canonical event envelope structure for the
consent-based governance system.

Event Envelope Pattern (from governance-architecture.md):
- All governance events use a consistent metadata + payload structure
- Event types follow branch.noun.verb naming convention
- Branch is derived at write-time, never trusted from caller
- Schema versioning enables deterministic replay
- Hash chain ensures cryptographic integrity (story consent-gov-1-3)
"""

from src.domain.governance.events.canonical_json import (
    canonical_json,
    canonical_json_bytes,
)
from src.domain.governance.events.event_envelope import (
    EventMetadata,
    GovernanceEvent,
)
from src.domain.governance.events.event_types import (
    GOVERNANCE_EVENT_TYPES,
    GovernanceEventType,
    validate_event_type,
)
from src.domain.governance.events.hash_algorithms import (
    DEFAULT_ALGORITHM,
    GENESIS_PREV_HASH,
    SUPPORTED_ALGORITHMS,
    Blake3Hasher,
    HashAlgorithm,
    Sha256Hasher,
    compute_hash,
    extract_algorithm_from_hash,
    get_hasher,
    is_genesis_hash,
    make_genesis_hash,
    validate_hash_format,
    verify_hash,
)
from src.domain.governance.events.hash_break_detection import (
    HASH_BREAK_EVENT_TYPE,
    HashBreakDetectionResult,
    HashBreakDetector,
    HashBreakInfo,
    HashBreakType,
)
from src.domain.governance.events.hash_chain import (
    HashVerificationResult,
    add_hash_to_event,
    chain_events,
    compute_event_hash,
    compute_event_hash_with_prev,
    verify_chain_link,
    verify_event_full,
    verify_event_hash,
)
from src.domain.governance.events.schema_versions import (
    CURRENT_SCHEMA_VERSION,
    validate_schema_version,
)

__all__ = [
    # Event envelope
    "CURRENT_SCHEMA_VERSION",
    "EventMetadata",
    "GOVERNANCE_EVENT_TYPES",
    "GovernanceEvent",
    "GovernanceEventType",
    "validate_event_type",
    "validate_schema_version",
    # Hash algorithms
    "Blake3Hasher",
    "DEFAULT_ALGORITHM",
    "GENESIS_PREV_HASH",
    "HashAlgorithm",
    "Sha256Hasher",
    "SUPPORTED_ALGORITHMS",
    "compute_hash",
    "extract_algorithm_from_hash",
    "get_hasher",
    "is_genesis_hash",
    "make_genesis_hash",
    "validate_hash_format",
    "verify_hash",
    # Canonical JSON
    "canonical_json",
    "canonical_json_bytes",
    # Hash chain
    "HashVerificationResult",
    "add_hash_to_event",
    "chain_events",
    "compute_event_hash",
    "compute_event_hash_with_prev",
    "verify_chain_link",
    "verify_event_full",
    "verify_event_hash",
    # Hash break detection
    "HASH_BREAK_EVENT_TYPE",
    "HashBreakDetectionResult",
    "HashBreakDetector",
    "HashBreakInfo",
    "HashBreakType",
]
