# Story consent-gov-9.3: Independent Verification

Status: done

---

## Story

As a **verifier**,
I want **to independently verify ledger integrity**,
So that **I don't have to trust the system**.

---

## Acceptance Criteria

1. **AC1:** Independent hash chain verification (FR58) ✅
2. **AC2:** Independent Merkle proof verification ✅
3. **AC3:** State derivable through event replay (NFR-AUDIT-06) ✅
4. **AC4:** Verification possible offline with exported ledger ✅
5. **AC5:** Event `audit.verification.completed` emitted after verification ✅
6. **AC6:** Verification detects tampering ✅
7. **AC7:** Verification detects missing events ✅
8. **AC8:** Unit tests for verification ✅

---

## Tasks / Subtasks

- [x] **Task 1: Create VerificationResult domain model** (AC: 1)
  - [x] Create `src/domain/governance/audit/verification_result.py`
  - [x] Include hash_chain_valid, merkle_valid
  - [x] Include detected_issues list
  - [x] Include verification timestamp

- [x] **Task 2: Create IndependentVerificationService** (AC: 1, 2, 5)
  - [x] Create `src/application/services/governance/independent_verification_service.py`
  - [x] Verify hash chain independently
  - [x] Verify Merkle proofs independently
  - [x] Emit verification events

- [x] **Task 3: Create VerificationPort interface** (AC: 1)
  - [x] Create port for verification operations
  - [x] Define `verify_hash_chain()` method
  - [x] Define `verify_merkle_proof()` method
  - [x] Define `verify_completeness()` method

- [x] **Task 4: Implement hash chain verification** (AC: 1)
  - [x] Recompute each event hash
  - [x] Verify prev_hash linkage
  - [x] Detect any breaks in chain
  - [x] Return detailed results

- [x] **Task 5: Implement Merkle verification** (AC: 2)
  - [x] Verify proof-of-inclusion for any event
  - [x] Reconstruct path to root
  - [x] Verify root matches expected
  - [x] Return verification result

- [x] **Task 6: Implement state replay** (AC: 3)
  - [x] Replay events from genesis
  - [x] Derive state from events
  - [x] State should be deterministic
  - [x] Same events = same state

- [x] **Task 7: Implement offline verification** (AC: 4)
  - [x] Work with exported ledger only
  - [x] No network calls required
  - [x] All data in export
  - [x] Standalone verification

- [x] **Task 8: Implement tampering detection** (AC: 6)
  - [x] Detect modified events (hash mismatch)
  - [x] Detect reordered events
  - [x] Detect content changes
  - [x] Clear error messages

- [x] **Task 9: Implement gap detection** (AC: 7)
  - [x] Detect missing sequence numbers
  - [x] Detect broken prev_hash links
  - [x] Report specific gaps
  - [x] Clear error messages

- [x] **Task 10: Write comprehensive unit tests** (AC: 8)
  - [x] Test valid ledger passes
  - [x] Test tampered ledger detected
  - [x] Test missing events detected
  - [x] Test state replay works
  - [x] Test offline verification

---

## Documentation Checklist

- [ ] Architecture docs updated (verification procedures)
- [ ] Auditor guide for verification
- [ ] Inline comments explaining verification logic
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Independent Verification?**
```
Trust requires verification:
  - System says ledger is complete
  - Verifier should be able to check
  - No "trust us" required
  - Math provides guarantees

Independent means:
  - No system cooperation needed
  - Works with export only
  - Offline capable
  - Third party can verify
```

**State Replay:**
```
NFR-AUDIT-06: State derivable through event replay

Event sourcing principle:
  - Events are the source of truth
  - State = f(events)
  - Replay events → derive state
  - Deterministic: same events = same state

Verification:
  - Export ledger
  - Replay all events
  - Derive state
  - Compare to expected

If mismatch:
  - Either events modified
  - Or state calculation bug
  - Either way, problem detected
```

**Offline Verification:**
```
Why offline?
  - No network dependency
  - No system availability requirement
  - Verifier controls environment
  - Cannot be influenced by system

Requirements:
  - Export contains all data
  - Proofs self-contained
  - Verification algorithm known
  - Reproducible results
```

### Domain Models

```python
class VerificationStatus(Enum):
    """Status of verification."""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"  # Some checks passed, some failed


class IssueType(Enum):
    """Type of detected issue."""
    HASH_MISMATCH = "hash_mismatch"
    SEQUENCE_GAP = "sequence_gap"
    BROKEN_LINK = "broken_link"
    MERKLE_MISMATCH = "merkle_mismatch"
    STATE_MISMATCH = "state_mismatch"


@dataclass(frozen=True)
class DetectedIssue:
    """Issue detected during verification."""
    issue_type: IssueType
    event_id: UUID | None
    sequence_number: int | None
    description: str
    expected: str | None
    actual: str | None


@dataclass(frozen=True)
class VerificationResult:
    """Result of independent verification.

    Contains detailed results of all verification checks.
    """
    verification_id: UUID
    verified_at: datetime
    status: VerificationStatus
    hash_chain_valid: bool
    merkle_valid: bool
    sequence_complete: bool
    state_replay_valid: bool
    issues: list[DetectedIssue]
    total_events_verified: int


class VerificationFailedError(ValueError):
    """Raised when verification fails."""
    pass
```

### Service Implementation Sketch

```python
class IndependentVerificationService:
    """Verifies ledger integrity independently.

    Works offline with exported ledger.
    No system cooperation required.
    """

    def __init__(
        self,
        hash_algorithm: HashAlgorithm,
        merkle_algorithm: MerkleAlgorithm,
        state_replayer: StateReplayer,
        event_emitter: EventEmitter | None,  # Optional - can be None for offline
        time_authority: TimeAuthority,
    ):
        self._hash = hash_algorithm
        self._merkle = merkle_algorithm
        self._replayer = state_replayer
        self._event_emitter = event_emitter
        self._time = time_authority

    async def verify_complete(
        self,
        ledger_export: LedgerExport,
        verifier_id: UUID | None = None,
    ) -> VerificationResult:
        """Perform complete independent verification.

        Can be run offline (event_emitter optional).

        Args:
            ledger_export: The exported ledger to verify
            verifier_id: Optional verifier ID (for logging)

        Returns:
            VerificationResult with all check results
        """
        now = self._time.now()
        verification_id = uuid4()
        issues = []

        # Verify hash chain
        chain_valid, chain_issues = await self._verify_hash_chain(
            ledger_export.events
        )
        issues.extend(chain_issues)

        # Verify sequence completeness
        seq_complete, seq_issues = await self._verify_sequence(
            ledger_export.events
        )
        issues.extend(seq_issues)

        # Verify Merkle root (if provided)
        merkle_valid = True
        if hasattr(ledger_export, 'merkle_root'):
            merkle_valid, merkle_issues = await self._verify_merkle(
                ledger_export.events,
                ledger_export.merkle_root,
            )
            issues.extend(merkle_issues)

        # Verify state replay
        replay_valid, replay_issues = await self._verify_state_replay(
            ledger_export.events
        )
        issues.extend(replay_issues)

        # Determine overall status
        if chain_valid and seq_complete and merkle_valid and replay_valid:
            status = VerificationStatus.VALID
        elif not issues:
            status = VerificationStatus.VALID
        elif any(chain_valid, seq_complete, merkle_valid, replay_valid):
            status = VerificationStatus.PARTIAL
        else:
            status = VerificationStatus.INVALID

        result = VerificationResult(
            verification_id=verification_id,
            verified_at=now,
            status=status,
            hash_chain_valid=chain_valid,
            merkle_valid=merkle_valid,
            sequence_complete=seq_complete,
            state_replay_valid=replay_valid,
            issues=issues,
            total_events_verified=len(ledger_export.events),
        )

        # Emit event if online
        if self._event_emitter and verifier_id:
            await self._event_emitter.emit(
                event_type="audit.verification.completed",
                actor=str(verifier_id),
                payload={
                    "verification_id": str(verification_id),
                    "verifier_id": str(verifier_id),
                    "verified_at": now.isoformat(),
                    "status": status.value,
                    "hash_chain_valid": chain_valid,
                    "merkle_valid": merkle_valid,
                    "sequence_complete": seq_complete,
                    "issues_count": len(issues),
                },
            )

        return result

    async def _verify_hash_chain(
        self,
        events: list[EventEnvelope],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify hash chain independently."""
        issues = []

        if not events:
            return True, issues

        for i, event in enumerate(events):
            # Compute expected hash
            prev_hash = events[i-1].event_hash if i > 0 else "0" * 64
            expected_hash = self._hash.compute(
                event.payload,
                prev_hash,
            )

            # Check event hash matches
            if event.event_hash != expected_hash:
                issues.append(DetectedIssue(
                    issue_type=IssueType.HASH_MISMATCH,
                    event_id=event.event_id,
                    sequence_number=event.sequence_number,
                    description=f"Hash mismatch at event {event.sequence_number}",
                    expected=expected_hash,
                    actual=event.event_hash,
                ))

            # Check prev_hash link
            if i > 0 and event.prev_hash != events[i-1].event_hash:
                issues.append(DetectedIssue(
                    issue_type=IssueType.BROKEN_LINK,
                    event_id=event.event_id,
                    sequence_number=event.sequence_number,
                    description=f"Broken link at event {event.sequence_number}",
                    expected=events[i-1].event_hash,
                    actual=event.prev_hash,
                ))

        return len(issues) == 0, issues

    async def _verify_sequence(
        self,
        events: list[EventEnvelope],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify sequence is complete with no gaps."""
        issues = []

        expected_seq = 1
        for event in events:
            if event.sequence_number != expected_seq:
                issues.append(DetectedIssue(
                    issue_type=IssueType.SEQUENCE_GAP,
                    event_id=event.event_id,
                    sequence_number=event.sequence_number,
                    description=f"Gap at sequence {expected_seq}",
                    expected=str(expected_seq),
                    actual=str(event.sequence_number),
                ))
            expected_seq = event.sequence_number + 1

        return len(issues) == 0, issues

    async def _verify_merkle(
        self,
        events: list[EventEnvelope],
        expected_root: str,
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify Merkle root matches."""
        issues = []

        computed_root = self._merkle.compute_root(
            [e.event_hash for e in events]
        )

        if computed_root != expected_root:
            issues.append(DetectedIssue(
                issue_type=IssueType.MERKLE_MISMATCH,
                event_id=None,
                sequence_number=None,
                description="Merkle root mismatch",
                expected=expected_root,
                actual=computed_root,
            ))

        return len(issues) == 0, issues

    async def _verify_state_replay(
        self,
        events: list[EventEnvelope],
    ) -> tuple[bool, list[DetectedIssue]]:
        """Verify state can be derived through replay."""
        issues = []

        try:
            # Replay events
            state = await self._replayer.replay(events)

            # State should be derivable
            if state is None:
                issues.append(DetectedIssue(
                    issue_type=IssueType.STATE_MISMATCH,
                    event_id=None,
                    sequence_number=None,
                    description="State could not be derived from events",
                    expected="Valid state",
                    actual="None",
                ))
        except Exception as e:
            issues.append(DetectedIssue(
                issue_type=IssueType.STATE_MISMATCH,
                event_id=None,
                sequence_number=None,
                description=f"State replay failed: {e}",
                expected="Successful replay",
                actual="Exception",
            ))

        return len(issues) == 0, issues

    async def verify_offline(
        self,
        ledger_json: str,
    ) -> VerificationResult:
        """Verify ledger from JSON export (fully offline).

        No network calls. No event emission.

        Args:
            ledger_json: JSON string of exported ledger

        Returns:
            VerificationResult
        """
        # Parse export
        export_data = json.loads(ledger_json)
        ledger_export = LedgerExport.from_dict(export_data)

        # Verify without event emission
        return await self.verify_complete(
            ledger_export=ledger_export,
            verifier_id=None,
        )
```

### Event Pattern

```python
# Verification completed
{
    "event_type": "audit.verification.completed",
    "actor": "verifier-uuid",
    "payload": {
        "verification_id": "uuid",
        "verifier_id": "uuid",
        "verified_at": "2026-01-16T00:00:00Z",
        "status": "valid",
        "hash_chain_valid": true,
        "merkle_valid": true,
        "sequence_complete": true,
        "issues_count": 0
    }
}
```

### Test Patterns

```python
class TestIndependentVerificationService:
    """Unit tests for independent verification service."""

    async def test_valid_ledger_passes(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ):
        """Valid ledger passes all verification checks."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.status == VerificationStatus.VALID
        assert result.hash_chain_valid
        assert result.merkle_valid
        assert result.sequence_complete

    async def test_tampered_event_detected(
        self,
        verification_service: IndependentVerificationService,
        export_with_tampered_event: LedgerExport,
    ):
        """Tampered event is detected."""
        result = await verification_service.verify_complete(
            ledger_export=export_with_tampered_event,
        )

        assert result.status != VerificationStatus.VALID
        assert not result.hash_chain_valid
        assert any(i.issue_type == IssueType.HASH_MISMATCH for i in result.issues)

    async def test_missing_event_detected(
        self,
        verification_service: IndependentVerificationService,
        export_with_gap: LedgerExport,
    ):
        """Missing event (gap) is detected."""
        result = await verification_service.verify_complete(
            ledger_export=export_with_gap,
        )

        assert result.status != VerificationStatus.VALID
        assert not result.sequence_complete
        assert any(i.issue_type == IssueType.SEQUENCE_GAP for i in result.issues)

    async def test_verification_event_emitted(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
        verifier: Verifier,
        event_capture: EventCapture,
    ):
        """Verification event is emitted."""
        await verification_service.verify_complete(
            ledger_export=valid_export,
            verifier_id=verifier.id,
        )

        event = event_capture.get_last("audit.verification.completed")
        assert event is not None


class TestOfflineVerification:
    """Tests for offline verification capability."""

    async def test_works_offline(
        self,
        offline_verification_service: IndependentVerificationService,
        valid_export_json: str,
    ):
        """Verification works completely offline."""
        result = await offline_verification_service.verify_offline(
            ledger_json=valid_export_json,
        )

        assert result.status == VerificationStatus.VALID

    async def test_no_network_required(
        self,
        verification_service_no_emitter: IndependentVerificationService,
        valid_export: LedgerExport,
    ):
        """Verification requires no network."""
        # Service constructed without event emitter
        result = await verification_service_no_emitter.verify_complete(
            ledger_export=valid_export,
        )

        assert result is not None


class TestStateReplay:
    """Tests for state derivation through replay."""

    async def test_state_derivable(
        self,
        verification_service: IndependentVerificationService,
        valid_export: LedgerExport,
    ):
        """State is derivable from events."""
        result = await verification_service.verify_complete(
            ledger_export=valid_export,
        )

        assert result.state_replay_valid

    async def test_deterministic_replay(
        self,
        state_replayer: StateReplayer,
        events: list[EventEnvelope],
    ):
        """Replay is deterministic - same events = same state."""
        state1 = await state_replayer.replay(events)
        state2 = await state_replayer.replay(events)

        assert state1 == state2


class TestTamperingDetection:
    """Tests for tampering detection."""

    async def test_modified_content_detected(
        self,
        verification_service: IndependentVerificationService,
        export_with_modified_content: LedgerExport,
    ):
        """Modified event content is detected."""
        result = await verification_service.verify_complete(
            ledger_export=export_with_modified_content,
        )

        assert not result.hash_chain_valid
        assert any("mismatch" in i.description.lower() for i in result.issues)

    async def test_reordered_events_detected(
        self,
        verification_service: IndependentVerificationService,
        export_with_reordered_events: LedgerExport,
    ):
        """Reordered events are detected."""
        result = await verification_service.verify_complete(
            ledger_export=export_with_reordered_events,
        )

        # Reordering breaks hash chain
        assert not result.hash_chain_valid


class TestGapDetection:
    """Tests for gap detection."""

    async def test_sequence_gap_detected(
        self,
        verification_service: IndependentVerificationService,
        export_missing_event_5: LedgerExport,
    ):
        """Gap in sequence numbers is detected."""
        result = await verification_service.verify_complete(
            ledger_export=export_missing_event_5,
        )

        assert not result.sequence_complete
        gap_issues = [i for i in result.issues if i.issue_type == IssueType.SEQUENCE_GAP]
        assert len(gap_issues) > 0
        assert gap_issues[0].expected == "5"
```

### Dependencies

- **Depends on:** consent-gov-9-1 (ledger export), consent-gov-9-2 (proof generation)
- **Enables:** Third-party auditing without system trust

### References

- FR58: Any participant can independently verify ledger integrity
- NFR-AUDIT-06: Ledger export enables deterministic state derivation by replay
