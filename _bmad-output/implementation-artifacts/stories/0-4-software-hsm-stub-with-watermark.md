# Story 0.4: Software HSM Stub with Watermark

Status: review

## Story

As a **developer**,
I want a software HSM stub for local development,
So that I can sign events without production HSM while clearly marking dev signatures.

## Acceptance Criteria

### AC1: Dev Mode Signature Creation

**Given** the application is running in dev mode (DEV_MODE=true)
**When** I request a signature from the HSM service
**Then** the signature is created using software cryptography
**And** the signed content includes `[DEV MODE]` prefix INSIDE the signature (RT-1 pattern)

### AC2: Signature Metadata Contains Mode

**Given** a dev mode signature
**When** I examine the signature metadata
**Then** it contains `mode: "development"`
**And** the watermark cannot be stripped without invalidating the signature

### AC3: Production Mode Fails Without HSM

**Given** production mode (DEV_MODE=false)
**When** I request a signature without HSM configured
**Then** the system fails with clear error "Production HSM not configured"
**And** no signature is produced

### AC4: Key Generation with Warning

**Given** the HSM stub
**When** I generate a key pair
**Then** the keys are stored in local file (not secure, dev only)
**And** a warning is logged: "Using software HSM - NOT FOR PRODUCTION"

## Tasks / Subtasks

- [x] Task 1: Create HSM protocol port in application layer (AC: 1, 2, 3)
  - [x] 1.1 Create `src/application/ports/hsm.py` with `HSMProtocol`
  - [x] 1.2 Define `sign()`, `verify()`, `generate_key_pair()`, `get_mode()` methods
  - [x] 1.3 Define `HSMMode` enum (DEVELOPMENT, PRODUCTION)
  - [x] 1.4 Define `SignatureResult` model with content, signature, mode, key_id

- [x] Task 2: Create SignableContent domain model (AC: 1, 2)
  - [x] 2.1 Create `src/domain/models/signable.py` with `SignableContent` class
  - [x] 2.2 Implement `to_bytes()` method with mode prefix INSIDE content
  - [x] 2.3 Pattern: `mode_prefix = b"[DEV MODE]" if is_dev() else b"[PROD]"`
  - [x] 2.4 Ensure mode cannot be stripped without invalidating signature

- [x] Task 3: Create software HSM stub adapter (AC: 1, 2, 4)
  - [x] 3.1 Create `src/infrastructure/adapters/security/__init__.py`
  - [x] 3.2 Create `src/infrastructure/adapters/security/hsm_dev.py`
  - [x] 3.3 Implement `DevHSM` class implementing `HSMProtocol`
  - [x] 3.4 Use `cryptography` library for Ed25519 or ECDSA signatures
  - [x] 3.5 Store keys in local file (`~/.archon72/dev_keys.json`)
  - [x] 3.6 Log warning on initialization: "Using software HSM - NOT FOR PRODUCTION"

- [x] Task 4: Create production HSM placeholder (AC: 3)
  - [x] 4.1 Create `src/infrastructure/adapters/security/hsm_cloud.py`
  - [x] 4.2 Implement `CloudHSM` class with `NotConfiguredError` for all methods
  - [x] 4.3 Error message: "Production HSM not configured"

- [x] Task 5: Create HSM factory with mode detection (AC: 1, 3)
  - [x] 5.1 Create `src/infrastructure/adapters/security/hsm_factory.py`
  - [x] 5.2 Implement `get_hsm()` factory function
  - [x] 5.3 Check `DEV_MODE` environment variable
  - [x] 5.4 Return `DevHSM` if DEV_MODE=true, else `CloudHSM`

- [x] Task 6: Add domain exceptions (AC: 3)
  - [x] 6.1 Create `src/domain/errors/hsm.py`
  - [x] 6.2 Add `HSMError(ConclaveError)` base exception
  - [x] 6.3 Add `HSMNotConfiguredError(HSMError)` for production mode without HSM
  - [x] 6.4 Add `HSMModeViolationError(HSMError)` for mode mismatches (RT-1)

- [x] Task 7: Write unit tests (AC: 1, 2, 3, 4)
  - [x] 7.1 Create `tests/unit/infrastructure/test_hsm_dev.py`
  - [x] 7.2 Test: dev mode signature includes `[DEV MODE]` prefix
  - [x] 7.3 Test: signature metadata contains `mode: "development"`
  - [x] 7.4 Test: key generation logs warning
  - [x] 7.5 Test: CloudHSM raises `HSMNotConfiguredError`
  - [x] 7.6 Test: factory returns correct HSM based on DEV_MODE

- [x] Task 8: Write integration tests (AC: 1, 2)
  - [x] 8.1 Create `tests/integration/test_hsm_integration.py`
  - [x] 8.2 Test: sign and verify round-trip with DevHSM
  - [x] 8.3 Test: watermark cannot be stripped (verification fails)
  - [x] 8.4 Test: key persistence across HSM instances

## Dev Notes

### Critical Architecture Requirements (RT-1 Pattern)

**WATERMARK MUST BE INSIDE THE SIGNATURE, NOT METADATA!**

```python
# WRONG - vulnerable to stripping
sig = Signature(
    value=hsm.sign(content),
    metadata={"mode": "DEV"}  # Can be stripped!
)

# CORRECT - watermark inside signable content
class SignableContent:
    def to_bytes(self) -> bytes:
        mode_prefix = b"[DEV MODE]" if is_dev() else b"[PROD]"
        return mode_prefix + self._content  # Mode is INSIDE signature
```

### HSM Protocol Definition (from Architecture)

```python
# src/application/ports/hsm.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

class HSMMode(Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class HSMProtocol(ABC):
    @abstractmethod
    async def sign(self, content: bytes) -> bytes:
        """Sign content and return signature."""
        ...

    @abstractmethod
    async def verify(self, content: bytes, signature: bytes) -> bool:
        """Verify signature against content."""
        ...

    @abstractmethod
    async def generate_key_pair(self) -> str:
        """Generate new key pair, return key_id."""
        ...

    @abstractmethod
    async def get_mode(self) -> HSMMode:
        """Return current HSM mode."""
        ...

    @abstractmethod
    async def get_current_key_id(self) -> str:
        """Return current signing key ID."""
        ...
```

### File Structure After Completion

```
src/
├── domain/
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── base.py          # ConclaveError (may need creation)
│   │   └── hsm.py           # NEW: HSMError, HSMNotConfiguredError
│   └── models/
│       ├── __init__.py
│       └── signable.py      # NEW: SignableContent
├── application/
│   └── ports/
│       ├── __init__.py
│       └── hsm.py           # NEW: HSMProtocol
└── infrastructure/
    └── adapters/
        └── security/
            ├── __init__.py  # NEW
            ├── hsm_dev.py   # NEW: DevHSM
            ├── hsm_cloud.py # NEW: CloudHSM placeholder
            └── hsm_factory.py # NEW: get_hsm() factory
```

### Cryptography Library Usage

```python
# Use Ed25519 for fast, secure signatures
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Key generation
private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# Signing
signature = private_key.sign(content)

# Verification
public_key.verify(signature, content)  # Raises InvalidSignature if fails
```

### Environment Variable Pattern

```python
import os

def is_dev_mode() -> bool:
    """Check if running in development mode."""
    return os.getenv("DEV_MODE", "false").lower() == "true"
```

### Logging Pattern (structlog)

```python
import structlog

log = structlog.get_logger()

# On DevHSM initialization
log.warning(
    "hsm_dev_mode_active",
    message="Using software HSM - NOT FOR PRODUCTION",
    key_storage="~/.archon72/dev_keys.json"
)
```

### Previous Story Learnings (Story 0.3)

From Story 0.3 completion:
- Use Pydantic models for all responses (not raw dicts)
- Add `/v1` prefix to API routes (if exposing HSM endpoints later)
- Integration test naming: `test_{feature}_integration.py`
- Create `.dockerignore` patterns for security files

### Import Boundary Rules

- `domain/` imports NOTHING from other layers
- `application/` imports from `domain/` only
- `infrastructure/` implements ports from `application/`
- `SignableContent` in domain - no infrastructure imports
- `HSMProtocol` in application - imports only domain types
- `DevHSM`/`CloudHSM` in infrastructure - implements protocol

### Testing Notes

**Unit Tests (no real crypto needed for some tests):**
```python
@pytest.mark.asyncio
async def test_dev_hsm_mode() -> None:
    hsm = DevHSM()
    mode = await hsm.get_mode()
    assert mode == HSMMode.DEVELOPMENT
```

**Key Storage Location:**
- Dev keys stored in `~/.archon72/dev_keys.json`
- Create directory if not exists
- Warn user about insecure storage

### Security Considerations

1. **Mode prefix is cryptographically bound** - changing it invalidates signature
2. **Dev keys are NOT secure** - clearly document this
3. **Production mode MUST fail without real HSM** - no fallback to dev
4. **RT-1 Pattern** - verify HSM mode matches environment at runtime

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-004]
- [Source: _bmad-output/planning-artifacts/architecture.md#RT-1]
- [Source: _bmad-output/planning-artifacts/epics.md#Story 0.4]
- [Source: _bmad-output/project-context.md#Dev Mode Watermark Pattern]
- [Source: _bmad-output/project-context.md#Security Rules]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 71 tests pass (29 new unit + 10 new integration + 32 existing)
- Poetry virtualenv with Python 3.12.12
- Ed25519 signatures for cryptographic operations

### Completion Notes List

1. Created `HSMProtocol` abstract interface in `src/application/ports/hsm.py` with async methods for sign, verify, generate_key_pair, get_mode, get_current_key_id
2. Created `HSMMode` enum (DEVELOPMENT, PRODUCTION) and `SignatureResult` dataclass
3. Created `SignableContent` domain model with RT-1 pattern (watermark INSIDE signed content)
4. Implemented `DevHSM` class using Ed25519 from cryptography library
5. DevHSM stores keys in `~/.archon72/dev_keys.json` with persistence across instances
6. DevHSM logs warning on initialization: "Using software HSM - NOT FOR PRODUCTION"
7. Created `CloudHSM` placeholder that raises `HSMNotConfiguredError` for all operations
8. Created `get_hsm()` factory function that checks `DEV_MODE` environment variable
9. Added domain exceptions: `HSMError`, `HSMNotConfiguredError`, `HSMModeViolationError`, `HSMKeyNotFoundError`
10. Created 29 unit tests covering all acceptance criteria
11. Created 10 integration tests for end-to-end signing/verification
12. All tests pass with no regressions
13. Linting issues fixed (import sorting, type annotation style)

### File List

_Files created:_
- `src/application/ports/__init__.py`
- `src/application/ports/hsm.py`
- `src/domain/models/__init__.py`
- `src/domain/models/signable.py`
- `src/domain/errors/__init__.py`
- `src/domain/errors/hsm.py`
- `src/infrastructure/adapters/__init__.py`
- `src/infrastructure/adapters/security/__init__.py`
- `src/infrastructure/adapters/security/hsm_dev.py`
- `src/infrastructure/adapters/security/hsm_cloud.py`
- `src/infrastructure/adapters/security/hsm_factory.py`
- `tests/unit/infrastructure/__init__.py`
- `tests/unit/infrastructure/test_hsm_dev.py`
- `tests/unit/domain/__init__.py`
- `tests/integration/test_hsm_integration.py`

_Files modified:_
- `src/application/__init__.py` (added HSM exports)
- `src/domain/__init__.py` (added SignableContent and HSM error exports)
- `src/infrastructure/__init__.py` (added HSM adapter exports)
