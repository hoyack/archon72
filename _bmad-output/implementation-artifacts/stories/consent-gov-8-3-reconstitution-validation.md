# Story consent-gov-8.3: Reconstitution Validation

Status: done

---

## Story

As a **governance system**,
I want **reconstitution artifacts validated before new instance**,
So that **new instances don't falsely inherit legitimacy**.

---

## Acceptance Criteria

1. **AC1:** Reconstitution Artifact validated (FR53)
2. **AC2:** Reject reconstitution claiming continuity (FR54)
3. **AC3:** Reject reconstitution inheriting legitimacy band (FR55)
4. **AC4:** New instance starts at baseline legitimacy
5. **AC5:** Event `constitutional.reconstitution.validated` or `rejected` emitted
6. **AC6:** Clear error messages explain rejection reasons
7. **AC7:** Valid artifact includes cessation record reference
8. **AC8:** Unit tests for validation rules

---

## Tasks / Subtasks

- [x] **Task 1: Create ReconstitutionArtifact domain model** (AC: 1, 7)
  - [x] Create `src/domain/governance/cessation/reconstitution_artifact.py`
  - [x] Include cessation_record_id reference
  - [x] Include proposed_legitimacy_band
  - [x] Include continuity_claims
  - [x] Immutable value object

- [x] **Task 2: Create ReconstitutionValidationService** (AC: 1, 5)
  - [x] Create `src/application/services/governance/reconstitution_validation_service.py`
  - [x] Validate artifact structure
  - [x] Check for prohibited claims
  - [x] Emit validation result events

- [x] **Task 3: Create ReconstitutionPort interface** (AC: 1)
  - [x] Create port for validation operations
  - [x] Define `store_validation_result()` method
  - [x] Define `get_validation_result()` method
  - [x] Return typed validation result

- [x] **Task 4: Implement continuity rejection** (AC: 2)
  - [x] Detect continuity claims in artifact
  - [x] Reject if claims_continuity = true
  - [x] Reject if references "same system"
  - [x] Clear rejection message

- [x] **Task 5: Implement legitimacy rejection** (AC: 3, 4)
  - [x] Reject if proposed_band != BASELINE
  - [x] Cannot inherit previous band
  - [x] New instance must earn legitimacy
  - [x] Starts at STABLE (baseline)

- [x] **Task 6: Implement validation success path** (AC: 1, 7)
  - [x] Valid artifact references cessation record
  - [x] Valid artifact has no continuity claims
  - [x] Valid artifact proposes BASELINE legitimacy
  - [x] Emit validation success event

- [x] **Task 7: Implement clear error messages** (AC: 6)
  - [x] `CONTINUITY_CLAIM_REJECTED`: "New instance cannot claim continuity"
  - [x] `LEGITIMACY_INHERITANCE_REJECTED`: "New instance cannot inherit legitimacy"
  - [x] `MISSING_CESSATION_REFERENCE`: "Must reference cessation record"
  - [x] Human-readable explanations

- [x] **Task 8: Write comprehensive unit tests** (AC: 8)
  - [x] Test valid artifact accepted
  - [x] Test continuity claim rejected
  - [x] Test legitimacy inheritance rejected
  - [x] Test missing cessation rejected
  - [x] Test events emitted

---

## Documentation Checklist

- [x] Architecture docs updated (reconstitution rules)
- [x] Operations runbook for new instance setup
- [x] Inline comments explaining rejection logic
- [x] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Validate Reconstitution?**
```
New instance cannot falsely claim:
  - "We are the same system"
  - "We inherit previous legitimacy"
  - "Nothing has changed"

Why these restrictions?
  - Cessation is permanent
  - Trust must be re-earned
  - Clean constitutional break
  - No inherited authority

Without validation:
  - Bad actors could restart and claim continuity
  - Legitimacy could be falsely inherited
  - Cessation becomes meaningless
  - Constitutional guarantees violated
```

**Continuity Claims:**
```
FR54: Reject reconstitution that claims continuity

Prohibited claims:
  - "This is the same system"
  - "We continue where we left off"
  - "Same identity, new instance"
  - "Upgrade, not restart"

Why prohibited?
  - Cessation = permanent death of that instance
  - New instance = new identity
  - Cannot inherit trust
  - Must earn legitimacy fresh

Technical detection:
  - claims_continuity: true → REJECTED
  - same_system_id: <id> → REJECTED
  - references "continuation" → REJECTED
```

**Legitimacy Inheritance:**
```
FR55: Reject reconstitution that inherits legitimacy band

New instance MUST start at BASELINE:
  - Cannot claim STABLE from previous
  - Cannot skip to any band
  - Must earn each band
  - Clean slate

Why?
  - Legitimacy was earned by previous instance
  - Previous instance ceased to exist
  - New instance has not earned anything
  - Trust must be rebuilt

BASELINE = STABLE (starting point):
  - Not starting at FAILED
  - Not starting at COMPROMISED
  - Fresh start, neutral position
```

### Domain Models

```python
class ValidationStatus(Enum):
    """Status of reconstitution validation."""
    VALID = "valid"
    REJECTED = "rejected"


class RejectionReason(Enum):
    """Reason for reconstitution rejection."""
    CONTINUITY_CLAIM = "continuity_claim"
    LEGITIMACY_INHERITANCE = "legitimacy_inheritance"
    MISSING_CESSATION_REFERENCE = "missing_cessation_reference"
    INVALID_ARTIFACT_STRUCTURE = "invalid_artifact_structure"


@dataclass(frozen=True)
class ReconstitutionArtifact:
    """Artifact proposing new system instance.

    Must be validated before new instance can start.
    """
    artifact_id: UUID
    cessation_record_id: UUID | None  # Reference to previous cessation
    proposed_legitimacy_band: str  # Must be "STABLE" (baseline)
    claims_continuity: bool  # Must be False
    proposed_at: datetime
    proposer_id: UUID


@dataclass(frozen=True)
class ValidationResult:
    """Result of reconstitution validation."""
    artifact_id: UUID
    status: ValidationStatus
    rejection_reasons: list[RejectionReason]
    rejection_messages: list[str]
    validated_at: datetime


class ContinuityClaimRejectedError(ValueError):
    """Raised when reconstitution claims continuity."""
    pass


class LegitimacyInheritanceRejectedError(ValueError):
    """Raised when reconstitution tries to inherit legitimacy."""
    pass


class MissingCessationReferenceError(ValueError):
    """Raised when artifact doesn't reference cessation."""
    pass
```

### Service Implementation Sketch

```python
# Baseline legitimacy for new instances
BASELINE_LEGITIMACY_BAND = "STABLE"

# Rejection messages
REJECTION_MESSAGES = {
    RejectionReason.CONTINUITY_CLAIM: (
        "New instance cannot claim continuity with ceased system. "
        "Each system instance is a distinct constitutional entity."
    ),
    RejectionReason.LEGITIMACY_INHERITANCE: (
        "New instance cannot inherit legitimacy from previous instance. "
        "Legitimacy must be earned through operation, not claimed."
    ),
    RejectionReason.MISSING_CESSATION_REFERENCE: (
        "Reconstitution artifact must reference the cessation record "
        "of the previous instance to acknowledge its end."
    ),
    RejectionReason.INVALID_ARTIFACT_STRUCTURE: (
        "Reconstitution artifact has invalid structure. "
        "All required fields must be present and valid."
    ),
}


class ReconstitutionValidationService:
    """Validates reconstitution artifacts.

    Rejects artifacts that:
    - Claim continuity with previous instance
    - Try to inherit legitimacy band
    - Don't reference cessation record
    """

    def __init__(
        self,
        reconstitution_port: ReconstitutionPort,
        cessation_port: CessationRecordPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._reconstitution = reconstitution_port
        self._cessation = cessation_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def validate_artifact(
        self,
        artifact: ReconstitutionArtifact,
    ) -> ValidationResult:
        """Validate reconstitution artifact.

        Args:
            artifact: The reconstitution artifact to validate

        Returns:
            ValidationResult with status and any rejection reasons
        """
        now = self._time.now()
        rejection_reasons = []
        rejection_messages = []

        # Check for continuity claims (FR54)
        if artifact.claims_continuity:
            rejection_reasons.append(RejectionReason.CONTINUITY_CLAIM)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.CONTINUITY_CLAIM]
            )

        # Check for legitimacy inheritance (FR55)
        if artifact.proposed_legitimacy_band != BASELINE_LEGITIMACY_BAND:
            rejection_reasons.append(RejectionReason.LEGITIMACY_INHERITANCE)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.LEGITIMACY_INHERITANCE]
            )

        # Check for cessation reference
        if artifact.cessation_record_id is None:
            rejection_reasons.append(RejectionReason.MISSING_CESSATION_REFERENCE)
            rejection_messages.append(
                REJECTION_MESSAGES[RejectionReason.MISSING_CESSATION_REFERENCE]
            )
        else:
            # Verify cessation record exists
            cessation = await self._cessation.get_record()
            if cessation is None or cessation.record_id != artifact.cessation_record_id:
                rejection_reasons.append(RejectionReason.MISSING_CESSATION_REFERENCE)
                rejection_messages.append(
                    "Referenced cessation record does not exist."
                )

        # Determine result
        status = ValidationStatus.VALID if not rejection_reasons else ValidationStatus.REJECTED

        result = ValidationResult(
            artifact_id=artifact.artifact_id,
            status=status,
            rejection_reasons=rejection_reasons,
            rejection_messages=rejection_messages,
            validated_at=now,
        )

        # Emit appropriate event
        if status == ValidationStatus.VALID:
            await self._emit_validated_event(artifact, result)
        else:
            await self._emit_rejected_event(artifact, result)

        return result

    async def _emit_validated_event(
        self,
        artifact: ReconstitutionArtifact,
        result: ValidationResult,
    ) -> None:
        """Emit validation success event."""
        await self._event_emitter.emit(
            event_type="constitutional.reconstitution.validated",
            actor="system",
            payload={
                "artifact_id": str(artifact.artifact_id),
                "cessation_record_id": str(artifact.cessation_record_id),
                "proposed_legitimacy_band": artifact.proposed_legitimacy_band,
                "validated_at": result.validated_at.isoformat(),
            },
        )

    async def _emit_rejected_event(
        self,
        artifact: ReconstitutionArtifact,
        result: ValidationResult,
    ) -> None:
        """Emit validation rejection event."""
        await self._event_emitter.emit(
            event_type="constitutional.reconstitution.rejected",
            actor="system",
            payload={
                "artifact_id": str(artifact.artifact_id),
                "rejection_reasons": [r.value for r in result.rejection_reasons],
                "rejection_messages": result.rejection_messages,
                "validated_at": result.validated_at.isoformat(),
            },
        )


class ReconstitutionPort(Protocol):
    """Port for reconstitution operations."""

    async def store_validation_result(
        self,
        result: ValidationResult,
    ) -> None:
        """Store validation result."""
        ...

    async def get_validation_result(
        self,
        artifact_id: UUID,
    ) -> ValidationResult | None:
        """Get validation result for artifact."""
        ...
```

### Event Patterns

```python
# Reconstitution validated
{
    "event_type": "constitutional.reconstitution.validated",
    "actor": "system",
    "payload": {
        "artifact_id": "uuid",
        "cessation_record_id": "uuid",
        "proposed_legitimacy_band": "STABLE",
        "validated_at": "2026-01-16T00:00:00Z"
    }
}

# Reconstitution rejected
{
    "event_type": "constitutional.reconstitution.rejected",
    "actor": "system",
    "payload": {
        "artifact_id": "uuid",
        "rejection_reasons": ["continuity_claim", "legitimacy_inheritance"],
        "rejection_messages": [
            "New instance cannot claim continuity with ceased system...",
            "New instance cannot inherit legitimacy from previous instance..."
        ],
        "validated_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestReconstitutionValidationService:
    """Unit tests for reconstitution validation service."""

    async def test_valid_artifact_accepted(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
    ):
        """Valid artifact is accepted."""
        result = await validation_service.validate_artifact(
            artifact=valid_artifact,
        )

        assert result.status == ValidationStatus.VALID
        assert len(result.rejection_reasons) == 0

    async def test_continuity_claim_rejected(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ):
        """Artifact claiming continuity is rejected."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STABLE",
            claims_continuity=True,  # INVALID
            proposed_at=datetime.now(UTC),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(
            artifact=artifact,
        )

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.CONTINUITY_CLAIM in result.rejection_reasons

    async def test_legitimacy_inheritance_rejected(
        self,
        validation_service: ReconstitutionValidationService,
        cessation_record: CessationRecord,
    ):
        """Artifact inheriting legitimacy is rejected."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="COMPROMISED",  # INVALID - must be STABLE
            claims_continuity=False,
            proposed_at=datetime.now(UTC),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(
            artifact=artifact,
        )

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.LEGITIMACY_INHERITANCE in result.rejection_reasons

    async def test_missing_cessation_rejected(
        self,
        validation_service: ReconstitutionValidationService,
    ):
        """Artifact without cessation reference is rejected."""
        artifact = ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=None,  # INVALID - must reference cessation
            proposed_legitimacy_band="STABLE",
            claims_continuity=False,
            proposed_at=datetime.now(UTC),
            proposer_id=uuid4(),
        )

        result = await validation_service.validate_artifact(
            artifact=artifact,
        )

        assert result.status == ValidationStatus.REJECTED
        assert RejectionReason.MISSING_CESSATION_REFERENCE in result.rejection_reasons

    async def test_validated_event_emitted(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
        event_capture: EventCapture,
    ):
        """Validated event is emitted on success."""
        await validation_service.validate_artifact(
            artifact=valid_artifact,
        )

        event = event_capture.get_last("constitutional.reconstitution.validated")
        assert event is not None

    async def test_rejected_event_emitted(
        self,
        validation_service: ReconstitutionValidationService,
        invalid_artifact: ReconstitutionArtifact,
        event_capture: EventCapture,
    ):
        """Rejected event is emitted on failure."""
        await validation_service.validate_artifact(
            artifact=invalid_artifact,
        )

        event = event_capture.get_last("constitutional.reconstitution.rejected")
        assert event is not None


class TestValidArtifactRequirements:
    """Tests for valid artifact requirements."""

    @pytest.fixture
    def valid_artifact(
        self,
        cessation_record: CessationRecord,
    ) -> ReconstitutionArtifact:
        """Create valid artifact for testing."""
        return ReconstitutionArtifact(
            artifact_id=uuid4(),
            cessation_record_id=cessation_record.record_id,
            proposed_legitimacy_band="STABLE",  # Required baseline
            claims_continuity=False,  # Required
            proposed_at=datetime.now(UTC),
            proposer_id=uuid4(),
        )

    async def test_baseline_legitimacy_required(
        self,
        validation_service: ReconstitutionValidationService,
        valid_artifact: ReconstitutionArtifact,
    ):
        """New instance starts at baseline legitimacy."""
        result = await validation_service.validate_artifact(
            artifact=valid_artifact,
        )

        assert result.status == ValidationStatus.VALID
        assert valid_artifact.proposed_legitimacy_band == "STABLE"


class TestRejectionMessages:
    """Tests for clear rejection messages."""

    async def test_continuity_message_is_clear(
        self,
        validation_service: ReconstitutionValidationService,
        continuity_claiming_artifact: ReconstitutionArtifact,
    ):
        """Continuity rejection has clear message."""
        result = await validation_service.validate_artifact(
            artifact=continuity_claiming_artifact,
        )

        assert any(
            "cannot claim continuity" in msg.lower()
            for msg in result.rejection_messages
        )

    async def test_legitimacy_message_is_clear(
        self,
        validation_service: ReconstitutionValidationService,
        legitimacy_inheriting_artifact: ReconstitutionArtifact,
    ):
        """Legitimacy rejection has clear message."""
        result = await validation_service.validate_artifact(
            artifact=legitimacy_inheriting_artifact,
        )

        assert any(
            "cannot inherit legitimacy" in msg.lower()
            for msg in result.rejection_messages
        )
```

### Dependencies

- **Depends on:** consent-gov-8-2 (cessation record creation)
- **Enables:** New system instances can be properly validated

### References

- FR53: System can validate Reconstitution Artifact before new instance
- FR54: System can reject reconstitution that claims continuity
- FR55: System can reject reconstitution that inherits legitimacy band
