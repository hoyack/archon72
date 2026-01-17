# Story consent-gov-5.3: Explicit Upward Transitions

Status: ready-for-dev

---

## Story

As a **Human Operator**,
I want **to acknowledge and execute upward legitimacy transitions**,
So that **restoration requires explicit human decision**.

---

## Acceptance Criteria

1. **AC1:** Upward transition requires explicit acknowledgment (FR30)
2. **AC2:** No automatic upward transitions (FR32)
3. **AC3:** Acknowledgment logged in append-only ledger (FR31)
4. **AC4:** Only one band up at a time (gradual restoration)
5. **AC5:** Operator must be authenticated and authorized
6. **AC6:** Event `constitutional.legitimacy.band_increased` emitted
7. **AC7:** Acknowledgment includes reason and evidence
8. **AC8:** FAILED state cannot be restored (terminal)
9. **AC9:** Unit tests for acknowledgment requirement

---

## Tasks / Subtasks

- [ ] **Task 1: Create LegitimacyRestorationPort interface** (AC: 1, 2)
  - [ ] Create `src/application/ports/governance/legitimacy_restoration_port.py`
  - [ ] Define `request_restoration()` method
  - [ ] Include operator_id, reason, evidence parameters
  - [ ] Return restoration result

- [ ] **Task 2: Create RestorationAcknowledgment domain model** (AC: 1, 7)
  - [ ] Create `src/domain/governance/legitimacy/restoration_acknowledgment.py`
  - [ ] Define immutable value object
  - [ ] Include operator_id, reason, evidence, timestamp
  - [ ] Include acknowledgment_id for tracking

- [ ] **Task 3: Implement LegitimacyRestorationService** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `src/application/services/governance/legitimacy_restoration_service.py`
  - [ ] Verify operator authorization
  - [ ] Validate transition (one step only)
  - [ ] Record acknowledgment
  - [ ] Execute transition

- [ ] **Task 4: Implement authorization check** (AC: 5)
  - [ ] Verify operator identity
  - [ ] Check restoration permission in rank matrix
  - [ ] Only Human Operator rank can restore
  - [ ] Log unauthorized attempts

- [ ] **Task 5: Implement one-step constraint** (AC: 4)
  - [ ] Validate target band is exactly one step up
  - [ ] Reject multi-step restoration attempts
  - [ ] Require separate acknowledgments for each step
  - [ ] Return clear error for invalid requests

- [ ] **Task 6: Implement FAILED terminal constraint** (AC: 8)
  - [ ] FAILED state cannot transition upward
  - [ ] Return specific error for FAILED restoration attempts
  - [ ] Document that reconstitution is required
  - [ ] No exceptions to this rule

- [ ] **Task 7: Implement acknowledgment recording** (AC: 3, 7)
  - [ ] Create acknowledgment record
  - [ ] Write to append-only ledger
  - [ ] Include reason and evidence
  - [ ] Link acknowledgment to transition

- [ ] **Task 8: Implement band_increased event emission** (AC: 6)
  - [ ] Emit `constitutional.legitimacy.band_increased`
  - [ ] Include from_band, to_band
  - [ ] Include operator_id and acknowledgment_id
  - [ ] Knight observes all restoration events

- [ ] **Task 9: Create restoration API endpoint** (AC: 1, 5)
  - [ ] POST `/governance/legitimacy/restore` endpoint
  - [ ] Require authentication
  - [ ] Require restoration permission
  - [ ] Return restoration result

- [ ] **Task 10: Write comprehensive unit tests** (AC: 9)
  - [ ] Test acknowledgment required for upward
  - [ ] Test automatic upward rejected
  - [ ] Test one step at a time
  - [ ] Test FAILED is terminal
  - [ ] Test acknowledgment logged
  - [ ] Test band_increased event emitted
  - [ ] Test unauthorized operator rejected

---

## Documentation Checklist

- [ ] Architecture docs updated (restoration workflow)
- [ ] Operations runbook for legitimacy restoration
- [ ] Inline comments explaining acknowledgment requirement
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Explicit Acknowledgment?**
```
Restoration requires human judgment:
  - Automatic restoration would hide problems
  - Human must verify underlying issue is resolved
  - Creates accountability for restoration decision
  - Prevents premature "everything is fine" signals

NFR-CONST-04 requires:
  - Explicit actor (not "system")
  - Documented reason
  - Traceable decision
```

**Why One Step at a Time?**
```
Gradual restoration:
  - COMPROMISED → ERODING → STRAINED → STABLE
  - Each step requires separate acknowledgment
  - Operator must consciously affirm each level
  - Prevents "jumping" from COMPROMISED to STABLE

This ensures:
  - Deliberate, thoughtful restoration
  - Multiple checkpoints for verification
  - Clear audit trail of decisions
  - Time for observation between steps
```

**Why FAILED is Terminal?**
```
FAILED represents fundamental integrity compromise:
  - Hash chain broken
  - Event tampering detected
  - Trust model violated

Recovery options:
  1. Reconstitution (new system instance)
  2. Fork resolution (if applicable)
  3. None - accept cessation

Restoration within the existing system is NOT possible
because the foundational trust is broken.
```

### Domain Models

```python
@dataclass(frozen=True)
class RestorationAcknowledgment:
    """Acknowledgment for legitimacy restoration."""
    acknowledgment_id: UUID
    operator_id: UUID
    from_band: LegitimacyBand
    to_band: LegitimacyBand
    reason: str
    evidence: str
    acknowledged_at: datetime


@dataclass(frozen=True)
class RestorationRequest:
    """Request to restore legitimacy."""
    operator_id: UUID
    target_band: LegitimacyBand
    reason: str
    evidence: str


@dataclass(frozen=True)
class RestorationResult:
    """Result of restoration attempt."""
    success: bool
    new_state: LegitimacyState | None
    acknowledgment: RestorationAcknowledgment | None
    error: str | None

    @classmethod
    def succeeded(
        cls,
        new_state: LegitimacyState,
        acknowledgment: RestorationAcknowledgment,
    ) -> "RestorationResult":
        return cls(
            success=True,
            new_state=new_state,
            acknowledgment=acknowledgment,
            error=None,
        )

    @classmethod
    def failed(cls, error: str) -> "RestorationResult":
        return cls(
            success=False,
            new_state=None,
            acknowledgment=None,
            error=error,
        )
```

### Service Implementation Sketch

```python
class LegitimacyRestorationService:
    """Handles explicit legitimacy restoration."""

    def __init__(
        self,
        legitimacy_state_port: LegitimacyStatePort,
        permission_matrix: PermissionMatrixPort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._state = legitimacy_state_port
        self._permissions = permission_matrix
        self._event_emitter = event_emitter
        self._time = time_authority

    async def request_restoration(
        self,
        request: RestorationRequest,
    ) -> RestorationResult:
        """Request legitimacy restoration."""

        # 1. Verify authorization
        try:
            await self._verify_restoration_permission(request.operator_id)
        except UnauthorizedError as e:
            return RestorationResult.failed(str(e))

        # 2. Get current state
        current_state = await self._state.get_legitimacy_state()

        # 3. Validate FAILED constraint
        if current_state.current_band == LegitimacyBand.FAILED:
            return RestorationResult.failed(
                "FAILED is terminal - reconstitution required"
            )

        # 4. Validate one-step constraint
        current_severity = current_state.current_band.severity
        target_severity = request.target_band.severity

        if target_severity >= current_severity:
            return RestorationResult.failed(
                f"Target band must be higher than current "
                f"({request.target_band.value} vs {current_state.current_band.value})"
            )

        if target_severity != current_severity - 1:
            return RestorationResult.failed(
                "Restoration must be one step at a time"
            )

        # 5. Create acknowledgment
        now = self._time.now()
        acknowledgment = RestorationAcknowledgment(
            acknowledgment_id=uuid4(),
            operator_id=request.operator_id,
            from_band=current_state.current_band,
            to_band=request.target_band,
            reason=request.reason,
            evidence=request.evidence,
            acknowledged_at=now,
        )

        # 6. Record acknowledgment to ledger
        await self._record_acknowledgment(acknowledgment)

        # 7. Execute transition
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=current_state.current_band,
            to_band=request.target_band,
            transition_type=TransitionType.ACKNOWLEDGED,
            actor=str(request.operator_id),
            triggering_event_id=None,
            acknowledgment_id=acknowledgment.acknowledgment_id,
            timestamp=now,
            reason=request.reason,
        )

        new_state = LegitimacyState(
            current_band=request.target_band,
            entered_at=now,
            violation_count=current_state.violation_count,  # Count preserved
            last_triggering_event_id=None,
            last_transition_type="acknowledged",
        )

        await self._state.save_transition(transition)
        await self._state.update_state(new_state)

        # 8. Emit event
        await self._event_emitter.emit(
            event_type="constitutional.legitimacy.band_increased",
            actor=str(request.operator_id),
            payload={
                "from_band": current_state.current_band.value,
                "to_band": request.target_band.value,
                "operator_id": str(request.operator_id),
                "acknowledgment_id": str(acknowledgment.acknowledgment_id),
                "reason": request.reason,
                "restored_at": now.isoformat(),
            },
        )

        return RestorationResult.succeeded(new_state, acknowledgment)

    async def _verify_restoration_permission(self, operator_id: UUID) -> None:
        """Verify operator has restoration permission."""
        permissions = await self._permissions.get_permissions_for_actor(operator_id)

        if "restore_legitimacy" not in permissions.allowed_actions:
            # Log unauthorized attempt
            await self._event_emitter.emit(
                event_type="security.unauthorized_restoration_attempt",
                actor=str(operator_id),
                payload={"attempted_action": "restore_legitimacy"},
            )
            raise UnauthorizedError("Operator not authorized to restore legitimacy")

    async def _record_acknowledgment(
        self,
        acknowledgment: RestorationAcknowledgment,
    ) -> None:
        """Record acknowledgment to append-only ledger."""
        await self._event_emitter.emit(
            event_type="constitutional.legitimacy.restoration_acknowledged",
            actor=str(acknowledgment.operator_id),
            payload={
                "acknowledgment_id": str(acknowledgment.acknowledgment_id),
                "from_band": acknowledgment.from_band.value,
                "to_band": acknowledgment.to_band.value,
                "reason": acknowledgment.reason,
                "evidence": acknowledgment.evidence,
                "acknowledged_at": acknowledgment.acknowledged_at.isoformat(),
            },
        )
```

### API Endpoint

```python
@router.post("/governance/legitimacy/restore")
async def restore_legitimacy(
    request: RestoreRequest,
    operator: Operator = Depends(get_authenticated_operator),
    restoration_service: LegitimacyRestorationService = Depends(),
) -> RestoreResponse:
    """Restore legitimacy band with acknowledgment.

    Requires:
    - Authentication
    - restore_legitimacy permission
    - Current band is not FAILED
    - Target band is exactly one step up
    """
    result = await restoration_service.request_restoration(
        RestorationRequest(
            operator_id=operator.id,
            target_band=LegitimacyBand(request.target_band),
            reason=request.reason,
            evidence=request.evidence,
        )
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return RestoreResponse(
        success=True,
        new_band=result.new_state.current_band.value,
        acknowledgment_id=str(result.acknowledgment.acknowledgment_id),
    )


class RestoreRequest(BaseModel):
    """Request to restore legitimacy."""
    target_band: str  # LegitimacyBand value
    reason: str
    evidence: str

    @validator("reason")
    def reason_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Reason is required")
        return v

    @validator("evidence")
    def evidence_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Evidence is required")
        return v


class RestoreResponse(BaseModel):
    """Response from restoration attempt."""
    success: bool
    new_band: str
    acknowledgment_id: str
```

### Event Patterns

```python
# Restoration acknowledged (recorded to ledger)
{
    "event_type": "constitutional.legitimacy.restoration_acknowledged",
    "actor": "operator-uuid",
    "payload": {
        "acknowledgment_id": "uuid",
        "from_band": "strained",
        "to_band": "stable",
        "reason": "Coercion patterns addressed in content review",
        "evidence": "Audit ID: AUD-2026-0115, all patterns resolved",
        "acknowledged_at": "2026-01-16T00:00:00Z"
    }
}

# Band increased event
{
    "event_type": "constitutional.legitimacy.band_increased",
    "actor": "operator-uuid",
    "payload": {
        "from_band": "strained",
        "to_band": "stable",
        "operator_id": "uuid",
        "acknowledgment_id": "uuid",
        "reason": "Coercion patterns addressed in content review",
        "restored_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestLegitimacyRestorationService:
    """Unit tests for explicit legitimacy restoration."""

    async def test_acknowledgment_required_for_upward(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        strained_state: LegitimacyState,
    ):
        """Upward transition requires acknowledgment."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Audit complete",
            )
        )

        assert result.success
        assert result.acknowledgment is not None
        assert result.new_state.current_band == LegitimacyBand.STABLE

    async def test_automatic_upward_rejected(
        self,
        decay_service: LegitimacyDecayService,
        strained_state: LegitimacyState,
    ):
        """Automatic upward transitions are rejected."""
        # Decay service cannot move upward
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="nonexistent.violation",  # Would default to MINOR
        )

        # Should not improve from STRAINED
        assert result.current_band.severity >= strained_state.current_band.severity

    async def test_one_step_at_a_time(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        compromised_state: LegitimacyState,
    ):
        """Restoration must be one step at a time."""
        # Try to jump from COMPROMISED to STABLE
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STABLE,
                reason="Everything is fixed",
                evidence="Trust me",
            )
        )

        assert not result.success
        assert "one step" in result.error.lower()

    async def test_failed_is_terminal(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        failed_state: LegitimacyState,
    ):
        """FAILED state cannot be restored."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.COMPROMISED,
                reason="Attempting restore",
                evidence="Evidence",
            )
        )

        assert not result.success
        assert "terminal" in result.error.lower() or "reconstitution" in result.error.lower()

    async def test_acknowledgment_logged(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        strained_state: LegitimacyState,
        event_capture: EventCapture,
    ):
        """Acknowledgment is logged to ledger."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Audit ID: AUD-123",
            )
        )

        event = event_capture.get_last("constitutional.legitimacy.restoration_acknowledged")
        assert event is not None
        assert event.payload["reason"] == "Issues resolved"
        assert event.payload["evidence"] == "Audit ID: AUD-123"

    async def test_band_increased_event_emitted(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        strained_state: LegitimacyState,
        event_capture: EventCapture,
    ):
        """Band increased event is emitted."""
        await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STABLE,
                reason="Issues resolved",
                evidence="Evidence",
            )
        )

        event = event_capture.get_last("constitutional.legitimacy.band_increased")
        assert event is not None
        assert event.payload["from_band"] == "strained"
        assert event.payload["to_band"] == "stable"
        assert event.actor == str(authorized_operator.id)

    async def test_unauthorized_operator_rejected(
        self,
        restoration_service: LegitimacyRestorationService,
        regular_user: Operator,
        strained_state: LegitimacyState,
    ):
        """Unauthorized operator cannot restore."""
        result = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=regular_user.id,
                target_band=LegitimacyBand.STABLE,
                reason="Trying to restore",
                evidence="No evidence",
            )
        )

        assert not result.success
        assert "authorized" in result.error.lower() or "unauthorized" in result.error.lower()

    async def test_reason_and_evidence_required(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        strained_state: LegitimacyState,
    ):
        """Reason and evidence are required for restoration."""
        # Empty reason
        with pytest.raises(ValueError):
            RestoreRequest(
                target_band="stable",
                reason="",
                evidence="Some evidence",
            )

        # Empty evidence
        with pytest.raises(ValueError):
            RestoreRequest(
                target_band="stable",
                reason="Some reason",
                evidence="",
            )


class TestRestorationWorkflow:
    """Integration tests for full restoration workflow."""

    async def test_gradual_restoration_from_compromised(
        self,
        restoration_service: LegitimacyRestorationService,
        authorized_operator: Operator,
        compromised_state: LegitimacyState,
    ):
        """Restoration from COMPROMISED requires multiple steps."""
        # Step 1: COMPROMISED → ERODING
        result1 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.ERODING,
                reason="Critical issues addressed",
                evidence="Audit 1",
            )
        )
        assert result1.success
        assert result1.new_state.current_band == LegitimacyBand.ERODING

        # Step 2: ERODING → STRAINED
        result2 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STRAINED,
                reason="Significant issues addressed",
                evidence="Audit 2",
            )
        )
        assert result2.success
        assert result2.new_state.current_band == LegitimacyBand.STRAINED

        # Step 3: STRAINED → STABLE
        result3 = await restoration_service.request_restoration(
            RestorationRequest(
                operator_id=authorized_operator.id,
                target_band=LegitimacyBand.STABLE,
                reason="All issues resolved",
                evidence="Audit 3",
            )
        )
        assert result3.success
        assert result3.new_state.current_band == LegitimacyBand.STABLE
```

### Dependencies

- **Depends on:** consent-gov-5-1 (legitimacy band domain model), consent-gov-5-2 (automatic decay)
- **Enables:** Full legitimacy lifecycle management

### References

- FR30: Human Operator can acknowledge and execute upward legitimacy transition
- FR31: System can record all legitimacy transitions in append-only ledger
- FR32: System can prevent upward transitions without explicit acknowledgment
- NFR-CONST-04: All transitions logged with timestamp, actor, reason
