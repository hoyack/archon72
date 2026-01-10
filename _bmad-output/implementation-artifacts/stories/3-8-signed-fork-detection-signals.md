# Story 3.8: Signed Fork Detection Signals (FR84-FR85)

Status: done

## Story

As an **external observer**,
I want fork detection signals to be signed,
so that I can verify the detection is authentic.

## Acceptance Criteria

1. **AC1: Fork Detection Signal Signing**
   - **Given** a fork is detected
   - **When** the detection signal is created
   - **Then** it is signed by the detecting service's key
   - **And** the signature can be verified by observers

2. **AC2: Invalid Signal Rejection**
   - **Given** an unsigned or invalid fork detection signal
   - **When** it is received
   - **Then** it is rejected
   - **And** the rejection is logged as potential attack

3. **AC3: Fork Signal Rate Limiting (FR85)**
   - **Given** fork signal rate limiting is enabled
   - **When** more than 3 fork signals per hour from the same source
   - **Then** additional signals are rate-limited
   - **And** a `ForkSignalRateLimitEvent` is created

## Tasks / Subtasks

- [x] Task 1: Add `signable_content()` to ForkDetectedPayload (AC: #1)
  - [x] 1.1: Add `signable_content() -> bytes` method to `src/domain/events/fork_detected.py`
  - [x] 1.2: Include all payload fields in deterministic order (per existing patterns)
  - [x] 1.3: Update unit tests in `tests/unit/domain/test_fork_detected_event.py`

- [x] Task 2: Create SignedForkSignal domain model (AC: #1, #2)
  - [x] 2.1: Create `src/domain/models/signed_fork_signal.py`
  - [x] 2.2: Define `SignedForkSignal` dataclass with:
    - `fork_payload: ForkDetectedPayload` - The fork detection details
    - `signature: str` - Base64-encoded signature
    - `signing_key_id: str` - Key ID used for signing
    - `sig_alg_version: int` - Signature algorithm version
  - [x] 2.3: Add `get_signable_content() -> bytes` method for validation
  - [x] 2.4: Export from `src/domain/models/__init__.py`
  - [x] 2.5: Write unit tests in `tests/unit/domain/test_signed_fork_signal.py`

- [x] Task 3: Create fork signal errors (AC: #2)
  - [x] 3.1: Create `src/domain/errors/fork_signal.py`
  - [x] 3.2: Define `UnsignedForkSignalError` for signals without signatures
  - [x] 3.3: Define `InvalidForkSignatureError` for failed verification
  - [x] 3.4: Define `ForkSignalRateLimitExceededError` for rate limiting (FR85)
  - [x] 3.5: Export from `src/domain/errors/__init__.py`
  - [x] 3.6: Write unit tests in `tests/unit/domain/test_fork_signal_errors.py`

- [x] Task 4: Create ForkSignalRateLimitEvent payload (AC: #3)
  - [x] 4.1: Create `src/domain/events/fork_signal_rate_limit.py`
  - [x] 4.2: Define `FORK_SIGNAL_RATE_LIMIT_EVENT_TYPE = "fork.signal_rate_limit"`
  - [x] 4.3: Define `ForkSignalRateLimitPayload` dataclass with:
    - `source_service_id: str` - Service that exceeded limit
    - `signal_count: int` - Number of signals in window
    - `window_start: datetime` - Start of rate limit window
    - `window_hours: int` - Window duration (default 1)
    - `rate_limited_at: datetime` - When rate limit was applied
  - [x] 4.4: Implement `signable_content() -> bytes` for witnessing
  - [x] 4.5: Export from `src/domain/events/__init__.py`
  - [x] 4.6: Write unit tests in `tests/unit/domain/test_fork_signal_rate_limit_event.py`

- [x] Task 5: Create ForkSignalRateLimiterPort (AC: #3)
  - [x] 5.1: Create `src/application/ports/fork_signal_rate_limiter.py`
  - [x] 5.2: Define abstract `ForkSignalRateLimiterPort` with:
    - `async def check_rate_limit(source_id: str) -> bool` - Returns True if allowed
    - `async def record_signal(source_id: str) -> None` - Record a signal
    - `async def get_signal_count(source_id: str, window_hours: int) -> int`
  - [x] 5.3: Add FR85 docstrings with rate limit thresholds (3/hour)
  - [x] 5.4: Export from `src/application/ports/__init__.py`
  - [x] 5.5: Write unit tests in `tests/unit/application/test_fork_signal_rate_limiter_port.py`

- [x] Task 6: Create ForkSignalRateLimiterStub (AC: #3)
  - [x] 6.1: Create `src/infrastructure/stubs/fork_signal_rate_limiter_stub.py`
  - [x] 6.2: Implement with configurable:
    - `_signal_counts: dict[str, list[datetime]]` - Per-source signal timestamps
    - `_rate_limit_threshold: int` - Default 3
    - `_window_hours: int` - Default 1
  - [x] 6.3: Add methods to simulate rate limiting scenarios
  - [x] 6.4: Export from `src/infrastructure/stubs/__init__.py`
  - [x] 6.5: Write unit tests in `tests/unit/infrastructure/test_fork_signal_rate_limiter_stub.py`

- [x] Task 7: Extend ForkMonitoringService with signing (AC: #1, #2, #3)
  - [x] 7.1: Update `src/application/services/fork_monitoring_service.py`
  - [x] 7.2: Add `SigningServiceProtocol` dependency injection
  - [x] 7.3: Add `ForkSignalRateLimiterPort` dependency injection
  - [x] 7.4: Implement `create_signed_fork_signal(payload: ForkDetectedPayload) -> SignedForkSignal`
  - [x] 7.5: Implement `validate_fork_signal(signal: SignedForkSignal) -> bool`
  - [x] 7.6: Implement `handle_fork_with_rate_limit(payload: ForkDetectedPayload) -> ForkHandleResult`
  - [x] 7.7: Write unit tests in `tests/unit/application/test_fork_monitoring_service.py`

- [x] Task 8: Integration tests (AC: #1, #2, #3)
  - [x] 8.1: Create `tests/integration/test_signed_fork_signal_integration.py`
  - [x] 8.2: Test: Fork detection creates signed signal with valid signature
  - [x] 8.3: Test: Signed signal can be verified by observer
  - [x] 8.4: Test: Invalid signature is rejected
  - [x] 8.5: Test: Rate limit triggers after 3 signals/hour
  - [x] 8.6: Test: Different sources tracked independently
  - [x] 8.7: Test: Rate limit resets after window expires
  - [x] 8.8: Test: Constitutional compliance (FR84, FR85, CT-12)

## Dev Notes

### Constitutional Requirements

**FR84 (Signed Fork Detection Signals):**
- Fork detection signals MUST be signed by the detecting service
- Signatures enable observers to verify authenticity
- Prevents fabricated fork detection attacks

**FR85 (Fork Signal Rate Limiting):**
- More than 3 fork signals per hour from same source triggers rate limiting
- Rate limiting prevents denial-of-service via fake fork spam
- Rate-limited signals create a `ForkSignalRateLimitEvent`

**Constitutional Truths to Honor:**
- **CT-11 (Silent failure destroys legitimacy):** Invalid signatures MUST be logged, not ignored
- **CT-12 (Witnessing creates accountability):** Fork signals are signed for verifiability
- **CT-13 (Integrity outranks availability):** Reject unsigned/invalid signals, don't accept "maybe valid"

**Red Team Scenario (RT-2):**
- Attacker could spam fake fork signals to trigger unnecessary halts
- Rate limiting (FR85) mitigates this attack vector
- Signing (FR84) ensures only legitimate services can create signals

### Architecture Compliance

**Hexagonal Architecture:**
- `src/domain/models/signed_fork_signal.py` - Domain model (pure domain)
- `src/domain/events/fork_signal_rate_limit.py` - Event payload (pure domain)
- `src/domain/errors/fork_signal.py` - Domain errors (pure domain)
- `src/application/ports/fork_signal_rate_limiter.py` - Abstract port
- `src/application/services/fork_monitoring_service.py` - Service extension
- `src/infrastructure/stubs/fork_signal_rate_limiter_stub.py` - Test stub

**Import Rules:**
- Domain layer: NO infrastructure imports
- Application layer: Import from domain only
- Infrastructure: Implements application ports

**Existing Infrastructure to Use:**
- `SigningService` - For cryptographic signing (FP-5 pattern)
- `ForkDetectedPayload` - From Story 3.1 (already exists)
- `ForkMonitoringService` - From Story 3.1 (extend with signing)
- `ConstitutionalCrisisPayload` - For halt trigger (Story 3.2)
- `EventWriterService` - For creating witnessed events (Story 1.6)

### Technical Implementation Notes

**SignedForkSignal Pattern:**
```python
from dataclasses import dataclass
from src.domain.events.fork_detected import ForkDetectedPayload

@dataclass(frozen=True)
class SignedForkSignal:
    """Signed fork detection signal (FR84).

    Contains a fork detection payload with cryptographic signature
    for observer verification.

    Constitutional Constraints:
    - FR84: Fork signals must be signed
    - CT-12: Witnessing creates accountability
    """

    fork_payload: ForkDetectedPayload
    signature: str  # Base64-encoded
    signing_key_id: str
    sig_alg_version: int

    def get_signable_content(self) -> bytes:
        """Get the content that was signed."""
        return self.fork_payload.signable_content()
```

**ForkDetectedPayload.signable_content() Pattern:**
```python
def signable_content(self) -> bytes:
    """Return canonical bytes for signing (FR84 support).

    Creates deterministic byte representation for cryptographic
    signing and verification.
    """
    # Sort conflicting event IDs for deterministic output
    sorted_event_ids = sorted(str(uid) for uid in self.conflicting_event_ids)
    content = (
        f"fork_detected:{self.prev_hash}"
        f":conflicting_events:{','.join(sorted_event_ids)}"
        f":content_hashes:{','.join(self.content_hashes)}"
        f":detected:{self.detection_timestamp.isoformat()}"
        f":service:{self.detecting_service_id}"
    )
    return content.encode("utf-8")
```

**Rate Limiting Pattern:**
```python
class ForkSignalRateLimiterPort(Protocol):
    """Port for fork signal rate limiting (FR85).

    Rate limit: 3 fork signals per hour per source.
    Prevents denial-of-service via fake fork spam.
    """

    # FR85: 3 signals per hour threshold
    RATE_LIMIT_THRESHOLD: int = 3
    RATE_LIMIT_WINDOW_HOURS: int = 1

    async def check_rate_limit(self, source_id: str) -> bool:
        """Check if source is within rate limit.

        Returns:
            True if signal is allowed, False if rate-limited.
        """
        ...

    async def record_signal(self, source_id: str) -> None:
        """Record a fork signal from source."""
        ...
```

**Service Extension Pattern:**
```python
# In ForkMonitoringService
async def handle_fork_detected(
    self,
    payload: ForkDetectedPayload,
) -> None:
    """Handle detected fork with signing and rate limiting (FR84-FR85).

    Extended from Story 3.1 to add:
    - Cryptographic signing (FR84)
    - Rate limiting (FR85)
    """
    # Check rate limit first (FR85)
    if not await self._rate_limiter.check_rate_limit(payload.detecting_service_id):
        await self._handle_rate_limit_exceeded(payload)
        return

    # Record this signal
    await self._rate_limiter.record_signal(payload.detecting_service_id)

    # Create signed signal (FR84)
    signed_signal = await self._create_signed_fork_signal(payload)

    # Log the signed detection
    self._log.warning(
        "fork_detected_signed",
        prev_hash=payload.prev_hash,
        conflicting_count=len(payload.conflicting_event_ids),
        signature_key=signed_signal.signing_key_id,
    )

    # Proceed with halt trigger (Story 3.2)
    await self._trigger_halt(payload)
```

### Library/Framework Requirements

**Required Libraries (already in project):**
- `dataclasses` - Immutable data structures
- `datetime` with `timezone.utc` - Timestamps
- `structlog` - Structured logging
- `pytest-asyncio` - Async testing

**Patterns to Follow:**
- Use `@dataclass(frozen=True)` for domain models
- Use `Optional[T]` not `T | None` (per project-context.md)
- Use `timezone.utc` for all timestamps
- Log all rate limit events with structlog
- Include signature verification failures in security logs

### File Structure

```
src/
├── domain/
│   ├── errors/
│   │   ├── fork_signal.py              # NEW: FR84-FR85 errors
│   │   └── __init__.py                 # UPDATE: export new errors
│   ├── events/
│   │   ├── fork_detected.py            # UPDATE: add signable_content()
│   │   ├── fork_signal_rate_limit.py   # NEW: Rate limit event
│   │   └── __init__.py                 # UPDATE: export new event
│   └── models/
│       ├── signed_fork_signal.py       # NEW: Signed signal model
│       └── __init__.py                 # UPDATE: export new model
├── application/
│   ├── ports/
│   │   ├── fork_signal_rate_limiter.py # NEW: Rate limiter port
│   │   └── __init__.py                 # UPDATE: export new port
│   └── services/
│       └── fork_monitoring_service.py  # UPDATE: add signing + rate limiting
└── infrastructure/
    └── stubs/
        ├── fork_signal_rate_limiter_stub.py  # NEW: Test stub
        └── __init__.py                 # UPDATE: export stub

tests/
├── unit/
│   ├── domain/
│   │   ├── test_fork_detected_event.py        # UPDATE: signable_content tests
│   │   ├── test_signed_fork_signal.py         # NEW
│   │   ├── test_fork_signal_errors.py         # NEW
│   │   └── test_fork_signal_rate_limit_event.py  # NEW
│   ├── application/
│   │   ├── test_fork_signal_rate_limiter_port.py  # NEW
│   │   └── test_fork_monitoring_service.py    # UPDATE: signing tests
│   └── infrastructure/
│       └── test_fork_signal_rate_limiter_stub.py  # NEW
└── integration/
    └── test_signed_fork_signal_integration.py  # NEW
```

### Testing Standards

**Unit Tests:**
- Test `ForkDetectedPayload.signable_content()` returns deterministic bytes
- Test `SignedForkSignal` can be created with valid signature
- Test signature verification succeeds with valid signature
- Test signature verification fails with tampered content
- Test rate limiter allows first 3 signals
- Test rate limiter blocks 4th signal within window
- Test rate limiter resets after window expires
- Use `pytest.mark.asyncio` for async tests
- Use `AsyncMock` for async dependencies
- Mock time for rate limit window testing

**Integration Tests:**
- Test full signing flow: fork → signed signal → verified
- Test invalid signature rejection with logged attack
- Test rate limit enforcement: 3 allowed, 4th blocked
- Test rate limit event creation
- Test end-to-end: fork detection → signing → rate check → halt

**Coverage Target:** 100% for `SignedForkSignal` and rate limiting (security-critical paths)

### Previous Story Learnings (Story 3.7)

**From Story 3.7 (Sequence Gap Detection):**
- `signable_content()` pattern for event payloads
- Include all fields in deterministic order
- Sort collections (UUIDs, etc.) before serialization
- Use f-string concatenation for content construction
- Add `previous_check_timestamp` equivalent fields where relevant

**From Story 3.1-3.2 (Fork Detection + Halt):**
- `ForkDetectedPayload` exists but needs `signable_content()`
- `ForkMonitoringService` exists - extend rather than replace
- `ConstitutionalCrisisPayload` has `signable_content()` (just added in 3.7 review)
- Integration with `HaltTriggerPort` for halt cascade

**Code Review Learnings from 3.7:**
- Always add `signable_content()` to event payloads that need witnessing
- Include all fields in signed content - don't miss any
- Sort collections for deterministic output
- Export new types from `__init__.py` immediately

### Dependencies

**Story Dependencies:**
- **Story 1.3 (Agent Attribution):** Provides signing infrastructure
- **Story 1.6 (Event Writer Service):** For creating witnessed events
- **Story 3.1 (Fork Detection):** Provides `ForkDetectedPayload` and `ForkMonitoringService`
- **Story 3.2 (Halt Trigger):** Integration for halt cascade

**Epic Dependencies:**
- **Epic 1 (Event Store):** Signing infrastructure

**Forward Dependencies:**
- **Story 3.9 (Witnessed Halt Event):** Uses signed signals
- **Epic 4 (Observer Interface):** Observers verify signed signals

### Security Considerations

**Attack Vectors Mitigated:**
1. **Fabricated fork signals:** Signing ensures only legitimate services can create signals
2. **Fork signal spam:** Rate limiting prevents DoS via fake fork flood
3. **Replay attacks:** Timestamps and signing key IDs provide uniqueness
4. **Phantom attacks:** Logging invalid signatures creates audit trail

**Remaining Attack Surface:**
- Compromised service key could sign fake signals (mitigated by key rotation ceremony)
- Rate limit could be circumvented by using multiple source IDs (mitigated by monitoring)
- Valid signal replay (mitigated by event deduplication in event store)

**Constitutional Safeguards:**
- FR84: All fork signals must be signed
- FR85: Rate limiting prevents signal spam
- CT-12: Signing creates accountability chain
- Logged rejections enable forensic analysis

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.8]
- [Source: _bmad-output/planning-artifacts/architecture.md#FP-5] - Centralized SigningService
- [Source: _bmad-output/planning-artifacts/architecture.md#RT-2] - Witness collusion defense
- [Source: src/domain/events/fork_detected.py] - Existing ForkDetectedPayload
- [Source: src/application/services/fork_monitoring_service.py] - Service to extend
- [Source: src/application/services/signing_service.py] - SigningService pattern
- [Source: _bmad-output/implementation-artifacts/stories/3-7-sequence-gap-detection.md] - Previous story patterns
- [Source: _bmad-output/planning-artifacts/project-context.md#Constitutional-Implementation-Rules]

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
