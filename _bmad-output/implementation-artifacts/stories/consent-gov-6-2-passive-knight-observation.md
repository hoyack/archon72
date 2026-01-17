# Story consent-gov-6.2: Passive Knight Observation

Status: done

---

## Story

As a **Knight**,
I want **passive observation via event subscription**,
So that **I see all branch actions without active intervention**.

---

## Acceptance Criteria

1. **AC1:** Event bus subscription for real-time observation
2. **AC2:** Ledger replay as verification backstop
3. **AC3:** Events observable within ≤1 second (NFR-OBS-01)
4. **AC4:** All branch actions logged with sufficient detail (NFR-AUDIT-01)
5. **AC5:** Knight can observe Prince Panel conduct (FR41)
6. **AC6:** No active notification from services (loose coupling)
7. **AC7:** Gap detection via hash chain continuity
8. **AC8:** Dual-path observation: bus (fast) + ledger (resilient)
9. **AC9:** Unit tests for observation mechanics

---

## Tasks / Subtasks

- [x] **Task 1: Create KnightObserverService** (AC: 1, 6)
  - [x] Create `src/application/services/governance/knight_observer_service.py`
  - [x] Ledger-based polling (passive) - architecture uses ledger not event bus
  - [x] Services write to ledger; Knight polls ledger (not called explicitly)
  - [x] Loose coupling maintained

- [x] **Task 2: Implement ledger polling** (AC: 1, 3)
  - [x] Poll all governance events from ledger
  - [x] All branch prefixes supported: executive, judicial, constitutional, etc.
  - [x] Process events within 1 second latency target
  - [x] Configurable batch size and poll interval

- [x] **Task 3: Implement position tracking** (AC: 2, 8)
  - [x] Track last observed sequence number
  - [x] Resume from specific sequence on restart
  - [x] Idempotent observation (skip already-observed events)
  - [x] Position tracking ensures no events missed

- [x] **Task 4: Implement gap detection** (AC: 7)
  - [x] Track expected sequence numbers
  - [x] Detect discontinuities in sequence
  - [x] Create witness statement for gaps (HASH_CHAIN_GAP type)
  - [x] Gap callback registration for external handling

- [x] **Task 5: Implement observation recording** (AC: 4)
  - [x] Create witness statement for each observed event
  - [x] Use WitnessStatementFactory (from 6-1)
  - [x] Include sufficient detail for audit (event_type, sequence, actor)
  - [x] Record to WitnessPort (append-only)

- [x] **Task 6: Implement panel observation** (AC: 5)
  - [x] Handle `judicial.panel.*` events specially
  - [x] Observe panel convening, deliberation, findings
  - [x] Knight watches the watchers (checks and balances)
  - [x] Record panel conduct observations with descriptive what field

- [x] **Task 7: Implement observation loop** (AC: 8)
  - [x] Primary: ledger polling (fast, configurable interval)
  - [x] Position tracking for resilience
  - [x] Async start/stop for lifecycle management
  - [x] Error handling in observation loop

- [x] **Task 8: Implement latency monitoring** (AC: 3)
  - [x] Track time from event timestamp to observation time
  - [x] Log warning if exceeds 1 second threshold
  - [x] Track latency violation count
  - [x] No action fails due to latency (observation-only)

- [x] **Task 9: Write comprehensive unit tests** (AC: 9)
  - [x] Test ledger polling receives events (35 tests)
  - [x] Test position tracking works
  - [x] Test gap detection
  - [x] Test latency within target
  - [x] Test panel observation (FR41)
  - [x] Test loose coupling design

---

## Documentation Checklist

- [ ] Architecture docs updated (observation pattern)
- [ ] Operations runbook for Knight health monitoring
- [ ] Inline comments explaining passive pattern
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Passive vs Active Observation:**
```
Active (REJECTED):
  - Services call Knight explicitly
  - Tight coupling
  - Service must know Knight exists
  - Service can choose not to call → suppression

Passive (ACCEPTED):
  - Services publish events
  - Knight subscribes
  - Loose coupling
  - Service doesn't know who's listening
  - Cannot suppress what you don't control
```

**Why Dual-Path (Bus + Ledger)?**
```
Event Bus:
  ✓ Fast (real-time)
  ✗ Unreliable (network, process restarts)

Ledger Poll:
  ✓ Reliable (persisted)
  ✗ Slower (polling interval)

Combined:
  ✓ Fast when healthy (bus)
  ✓ Complete when degraded (ledger)
  ✓ Gap detection between them

If bus misses event:
  - Ledger poll catches it
  - Gap is detectable and logged
  - No observation is lost
```

**NFR-OBS-01 Compliance:**
```
Requirement: Knight observes all branch actions ≤1 second

Implementation:
  - Event bus subscription is sub-second
  - Ledger poll interval is fallback (not primary)
  - Latency monitoring ensures compliance
  - Alert if target exceeded (but don't fail)

Note: Observation is best-effort for latency, guaranteed for completeness
```

### Service Implementation Sketch

```python
class KnightObserverService:
    """Passive observation service for Knight witness.

    Subscribes to event bus (fast path).
    Falls back to ledger poll (resilient path).
    """

    def __init__(
        self,
        event_bus: EventBusPort,
        ledger: LedgerPort,
        witness_port: WitnessPort,
        statement_factory: WitnessStatementFactory,
        time_authority: TimeAuthority,
    ):
        self._bus = event_bus
        self._ledger = ledger
        self._witness = witness_port
        self._factory = statement_factory
        self._time = time_authority

        # Tracking
        self._last_observed_position = 0
        self._bus_active = True

    async def start(self) -> None:
        """Start observation (subscribe to bus, start ledger poll)."""
        # Primary: event bus subscription
        await self._subscribe_to_events()

        # Secondary: periodic ledger poll
        asyncio.create_task(self._ledger_poll_loop())

    async def _subscribe_to_events(self) -> None:
        """Subscribe to all governance events."""
        patterns = [
            "governance.*",
            "constitutional.*",
            "executive.*",
            "judicial.*",
            "administrative.*",
        ]

        for pattern in patterns:
            await self._bus.subscribe(
                pattern=pattern,
                handler=self._handle_event,
            )

    async def _handle_event(self, event: Event) -> None:
        """Handle observed event (bus path)."""
        observed_at = self._time.now()
        latency_ms = (observed_at - event.timestamp).total_seconds() * 1000

        # Log latency
        if latency_ms > 1000:  # >1 second
            logger.warning(f"Observation latency {latency_ms}ms exceeds 1s target")

        # Create witness statement
        statement = self._factory.create_statement(
            observation_type=self._classify_event(event),
            observed_event=event,
            what=self._describe_event(event),
            where=self._determine_branch(event),
        )

        # Record to ledger
        await self._witness.record_statement(statement)

        # Update tracking
        if event.sequence_number:
            self._check_for_gap(event.sequence_number)
            self._last_observed_position = event.sequence_number

    async def _ledger_poll_loop(self) -> None:
        """Periodic ledger poll for missed events."""
        while True:
            try:
                await asyncio.sleep(10)  # 10 second interval

                # Get events since last position
                events = await self._ledger.get_events_since(
                    self._last_observed_position
                )

                for event in events:
                    if not await self._already_observed(event):
                        logger.info(f"Ledger catchup: {event.event_id}")
                        await self._handle_event(event)

            except Exception as e:
                logger.error(f"Ledger poll failed: {e}")

    def _check_for_gap(self, position: int) -> None:
        """Check for gap in sequence."""
        expected = self._last_observed_position + 1

        if position > expected:
            missing = position - expected
            logger.warning(f"Gap detected: {missing} events missing")

            # Emit gap detection event
            asyncio.create_task(
                self._emit_gap_event(expected, position, missing)
            )

    async def _emit_gap_event(
        self,
        expected: int,
        actual: int,
        missing: int,
    ) -> None:
        """Emit gap detection event."""
        await self._witness.record_statement(
            self._factory.create_statement(
                observation_type=ObservationType.HASH_CHAIN_GAP,
                observed_event=Event(
                    event_id=uuid4(),
                    event_type="internal.gap_detection",
                    actor="knight",
                    timestamp=self._time.now(),
                ),
                what=f"Expected position {expected}, received {actual}, missing {missing} events",
                where="witness.observation",
            )
        )

    def _classify_event(self, event: Event) -> ObservationType:
        """Classify event for observation type."""
        if "violation" in event.event_type:
            return ObservationType.POTENTIAL_VIOLATION

        if event.event_type.startswith("judicial.panel"):
            return ObservationType.BRANCH_ACTION  # Panel actions

        return ObservationType.BRANCH_ACTION

    def _describe_event(self, event: Event) -> str:
        """Create factual description of event."""
        return f"Event {event.event_type} by {event.actor}"

    def _determine_branch(self, event: Event) -> str:
        """Determine which branch the event belongs to."""
        if event.event_type.startswith("executive"):
            return "executive"
        if event.event_type.startswith("judicial"):
            return "judicial"
        if event.event_type.startswith("constitutional"):
            return "constitutional"
        return "governance"

    async def _already_observed(self, event: Event) -> bool:
        """Check if event was already observed via bus."""
        statements = await self._witness.get_statements_for_event(event.event_id)
        return len(statements) > 0
```

### Panel Observation Pattern

```python
class PanelObserver:
    """Observer for Prince Panel conduct (FR41)."""

    PANEL_EVENT_PATTERNS = [
        "judicial.panel.convened",
        "judicial.panel.deliberation_started",
        "judicial.panel.member_recused",
        "judicial.panel.finding_proposed",
        "judicial.panel.vote_recorded",
        "judicial.panel.finding_issued",
        "judicial.panel.dissent_recorded",
    ]

    async def observe_panel_event(self, event: Event) -> WitnessStatement:
        """Create observation of panel conduct."""
        return self._factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=event,
            what=self._describe_panel_event(event),
            where="judicial.prince_panel",
        )

    def _describe_panel_event(self, event: Event) -> str:
        """Factual description of panel event."""
        descriptions = {
            "judicial.panel.convened": "Panel convened with members",
            "judicial.panel.deliberation_started": "Deliberation began",
            "judicial.panel.member_recused": "Member recused from panel",
            "judicial.panel.finding_proposed": "Finding proposed for vote",
            "judicial.panel.vote_recorded": "Vote recorded by member",
            "judicial.panel.finding_issued": "Formal finding issued",
            "judicial.panel.dissent_recorded": "Dissent recorded in finding",
        }
        return descriptions.get(event.event_type, f"Panel event: {event.event_type}")
```

### Test Patterns

```python
class TestKnightObserverService:
    """Unit tests for Knight observation service."""

    async def test_bus_subscription_receives_events(
        self,
        observer: KnightObserverService,
        event_bus: FakeEventBus,
        witness_port: FakeWitnessPort,
    ):
        """Events on bus are observed."""
        await observer.start()

        test_event = Event(
            event_id=uuid4(),
            event_type="executive.task.activated",
            actor="earl",
            timestamp=datetime.now(UTC),
        )

        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)  # Allow processing

        statements = await witness_port.get_statements_for_event(test_event.event_id)
        assert len(statements) == 1

    async def test_ledger_fallback_catches_missed(
        self,
        observer: KnightObserverService,
        event_bus: FakeEventBus,
        ledger: FakeLedger,
        witness_port: FakeWitnessPort,
    ):
        """Ledger poll catches events missed by bus."""
        await observer.start()

        # Simulate bus failure (event not delivered)
        test_event = Event(
            event_id=uuid4(),
            event_type="executive.task.activated",
            actor="earl",
            timestamp=datetime.now(UTC),
            sequence_number=100,
        )

        # Add to ledger but not bus
        await ledger.append(test_event)

        # Wait for ledger poll
        await asyncio.sleep(15)

        statements = await witness_port.get_statements_for_event(test_event.event_id)
        assert len(statements) == 1

    async def test_gap_detection(
        self,
        observer: KnightObserverService,
        event_bus: FakeEventBus,
        witness_port: FakeWitnessPort,
    ):
        """Gaps in sequence are detected."""
        await observer.start()

        # First event at position 1
        event1 = Event(
            event_id=uuid4(),
            event_type="test.event",
            actor="test",
            timestamp=datetime.now(UTC),
            sequence_number=1,
        )
        await event_bus.publish(event1)
        await asyncio.sleep(0.1)

        # Skip to position 5 (missing 2, 3, 4)
        event5 = Event(
            event_id=uuid4(),
            event_type="test.event",
            actor="test",
            timestamp=datetime.now(UTC),
            sequence_number=5,
        )
        await event_bus.publish(event5)
        await asyncio.sleep(0.1)

        # Check for gap detection statement
        all_statements = await witness_port.get_all_statements()
        gap_statements = [
            s for s in all_statements
            if s.observation_type == ObservationType.HASH_CHAIN_GAP
        ]
        assert len(gap_statements) == 1

    async def test_latency_within_target(
        self,
        observer: KnightObserverService,
        event_bus: FakeEventBus,
        time_authority: FakeTimeAuthority,
    ):
        """Observation latency is within 1 second."""
        await observer.start()

        event_time = time_authority.now()
        test_event = Event(
            event_id=uuid4(),
            event_type="test.event",
            actor="test",
            timestamp=event_time,
        )

        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)

        # Observation should be nearly instant
        observed_time = time_authority.now()
        latency_ms = (observed_time - event_time).total_seconds() * 1000

        assert latency_ms < 1000  # <1 second

    async def test_panel_events_observed(
        self,
        observer: KnightObserverService,
        event_bus: FakeEventBus,
        witness_port: FakeWitnessPort,
    ):
        """Panel conduct events are observed."""
        await observer.start()

        panel_event = Event(
            event_id=uuid4(),
            event_type="judicial.panel.finding_issued",
            actor="prince-panel",
            timestamp=datetime.now(UTC),
        )

        await event_bus.publish(panel_event)
        await asyncio.sleep(0.1)

        statements = await witness_port.get_statements_for_event(panel_event.event_id)
        assert len(statements) == 1
        assert "judicial.prince_panel" in statements[0].content.where
```

### Dependencies

- **Depends on:** consent-gov-6-1 (witness domain model), consent-gov-1-1 (event infrastructure)
- **Enables:** consent-gov-6-3 (statement routing)

### References

- FR33: Knight can observe and record violations across all branches
- FR41: Knight can observe Prince Panel conduct
- NFR-OBS-01: Knight observes all branch actions within ≤1 second
- NFR-AUDIT-01: All branch actions logged with sufficient detail
- AD-16: Knight Observation Pattern (passive subscription)
