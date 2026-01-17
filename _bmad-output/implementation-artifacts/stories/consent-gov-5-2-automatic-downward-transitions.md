# Story consent-gov-5.2: Automatic Downward Transitions

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **automatic legitimacy decay based on violations**,
So that **system health degrades visibly when problems occur**.

---

## Acceptance Criteria

1. **AC1:** Auto-transition downward based on violation events (FR29)
2. **AC2:** Transition includes triggering event reference (NFR-AUDIT-04)
3. **AC3:** All transitions logged with timestamp, actor, reason (NFR-CONST-04)
4. **AC4:** Decay can skip bands based on violation severity
5. **AC5:** System actor for automatic transitions
6. **AC6:** Event `constitutional.legitimacy.band_decreased` emitted
7. **AC7:** Transition record includes violation_event_id
8. **AC8:** Multiple violations accumulate (don't reset on transition)
9. **AC9:** Unit tests for auto-decay scenarios

---

## Tasks / Subtasks

- [ ] **Task 1: Define violation severity mapping** (AC: 1, 4)
  - [ ] Create `src/domain/governance/legitimacy/violation_severity.py`
  - [ ] Map violation types to severity levels
  - [ ] Define how severity maps to band transitions
  - [ ] Severe violations can skip bands

- [ ] **Task 2: Create LegitimacyDecayPort interface** (AC: 1, 2)
  - [ ] Create `src/application/ports/governance/legitimacy_decay_port.py`
  - [ ] Define `process_violation()` method
  - [ ] Include violation_event_id parameter
  - [ ] Return new legitimacy state

- [ ] **Task 3: Implement LegitimacyDecayService** (AC: 1, 2, 3, 4, 5)
  - [ ] Create `src/application/services/governance/legitimacy_decay_service.py`
  - [ ] Receive violation events
  - [ ] Calculate target band based on severity
  - [ ] Execute transition with system actor

- [ ] **Task 4: Implement severity-based band calculation** (AC: 4)
  - [ ] Minor violation: drop 1 band (e.g., STABLE → STRAINED)
  - [ ] Major violation: drop 2 bands (e.g., STABLE → ERODING)
  - [ ] Critical violation: drop to COMPROMISED
  - [ ] Integrity violation: immediate FAILED

- [ ] **Task 5: Implement violation accumulation** (AC: 8)
  - [ ] Track violation_count in LegitimacyState
  - [ ] Increment on each violation
  - [ ] Count persists across transitions
  - [ ] Only reset on reconstitution

- [ ] **Task 6: Implement transition recording** (AC: 2, 3, 7)
  - [ ] Record transition with triggering_event_id
  - [ ] Include timestamp from TimeAuthority
  - [ ] Actor is "system" for automatic transitions
  - [ ] Include reason describing violation type

- [ ] **Task 7: Implement band_decreased event emission** (AC: 6)
  - [ ] Emit `constitutional.legitimacy.band_decreased`
  - [ ] Include from_band, to_band, severity
  - [ ] Include violation_event_id
  - [ ] Knight observes all decay events

- [ ] **Task 8: Subscribe to violation events** (AC: 1)
  - [ ] Listen for `constitutional.violation.*` events
  - [ ] Extract violation severity from event
  - [ ] Trigger decay processing

- [ ] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [ ] Test minor violation drops 1 band
  - [ ] Test major violation drops 2 bands
  - [ ] Test critical violation goes to COMPROMISED
  - [ ] Test integrity violation goes to FAILED
  - [ ] Test violation count accumulates
  - [ ] Test transition includes triggering event
  - [ ] Test band_decreased event emitted

---

## Documentation Checklist

- [ ] Architecture docs updated (auto-decay mechanism)
- [ ] Inline comments explaining severity mapping
- [ ] Violation type to severity documentation
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Why Automatic Decay?**
```
Violations are objective events that should have immediate effect:
  - No judgment call needed for severity (predefined mapping)
  - Delayed response would hide problems
  - System health should transparently reflect reality
  - Human cannot intervene to prevent decay (only to restore later)

This asymmetry is intentional:
  - Decay: automatic, immediate, objective
  - Restoration: explicit, deliberate, acknowledged
```

**Severity-to-Band Mapping:**
```
Violation Severity │ Effect
──────────────────┼──────────────────────────────────────
MINOR             │ Drop 1 band (e.g., STABLE → STRAINED)
MAJOR             │ Drop 2 bands (e.g., STABLE → ERODING)
CRITICAL          │ Jump to COMPROMISED
INTEGRITY         │ Immediate FAILED (terminal)
```

**Violation Type Examples:**
```
MINOR violations:
  - Task timeout without explicit decline
  - Reminder sent at 90% TTL (system strain indicator)
  - Advisory not acknowledged within 24h

MAJOR violations:
  - Coercion filter BLOCKED outcome
  - Consent bypassed in routing
  - Role constraint violated

CRITICAL violations:
  - Multiple concurrent coercion violations
  - Task created without authorization
  - Panel finding ignored

INTEGRITY violations:
  - Hash chain discontinuity
  - Event tampering detected
  - Witness signature invalid
```

### Domain Models

```python
class ViolationSeverity(Enum):
    """Severity level of governance violations."""

    MINOR = "minor"       # Drop 1 band
    MAJOR = "major"       # Drop 2 bands
    CRITICAL = "critical" # Jump to COMPROMISED
    INTEGRITY = "integrity"  # Immediate FAILED


# Violation type to severity mapping
VIOLATION_SEVERITY_MAP: dict[str, ViolationSeverity] = {
    # MINOR violations
    "task.timeout_without_decline": ViolationSeverity.MINOR,
    "task.reminder_at_90_percent": ViolationSeverity.MINOR,
    "advisory.acknowledgment_timeout": ViolationSeverity.MINOR,

    # MAJOR violations
    "coercion.filter_blocked": ViolationSeverity.MAJOR,
    "consent.bypass_detected": ViolationSeverity.MAJOR,
    "role.constraint_violated": ViolationSeverity.MAJOR,

    # CRITICAL violations
    "coercion.multiple_concurrent": ViolationSeverity.CRITICAL,
    "task.unauthorized_creation": ViolationSeverity.CRITICAL,
    "panel.finding_ignored": ViolationSeverity.CRITICAL,

    # INTEGRITY violations
    "chain.discontinuity": ViolationSeverity.INTEGRITY,
    "event.tampering_detected": ViolationSeverity.INTEGRITY,
    "witness.signature_invalid": ViolationSeverity.INTEGRITY,
}


def calculate_target_band(
    current: LegitimacyBand,
    severity: ViolationSeverity,
) -> LegitimacyBand:
    """Calculate target band based on violation severity."""

    if severity == ViolationSeverity.INTEGRITY:
        return LegitimacyBand.FAILED  # Terminal

    if severity == ViolationSeverity.CRITICAL:
        return LegitimacyBand.COMPROMISED

    # Calculate bands to drop
    bands_to_drop = 1 if severity == ViolationSeverity.MINOR else 2

    # Get ordered bands by severity
    bands = list(LegitimacyBand)
    current_idx = bands.index(current)
    target_idx = min(current_idx + bands_to_drop, len(bands) - 1)

    return bands[target_idx]
```

### Service Implementation Sketch

```python
class LegitimacyDecayService:
    """Handles automatic legitimacy decay based on violations."""

    def __init__(
        self,
        legitimacy_state_port: LegitimacyStatePort,
        event_emitter: EventEmitter,
        time_authority: TimeAuthority,
    ):
        self._state = legitimacy_state_port
        self._event_emitter = event_emitter
        self._time = time_authority

    async def process_violation(
        self,
        violation_event_id: UUID,
        violation_type: str,
    ) -> LegitimacyState:
        """Process violation and decay legitimacy if needed."""

        # 1. Get current state
        current_state = await self._state.get_legitimacy_state()

        # Skip if already FAILED (terminal)
        if current_state.current_band == LegitimacyBand.FAILED:
            return current_state

        # 2. Determine severity
        severity = VIOLATION_SEVERITY_MAP.get(
            violation_type,
            ViolationSeverity.MINOR,  # Default to minor if unknown
        )

        # 3. Calculate target band
        target_band = calculate_target_band(
            current_state.current_band,
            severity,
        )

        # Skip if no change needed
        if target_band == current_state.current_band:
            return current_state

        # 4. Execute transition
        now = self._time.now()
        transition = LegitimacyTransition(
            transition_id=uuid4(),
            from_band=current_state.current_band,
            to_band=target_band,
            transition_type=TransitionType.AUTOMATIC,
            actor="system",
            triggering_event_id=violation_event_id,
            acknowledgment_id=None,  # Automatic transitions have no ack
            timestamp=now,
            reason=f"Violation: {violation_type}",
        )

        # 5. Update state
        new_state = LegitimacyState(
            current_band=target_band,
            entered_at=now,
            violation_count=current_state.violation_count + 1,
            last_triggering_event_id=violation_event_id,
            last_transition_type="automatic",
        )

        await self._state.save_transition(transition)
        await self._state.update_state(new_state)

        # 6. Emit event
        await self._event_emitter.emit(
            event_type="constitutional.legitimacy.band_decreased",
            actor="system",
            payload={
                "from_band": current_state.current_band.value,
                "to_band": target_band.value,
                "severity": severity.value,
                "violation_type": violation_type,
                "violation_event_id": str(violation_event_id),
                "violation_count": new_state.violation_count,
                "transitioned_at": now.isoformat(),
            },
        )

        return new_state


# Event subscription
class ViolationEventSubscriber:
    """Subscribes to violation events and triggers decay."""

    def __init__(
        self,
        decay_service: LegitimacyDecayService,
        event_bus: EventBus,
    ):
        self._decay = decay_service
        self._bus = event_bus

        # Subscribe to all violation events
        self._bus.subscribe(
            pattern="constitutional.violation.*",
            handler=self._handle_violation,
        )

    async def _handle_violation(self, event: Event) -> None:
        """Handle incoming violation event."""
        await self._decay.process_violation(
            violation_event_id=event.event_id,
            violation_type=event.payload.get("violation_type", "unknown"),
        )
```

### Event Pattern

```python
# Band decreased event (auto-decay)
{
    "event_type": "constitutional.legitimacy.band_decreased",
    "actor": "system",
    "payload": {
        "from_band": "stable",
        "to_band": "strained",
        "severity": "minor",
        "violation_type": "task.timeout_without_decline",
        "violation_event_id": "uuid",
        "violation_count": 1,
        "transitioned_at": "2026-01-16T00:00:00Z"
    }
}

# Critical violation causing jump to COMPROMISED
{
    "event_type": "constitutional.legitimacy.band_decreased",
    "actor": "system",
    "payload": {
        "from_band": "stable",
        "to_band": "compromised",
        "severity": "critical",
        "violation_type": "task.unauthorized_creation",
        "violation_event_id": "uuid",
        "violation_count": 1,
        "transitioned_at": "2026-01-16T00:00:00Z"
    }
}

# Integrity violation causing immediate FAILED
{
    "event_type": "constitutional.legitimacy.band_decreased",
    "actor": "system",
    "payload": {
        "from_band": "eroding",
        "to_band": "failed",
        "severity": "integrity",
        "violation_type": "chain.discontinuity",
        "violation_event_id": "uuid",
        "violation_count": 5,
        "transitioned_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestLegitimacyDecayService:
    """Unit tests for automatic legitimacy decay."""

    async def test_minor_violation_drops_one_band(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
    ):
        """Minor violation drops 1 band."""
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        assert result.current_band == LegitimacyBand.STRAINED
        assert result.violation_count == stable_state.violation_count + 1

    async def test_major_violation_drops_two_bands(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
    ):
        """Major violation drops 2 bands."""
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        assert result.current_band == LegitimacyBand.ERODING

    async def test_critical_violation_jumps_to_compromised(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
    ):
        """Critical violation jumps directly to COMPROMISED."""
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.unauthorized_creation",
        )

        assert result.current_band == LegitimacyBand.COMPROMISED

    async def test_integrity_violation_immediate_failed(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
    ):
        """Integrity violation causes immediate FAILED."""
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="chain.discontinuity",
        )

        assert result.current_band == LegitimacyBand.FAILED

    async def test_violation_count_accumulates(
        self,
        decay_service: LegitimacyDecayService,
        strained_state: LegitimacyState,
    ):
        """Violation count accumulates across transitions."""
        # First violation
        result1 = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        # Second violation
        result2 = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="task.timeout_without_decline",
        )

        assert result2.violation_count == result1.violation_count + 1

    async def test_transition_includes_triggering_event(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
        transition_capture: TransitionCapture,
    ):
        """Transition record includes triggering event ID."""
        violation_id = uuid4()

        await decay_service.process_violation(
            violation_event_id=violation_id,
            violation_type="coercion.filter_blocked",
        )

        transition = transition_capture.get_last()
        assert transition.triggering_event_id == violation_id

    async def test_band_decreased_event_emitted(
        self,
        decay_service: LegitimacyDecayService,
        stable_state: LegitimacyState,
        event_capture: EventCapture,
    ):
        """Band decreased event is emitted."""
        await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="coercion.filter_blocked",
        )

        event = event_capture.get_last("constitutional.legitimacy.band_decreased")
        assert event is not None
        assert event.payload["from_band"] == "stable"
        assert event.payload["to_band"] == "eroding"
        assert event.payload["severity"] == "major"

    async def test_failed_state_is_terminal(
        self,
        decay_service: LegitimacyDecayService,
        failed_state: LegitimacyState,
    ):
        """FAILED state does not change on further violations."""
        result = await decay_service.process_violation(
            violation_event_id=uuid4(),
            violation_type="chain.discontinuity",
        )

        # State unchanged (already terminal)
        assert result.current_band == LegitimacyBand.FAILED


class TestViolationSeverityMapping:
    """Unit tests for violation severity mapping."""

    def test_all_defined_violations_have_severity(self):
        """All defined violation types have severity mapping."""
        for violation_type in VIOLATION_SEVERITY_MAP:
            assert VIOLATION_SEVERITY_MAP[violation_type] in ViolationSeverity

    def test_unknown_violation_defaults_to_minor(self):
        """Unknown violation types default to MINOR severity."""
        severity = VIOLATION_SEVERITY_MAP.get(
            "unknown.violation.type",
            ViolationSeverity.MINOR,
        )
        assert severity == ViolationSeverity.MINOR
```

### Dependencies

- **Depends on:** consent-gov-5-1 (legitimacy band domain model)
- **Enables:** consent-gov-5-3 (explicit upward transitions)

### References

- FR29: System can auto-transition legitimacy downward based on violation events
- NFR-AUDIT-04: Transition includes triggering event reference
- NFR-CONST-04: All transitions logged with timestamp, actor, reason
