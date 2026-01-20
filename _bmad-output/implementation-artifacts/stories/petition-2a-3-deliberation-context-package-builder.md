# Story 2A.3: Deliberation Context Package Builder

## Story Information

| Field | Value |
|-------|-------|
| **Story ID** | petition-2a-3 |
| **Epic** | Epic 2A: Core Deliberation Protocol |
| **Priority** | P0-CRITICAL |
| **Status** | done |
| **Created** | 2026-01-19 |

## User Story

**As a** system,
**I want** to build a context package for each deliberating Archon,
**So that** they have sufficient information to render judgment.

## Requirements Coverage

### Functional Requirements

| FR ID | Requirement | Priority |
|-------|-------------|----------|
| FR-11.3 | System SHALL provide deliberation context package (petition, type, co-signer count, similar petitions) to each Fate Archon | P0 |

### Non-Functional Requirements

| NFR ID | Requirement | Target |
|--------|-------------|--------|
| NFR-10.3 | Consensus determinism | 100% reproducible given same inputs |
| NFR-10.4 | Witness completeness | 100% utterances witnessed |

### Rulings Applied

| Ruling | Decision | Impact |
|--------|----------|--------|
| Ruling-3 | Similar petitions deferred to M2 | Package does NOT include similar petitions in M1 |

### Constitutional Truths

- **CT-1**: LLMs are stateless - Context package provides deterministic state
- **CT-12**: Witnessing creates accountability - Package hash enables audit trail
- **CT-14**: "Silence must be expensive. Every claim on attention terminates in a visible, witnessed fate."

## Acceptance Criteria

### AC-1: Context Package Contains Required Fields

**Given** a petition assigned for deliberation
**When** the context package is built
**Then** it contains:
- `petition_id` (UUID)
- `petition_text` (full text content)
- `petition_type` (GENERAL, CESSATION, GRIEVANCE, COLLABORATION)
- `co_signer_count` (current count, default 0)
- `submitter_id` (anonymized identifier, nullable)
- `realm` (routing realm)
- `submitted_at` (ISO8601 timestamp)
- `session_id` (deliberation session reference)
- `assigned_archons` (tuple of 3 archon IDs)
**And** the package is immutable (frozen dataclass)

### AC-2: JSON Serialization

**Given** a built context package
**When** serialized to JSON
**Then** the output uses canonical JSON (sorted keys, stable encoding)
**And** can be deserialized back to identical package
**And** all UUID fields are serialized as strings
**And** datetime fields use ISO8601 format

### AC-3: Similar Petitions NOT Included (Ruling-3)

**Given** the M1 milestone scope
**When** the context package is built
**Then** it does NOT include similar petition references
**And** a `similar_petitions` field is explicitly set to empty tuple
**And** the package includes a `ruling_3_deferred: true` flag for auditability

### AC-4: Package Hash for Integrity

**Given** a built context package
**When** the package is finalized
**Then** a SHA-256 hash of the canonical JSON is computed
**And** the hash is stored in `content_hash` field
**And** the hash can be verified by re-computing from package contents

### AC-5: Builder Service Protocol

**Given** the need for testability and dependency injection
**Then** a `ContextPackageBuilderProtocol` is defined with:
- `build_package(petition: PetitionSubmission, session: DeliberationSession) -> DeliberationContextPackage`
**And** a stub implementation is provided for testing
**And** the protocol is registered in application ports

### AC-6: Idempotent Building

**Given** the same petition and session
**When** `build_package()` is called multiple times
**Then** identical context packages are produced (deterministic)
**And** the content_hash is identical across calls

### AC-7: Schema Version

**Given** the context package
**When** created
**Then** it includes `schema_version: "1.0.0"` for D2 compliance
**And** the version enables future schema evolution

## Technical Design

### Domain Model

```python
# src/domain/models/deliberation_context_package.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

@dataclass(frozen=True, eq=True)
class DeliberationContextPackage:
    """Context package for Three Fates deliberation (Story 2A.3, FR-11.3).

    Provides deliberating Archons with all information needed to render
    judgment on a petition. Package is immutable and content-hashed for
    integrity verification.

    Constitutional Constraints:
    - CT-1: Provides deterministic state for stateless LLMs
    - CT-12: content_hash enables witnessing and audit
    - Ruling-3: similar_petitions explicitly empty in M1

    Attributes:
        petition_id: UUID of the petition being deliberated.
        petition_text: Full text content of petition.
        petition_type: Type classification (GENERAL, CESSATION, etc.).
        co_signer_count: Current number of co-signers.
        submitter_id: Anonymized submitter identifier (nullable).
        realm: Routing realm for the petition.
        submitted_at: When petition was submitted (UTC).
        session_id: UUID of the deliberation session.
        assigned_archons: Tuple of 3 assigned archon UUIDs.
        similar_petitions: Empty tuple (Ruling-3 deferred to M2).
        ruling_3_deferred: Flag indicating similar petitions deferred.
        schema_version: Package schema version for evolution.
        built_at: When package was built (UTC).
        content_hash: SHA-256 hash of canonical JSON (computed).
    """

    # Core petition data
    petition_id: UUID
    petition_text: str
    petition_type: str  # PetitionType.value
    co_signer_count: int
    submitter_id: UUID | None
    realm: str
    submitted_at: datetime

    # Session data
    session_id: UUID
    assigned_archons: tuple[UUID, UUID, UUID]

    # M2 deferred (Ruling-3)
    similar_petitions: tuple[()] = field(default=tuple())
    ruling_3_deferred: bool = field(default=True)

    # Metadata
    schema_version: Literal["1.0.0"] = field(default="1.0.0")
    built_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = field(default="")  # Computed after construction
```

### Service Protocol

```python
# src/application/ports/context_package_builder.py

from typing import Protocol
from src.domain.models.petition_submission import PetitionSubmission
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.deliberation_context_package import DeliberationContextPackage

class ContextPackageBuilderProtocol(Protocol):
    """Protocol for building deliberation context packages (Story 2A.3, FR-11.3)."""

    def build_package(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession,
    ) -> DeliberationContextPackage:
        """Build a context package for deliberation.

        Creates an immutable, content-hashed package containing all
        information needed by Fate Archons to deliberate the petition.

        Args:
            petition: The petition being deliberated.
            session: The deliberation session with assigned archons.

        Returns:
            DeliberationContextPackage with computed content_hash.

        Raises:
            ValueError: If petition or session is invalid.
        """
        ...
```

### Service Implementation

```python
# src/application/services/context_package_builder_service.py

import hashlib
import json
from datetime import datetime, timezone
from src.domain.models.petition_submission import PetitionSubmission
from src.domain.models.deliberation_session import DeliberationSession
from src.domain.models.deliberation_context_package import DeliberationContextPackage

class ContextPackageBuilderService:
    """Service for building deliberation context packages (Story 2A.3)."""

    def build_package(
        self,
        petition: PetitionSubmission,
        session: DeliberationSession,
    ) -> DeliberationContextPackage:
        """Build a context package for deliberation."""
        # Create package without hash first
        built_at = datetime.now(timezone.utc)

        package = DeliberationContextPackage(
            petition_id=petition.id,
            petition_text=petition.text,
            petition_type=petition.type.value,
            co_signer_count=petition.co_signer_count,
            submitter_id=petition.submitter_id,
            realm=petition.realm,
            submitted_at=petition.created_at,
            session_id=session.session_id,
            assigned_archons=session.assigned_archons,
            similar_petitions=tuple(),
            ruling_3_deferred=True,
            schema_version="1.0.0",
            built_at=built_at,
            content_hash="",  # Placeholder
        )

        # Compute content hash
        content_hash = self._compute_hash(package)

        # Return new package with hash set
        return DeliberationContextPackage(
            petition_id=package.petition_id,
            petition_text=package.petition_text,
            petition_type=package.petition_type,
            co_signer_count=package.co_signer_count,
            submitter_id=package.submitter_id,
            realm=package.realm,
            submitted_at=package.submitted_at,
            session_id=package.session_id,
            assigned_archons=package.assigned_archons,
            similar_petitions=package.similar_petitions,
            ruling_3_deferred=package.ruling_3_deferred,
            schema_version=package.schema_version,
            built_at=package.built_at,
            content_hash=content_hash,
        )

    def _compute_hash(self, package: DeliberationContextPackage) -> str:
        """Compute SHA-256 hash of canonical JSON."""
        # Create dict for hashing (exclude content_hash itself)
        hashable = {
            "petition_id": str(package.petition_id),
            "petition_text": package.petition_text,
            "petition_type": package.petition_type,
            "co_signer_count": package.co_signer_count,
            "submitter_id": str(package.submitter_id) if package.submitter_id else None,
            "realm": package.realm,
            "submitted_at": package.submitted_at.isoformat(),
            "session_id": str(package.session_id),
            "assigned_archons": [str(a) for a in package.assigned_archons],
            "similar_petitions": list(package.similar_petitions),
            "ruling_3_deferred": package.ruling_3_deferred,
            "schema_version": package.schema_version,
            "built_at": package.built_at.isoformat(),
        }

        # Canonical JSON (sorted keys, compact)
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))

        # SHA-256 hash
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

## Dependencies

### Upstream Dependencies (Required Before This Story)

| Story ID | Name | Status | Why Needed |
|----------|------|--------|------------|
| petition-2a-1 | Deliberation Session Domain Model | DONE | DeliberationSession with assigned_archons |
| petition-2a-2 | Archon Assignment Service | DONE | Session creation with archon assignment |
| petition-0-2 | Petition Domain Model | DONE | PetitionSubmission domain model |

### Downstream Dependencies (Blocked By This Story)

| Story ID | Name | Why Blocked |
|----------|------|-------------|
| petition-2a-4 | Deliberation Protocol Orchestrator | Needs context package for phase execution |
| petition-2a-5 | CrewAI Deliberation Adapter | Needs context package for agent invocation |

## Implementation Tasks

### Task 1: Create Domain Model
- [x] Create `src/domain/models/deliberation_context_package.py`
- [x] Define `DeliberationContextPackage` frozen dataclass
- [x] Implement `to_dict()` for JSON serialization
- [x] Implement `to_canonical_json()` for deterministic hashing
- [x] Export from `src/domain/models/__init__.py`

### Task 2: Create Service Protocol
- [x] Create `src/application/ports/context_package_builder.py`
- [x] Define `ContextPackageBuilderProtocol`
- [x] Export from `src/application/ports/__init__.py`

### Task 3: Create Service Implementation
- [x] Create `src/application/services/context_package_builder_service.py`
- [x] Implement `build_package()` method
- [x] Implement `_compute_hash()` for content integrity
- [x] Export from `src/application/services/__init__.py`

### Task 4: Create Stub Implementation
- [x] Create `src/infrastructure/stubs/context_package_builder_stub.py`
- [x] Implement in-memory builder for testing
- [x] Export from `src/infrastructure/stubs/__init__.py`

### Task 5: Write Unit Tests
- [x] Create `tests/unit/domain/models/test_deliberation_context_package.py`
- [x] Test frozen dataclass behavior
- [x] Test JSON serialization/deserialization
- [x] Test content hash computation
- [x] Test schema version presence

### Task 6: Write Service Tests
- [x] Create `tests/unit/application/services/test_context_package_builder_service.py`
- [x] Test package building from petition + session
- [x] Test idempotent building (same inputs = same hash)
- [x] Test Ruling-3 compliance (empty similar_petitions)

### Task 7: Write Integration Tests
- [x] Create `tests/integration/test_context_package_builder_integration.py`
- [x] Test with real petition and session models
- [x] Test hash verification workflow

## Definition of Done

- [x] DeliberationContextPackage domain model created
- [x] ContextPackageBuilderProtocol defined
- [x] Service implementation complete
- [x] Stub implementation for testing
- [x] Unit tests pass (>90% coverage)
- [x] Integration tests verify hash integrity
- [ ] Code review completed
- [x] FR-11.3 satisfied: Context package provided to each Archon
- [x] Ruling-3 satisfied: Similar petitions deferred to M2
- [x] NFR-10.3 satisfied: Deterministic package building

## Test Scenarios

### Scenario 1: Happy Path - Build Package
```python
# Setup
petition = create_petition(type=PetitionType.GENERAL, text="Test petition")
session = create_session(petition_id=petition.id, archons=(a1, a2, a3))
builder = ContextPackageBuilderService()

# Execute
package = builder.build_package(petition, session)

# Verify
assert package.petition_id == petition.id
assert package.petition_text == petition.text
assert package.petition_type == "GENERAL"
assert package.session_id == session.session_id
assert package.assigned_archons == session.assigned_archons
assert len(package.content_hash) == 64  # SHA-256 hex
```

### Scenario 2: Idempotent Building
```python
# Build twice with same inputs
package1 = builder.build_package(petition, session)
package2 = builder.build_package(petition, session)

# Same content produces same hash
assert package1.content_hash == package2.content_hash
```

### Scenario 3: Ruling-3 Compliance
```python
package = builder.build_package(petition, session)

# Similar petitions explicitly empty
assert package.similar_petitions == tuple()
assert package.ruling_3_deferred is True
```

### Scenario 4: JSON Serialization Round-Trip
```python
package = builder.build_package(petition, session)

# Serialize
json_str = package.to_canonical_json()

# Deserialize
restored = DeliberationContextPackage.from_json(json_str)

# Verify equality
assert restored.content_hash == package.content_hash
```

## Notes

- Package is intentionally simpler than ContextBundlePayload (ADR-2) which is for meeting deliberations
- Similar petitions feature deferred per Ruling-3 to avoid scope creep
- Content hash enables audit trail and replay verification
- Schema version enables future evolution without breaking consumers

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2026-01-19 | Claude | Initial story creation |
