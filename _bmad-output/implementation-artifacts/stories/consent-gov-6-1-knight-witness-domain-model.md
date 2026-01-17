# Story consent-gov-6.1: Knight Witness Domain Model

Status: ready-for-dev

---

## Story

As a **governance system**,
I want **a Knight witness capability**,
So that **violations can be observed and recorded neutrally**.

---

## Acceptance Criteria

1. **AC1:** Knight can observe all branch actions (FR33)
2. **AC2:** Knight observes but does not judge or enforce
3. **AC3:** Witness statements are observation only, no judgment (FR34)
4. **AC4:** Statements cannot be suppressed by any role (NFR-CONST-07)
5. **AC5:** Witness statement includes observed event reference
6. **AC6:** Statement includes observation timestamp
7. **AC7:** Statement includes factual observation content
8. **AC8:** No interpretation or recommendation in statement
9. **AC9:** Unit tests for witness statement creation

---

## Tasks / Subtasks

- [ ] **Task 1: Create witness domain package** (AC: 1, 2)
  - [ ] Create `src/domain/governance/witness/__init__.py`
  - [ ] Create `src/domain/governance/witness/witness_statement.py`
  - [ ] Define Knight's role boundaries
  - [ ] Document observation-only semantics

- [ ] **Task 2: Create WitnessStatement domain model** (AC: 3, 5, 6, 7, 8)
  - [ ] Define immutable value object
  - [ ] Include statement_id, observed_event_id, observed_at
  - [ ] Include factual observation content
  - [ ] Prevent judgment/recommendation fields

- [ ] **Task 3: Create ObservationType enum** (AC: 1, 3)
  - [ ] BRANCH_ACTION: Normal branch operation observed
  - [ ] POTENTIAL_VIOLATION: Pattern matching violation indicators
  - [ ] TIMING_ANOMALY: Unexpected timing detected
  - [ ] HASH_CHAIN_GAP: Missing expected event
  - [ ] All types are observations, not judgments

- [ ] **Task 4: Create WitnessStatementFactory** (AC: 3, 7, 8)
  - [ ] Factory method for statement creation
  - [ ] Validate observation content (no judgment language)
  - [ ] Enforce structure compliance
  - [ ] Reject invalid statement attempts

- [ ] **Task 5: Implement suppression prevention** (AC: 4)
  - [ ] Statement emission BEFORE state commit (two-phase)
  - [ ] No deletion method on statement
  - [ ] No modification method on statement
  - [ ] Hash chain gap detection for missing statements

- [ ] **Task 6: Create WitnessPort interface** (AC: 1, 4)
  - [ ] Create `src/application/ports/governance/witness_port.py`
  - [ ] Define `record_statement()` method
  - [ ] Define `get_statements_for_event()` method
  - [ ] No `delete_statement()` or `modify_statement()` methods

- [ ] **Task 7: Define observation content structure** (AC: 7, 8)
  - [ ] Factual fields: what, when, who (actor), where (component)
  - [ ] No fields for: why, should, recommendation
  - [ ] Structured for machine readability
  - [ ] Human readable summary optional

- [ ] **Task 8: Write comprehensive unit tests** (AC: 9)
  - [ ] Test statement creation with valid observation
  - [ ] Test statement immutability
  - [ ] Test no judgment fields allowed
  - [ ] Test no suppression methods exist
  - [ ] Test all observation types
  - [ ] Test factory validation

---

## Documentation Checklist

- [ ] Architecture docs updated (Knight role)
- [ ] Inline comments explaining observation-only principle
- [ ] Knight boundaries documented
- [ ] N/A - README (internal component)

---

## Dev Notes

### Key Architectural Decisions

**Knight's Role: Observer, Not Judge**
```
What Knight DOES:
  - Observes all branch actions
  - Records factual observations
  - Detects timing anomalies
  - Detects hash chain gaps
  - Routes statements to Prince Panel queue

What Knight does NOT do:
  - Make judgments about violations
  - Recommend remedies
  - Enforce rules
  - Block actions

The Knight is analogous to a court reporter:
  - Records everything accurately
  - Does not interrupt proceedings
  - Does not offer opinions
  - Provides transcript for others to judge
```

**Why Observation-Only?**
```
Separation of witness and judicial powers:
  - Observer who judges is a conflict of interest
  - Observation must be neutral to be trusted
  - Judgment requires deliberation (panels)
  - Knight's value is in completeness, not interpretation

If Knight could judge:
  - Knight becomes a single point of failure
  - Knight's biases affect all outcomes
  - No appeal possible from Knight judgment
  - Separation of powers violated
```

**Suppression Prevention:**
```
NFR-CONST-07: Statements cannot be suppressed

Mechanisms:
1. Two-phase emission: intent → observation → commit
   - Observation emitted BEFORE state changes
   - If action fails, observation still recorded

2. Immutable statements:
   - No delete method exists
   - No modify method exists
   - Append-only ledger enforces this

3. Gap detection:
   - Hash chain reveals missing statements
   - Gap itself becomes violation evidence
   - Knight has dual path: bus + ledger poll
```

### Domain Models

```python
class ObservationType(Enum):
    """Type of observation recorded by Knight."""

    BRANCH_ACTION = "branch_action"
    """Normal branch operation observed."""

    POTENTIAL_VIOLATION = "potential_violation"
    """Pattern matching violation indicators detected."""

    TIMING_ANOMALY = "timing_anomaly"
    """Unexpected timing deviation detected."""

    HASH_CHAIN_GAP = "hash_chain_gap"
    """Missing expected event in sequence."""


@dataclass(frozen=True)
class ObservationContent:
    """Factual observation content (no judgment).

    Structure enforces observation-only:
    - what: factual description
    - when: timestamp
    - who: actor(s) involved
    - where: component/branch

    Explicitly excluded (not even optional):
    - why: interpretation
    - should: recommendation
    - severity: judgment
    """
    what: str  # Factual description
    when: datetime  # Observation timestamp
    who: list[str]  # Actor IDs involved
    where: str  # Component/branch identifier
    event_type: str  # Observed event type
    event_id: UUID  # Reference to observed event

    # Computed field for readability
    @property
    def summary(self) -> str:
        """Human-readable summary (still factual)."""
        return f"At {self.when.isoformat()}, {self.event_type} observed in {self.where}"


@dataclass(frozen=True)
class WitnessStatement:
    """Immutable witness statement from Knight.

    Represents a neutral observation of governance activity.
    Contains facts only - no judgment, no recommendation.

    Cannot be modified or deleted once created.
    """
    statement_id: UUID
    observation_type: ObservationType
    content: ObservationContent
    observed_at: datetime  # When Knight observed (may differ from event time)
    hash_chain_position: int  # Position in statement chain

    # No judgment fields - intentionally omitted:
    # - severity (that's judgment)
    # - recommendation (that's advice)
    # - violation (that's conclusion)
    # - remedy (that's prescription)


class WitnessStatementFactory:
    """Factory for creating valid witness statements.

    Enforces observation-only content.
    """

    # Banned words indicating judgment
    JUDGMENT_INDICATORS = {
        "should", "must", "recommend", "suggests",
        "violated", "guilty", "innocent", "fault",
        "severe", "minor", "critical",  # Severity words
        "remedy", "punishment", "consequence",  # Prescription words
    }

    def __init__(self, time_authority: TimeAuthority):
        self._time = time_authority
        self._position_counter = 0

    def create_statement(
        self,
        observation_type: ObservationType,
        observed_event: Event,
        what: str,
        where: str,
    ) -> WitnessStatement:
        """Create a witness statement.

        Validates that content is observation-only (no judgment).
        """
        # Validate no judgment language
        self._validate_no_judgment(what)

        now = self._time.now()
        self._position_counter += 1

        return WitnessStatement(
            statement_id=uuid4(),
            observation_type=observation_type,
            content=ObservationContent(
                what=what,
                when=observed_event.timestamp,
                who=[observed_event.actor],
                where=where,
                event_type=observed_event.event_type,
                event_id=observed_event.event_id,
            ),
            observed_at=now,
            hash_chain_position=self._position_counter,
        )

    def _validate_no_judgment(self, content: str) -> None:
        """Validate content contains no judgment language."""
        lower_content = content.lower()
        for indicator in self.JUDGMENT_INDICATORS:
            if indicator in lower_content:
                raise JudgmentLanguageError(
                    f"Statement contains judgment indicator '{indicator}'. "
                    f"Knight statements must be observation-only."
                )


class JudgmentLanguageError(ValueError):
    """Raised when witness statement contains judgment language."""
    pass
```

### Port Interface

```python
class WitnessPort(Protocol):
    """Port for witness statement operations.

    Note: Intentionally NO delete or modify methods.
    Statements are append-only by design (NFR-CONST-07).
    """

    async def record_statement(
        self,
        statement: WitnessStatement,
    ) -> None:
        """Record witness statement to append-only ledger.

        Once recorded, statement cannot be deleted or modified.
        """
        ...

    async def get_statements_for_event(
        self,
        event_id: UUID,
    ) -> list[WitnessStatement]:
        """Get all witness statements for an event."""
        ...

    async def get_statements_by_type(
        self,
        observation_type: ObservationType,
        since: datetime | None = None,
    ) -> list[WitnessStatement]:
        """Get statements by observation type."""
        ...

    async def get_statement_chain(
        self,
        start_position: int,
        end_position: int,
    ) -> list[WitnessStatement]:
        """Get statements by chain position for gap detection."""
        ...

    # Explicitly NOT defined:
    # - delete_statement()  # Suppression not allowed
    # - modify_statement()  # Immutability enforced
```

### Event Pattern

```python
# Witness statement recorded event
{
    "event_type": "judicial.witness.statement_recorded",
    "actor": "knight",
    "payload": {
        "statement_id": "uuid",
        "observation_type": "potential_violation",
        "observed_event_id": "uuid",
        "observed_event_type": "task.consent_bypassed",
        "what": "Task activated without explicit consent from Cluster",
        "where": "executive.task_coordination",
        "observed_at": "2026-01-16T00:00:00Z",
        "hash_chain_position": 1234
    }
}

# Hash chain gap detected (Knight observes own chain)
{
    "event_type": "judicial.witness.gap_detected",
    "actor": "knight",
    "payload": {
        "expected_position": 1233,
        "actual_position": 1235,
        "missing_count": 1,
        "detected_at": "2026-01-16T00:00:00Z"
    }
}
```

### Test Patterns

```python
class TestWitnessStatement:
    """Unit tests for witness statement domain model."""

    def test_statement_is_immutable(self):
        """Statements cannot be modified after creation."""
        statement = create_test_statement()

        with pytest.raises(FrozenInstanceError):
            statement.content = "modified"

    def test_statement_has_no_judgment_fields(self):
        """Statement structure excludes judgment fields."""
        statement = create_test_statement()

        # These should not exist
        assert not hasattr(statement, "severity")
        assert not hasattr(statement, "recommendation")
        assert not hasattr(statement, "violation")
        assert not hasattr(statement, "remedy")

    def test_observation_content_is_factual(self):
        """Observation content structure is factual only."""
        content = ObservationContent(
            what="Task activated without explicit consent",
            when=datetime.now(UTC),
            who=["actor-uuid"],
            where="executive.task_coordination",
            event_type="task.activated",
            event_id=uuid4(),
        )

        # Factual fields present
        assert content.what
        assert content.when
        assert content.who
        assert content.where

        # No judgment fields (they don't exist in the class)
        assert not hasattr(content, "why")
        assert not hasattr(content, "should")
        assert not hasattr(content, "severity")


class TestWitnessStatementFactory:
    """Unit tests for statement factory."""

    def test_factory_creates_valid_statement(
        self,
        factory: WitnessStatementFactory,
        observed_event: Event,
    ):
        """Factory creates valid observation statement."""
        statement = factory.create_statement(
            observation_type=ObservationType.BRANCH_ACTION,
            observed_event=observed_event,
            what="Task state changed from AUTHORIZED to ACTIVATED",
            where="executive.task_coordination",
        )

        assert statement.observation_type == ObservationType.BRANCH_ACTION
        assert statement.content.event_id == observed_event.event_id

    def test_factory_rejects_judgment_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: Event,
    ):
        """Factory rejects statements with judgment language."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="This should not have happened",  # "should" = judgment
                where="executive",
            )

    def test_factory_rejects_severity_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: Event,
    ):
        """Factory rejects severity descriptors (judgment)."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Severe violation of consent protocol",  # "severe" = judgment
                where="executive",
            )

    def test_factory_rejects_recommendation_language(
        self,
        factory: WitnessStatementFactory,
        observed_event: Event,
    ):
        """Factory rejects recommendation language."""
        with pytest.raises(JudgmentLanguageError):
            factory.create_statement(
                observation_type=ObservationType.POTENTIAL_VIOLATION,
                observed_event=observed_event,
                what="Recommend immediate halt",  # "recommend" = judgment
                where="executive",
            )


class TestWitnessPort:
    """Unit tests for witness port interface."""

    def test_port_has_no_delete_method(self):
        """Port interface has no delete method (suppression prevention)."""
        # This is a structural test of the protocol
        assert not hasattr(WitnessPort, "delete_statement")

    def test_port_has_no_modify_method(self):
        """Port interface has no modify method (immutability)."""
        assert not hasattr(WitnessPort, "modify_statement")

    async def test_record_statement_persists(
        self,
        witness_port: WitnessPort,
        statement: WitnessStatement,
    ):
        """Recorded statements are persisted."""
        await witness_port.record_statement(statement)

        retrieved = await witness_port.get_statements_for_event(
            statement.content.event_id
        )

        assert statement in retrieved


class TestObservationType:
    """Unit tests for observation type enum."""

    def test_all_types_are_observations(self):
        """All observation types are neutral observations."""
        # None of these should imply judgment
        neutral_types = [
            ObservationType.BRANCH_ACTION,
            ObservationType.POTENTIAL_VIOLATION,  # "potential" = observation
            ObservationType.TIMING_ANOMALY,
            ObservationType.HASH_CHAIN_GAP,
        ]

        for obs_type in ObservationType:
            assert obs_type in neutral_types
            # Type names don't include judgment words
            assert "guilty" not in obs_type.value
            assert "innocent" not in obs_type.value
            assert "fault" not in obs_type.value
```

### Dependencies

- **Depends on:** consent-gov-1-1 (event infrastructure)
- **Enables:** consent-gov-6-2 (passive observation), consent-gov-6-3 (statement routing)

### References

- FR33: Knight can observe and record violations across all branches
- FR34: Knight can publish witness statements (observation only, no judgment)
- NFR-CONST-07: Witness statements cannot be suppressed by any role
- AD-16: Knight Observation Pattern (passive subscription)
