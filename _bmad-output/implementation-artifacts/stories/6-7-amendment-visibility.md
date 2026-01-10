# Story 6.7: Amendment Visibility (FR126-FR128)

Status: done

## Story

As an **external observer**,
I want 14 days visibility before amendment votes,
So that I can review proposed changes.

## Acceptance Criteria

### AC1: 14-Day Visibility Period (FR126)
**Given** an amendment is proposed
**When** it is submitted
**Then** it must be public for 14 days before vote
**And** vote is blocked if visibility period incomplete
**And** an `AmendmentProposedEvent` is created with `visible_from` timestamp

### AC2: Vote Blocking Enforcement (FR126)
**Given** an amendment with visibility period incomplete
**When** a vote is attempted
**Then** the vote is rejected
**And** error includes "FR126: Amendment visibility period incomplete - {days_remaining} days remaining"
**And** rejection is logged as witnessed event

### AC3: Impact Analysis Requirement (FR127)
**Given** a core guarantee amendment
**When** proposed
**Then** impact analysis is required
**And** analysis MUST answer: "reduces visibility?", "raises silence probability?", "weakens irreversibility?"
**And** analysis is attached to `AmendmentProposedEvent`
**And** missing analysis blocks submission

### AC4: Amendment History Protection (FR128)
**Given** amendment history protection
**When** an amendment to hide previous amendments is proposed
**Then** it is rejected
**And** error includes "FR128: Amendment history cannot be made unreviewable"
**And** rejection logged as witnessed event

### AC5: Amendment Visibility Query (FR126)
**Given** an observer queries amendments
**When** the query is executed
**Then** all pending amendments are returned with:
  - Amendment ID
  - Proposed timestamp
  - Visible from timestamp
  - Days until votable
  - Impact analysis (if core guarantee)
  - Proposer attribution

## Tasks / Subtasks

- [x] Task 1: Create Amendment Domain Events (AC: #1, #5)
  - [ ] 1.1 Create `src/domain/events/amendment.py`:
    - `AmendmentProposedEventPayload` frozen dataclass with:
      - `amendment_id: str` - Unique amendment identifier
      - `amendment_type: AmendmentType` - Constitutional tier (Tier 2 or Tier 3)
      - `title: str` - Brief description
      - `summary: str` - Full amendment text/summary
      - `proposed_at: datetime` - Submission timestamp
      - `visible_from: datetime` - When visibility period started (same as proposed_at)
      - `votable_from: datetime` - 14 days after visible_from (FR126)
      - `proposer_id: str` - Who submitted (attribution)
      - `is_core_guarantee: bool` - Triggers FR127 impact analysis
      - `impact_analysis: AmendmentImpactAnalysis | None` - Required if core guarantee
      - `affected_guarantees: tuple[str, ...]` - What constitutional guarantees are affected
    - `AmendmentType` enum: TIER_2_CONSTITUTIONAL, TIER_3_CONVENTION
    - Event type constant: `AMENDMENT_PROPOSED_EVENT_TYPE = "amendment.proposed"`
    - `to_dict()` for event serialization
    - `signable_content()` for witnessing (CT-12)
  - [ ] 1.2 Create `AmendmentImpactAnalysis` frozen dataclass:
    - `reduces_visibility: bool` - FR127 question 1
    - `raises_silence_probability: bool` - FR127 question 2
    - `weakens_irreversibility: bool` - FR127 question 3
    - `analysis_text: str` - Human-readable explanation
    - `analyzed_by: str` - Attribution
    - `analyzed_at: datetime`
  - [ ] 1.3 Create `AmendmentVoteBlockedEventPayload` frozen dataclass:
    - `amendment_id: str`
    - `blocked_reason: str`
    - `days_remaining: int`
    - `votable_from: datetime`
    - `blocked_at: datetime`
  - [ ] 1.4 Create `AmendmentRejectedEventPayload` frozen dataclass:
    - `amendment_id: str`
    - `rejection_reason: str` - FR128 or other
    - `rejected_at: datetime`
  - [ ] 1.5 Export from `src/domain/events/__init__.py`

- [x] Task 2: Create Amendment Domain Errors (AC: #2, #3, #4)
  - [ ] 2.1 Create `src/domain/errors/amendment.py`:
    - `AmendmentError(ConstitutionalViolationError)` - Base class
    - `AmendmentVisibilityIncompleteError(AmendmentError)` - FR126
      - Attributes: `amendment_id: str`, `days_remaining: int`, `votable_from: datetime`
      - Message: "FR126: Amendment visibility period incomplete - {days_remaining} days remaining"
    - `AmendmentImpactAnalysisMissingError(AmendmentError)` - FR127
      - Attributes: `amendment_id: str`, `affected_guarantees: tuple[str, ...]`
      - Message: "FR127: Core guarantee amendment requires impact analysis"
    - `AmendmentHistoryProtectionError(AmendmentError)` - FR128
      - Attributes: `amendment_id: str`
      - Message: "FR128: Amendment history cannot be made unreviewable"
    - `AmendmentNotFoundError(AmendmentError)`
      - Attributes: `amendment_id: str`
      - Message: "Amendment {amendment_id} not found"
  - [ ] 2.2 Export from `src/domain/errors/__init__.py`

- [x] Task 3: Create Amendment Repository Port (AC: #1, #5)
  - [ ] 3.1 Create `src/application/ports/amendment_repository.py`:
    - `AmendmentRepositoryProtocol` ABC with methods:
      - `async def save_amendment(amendment: AmendmentProposal) -> None`
        - Persists amendment proposal
      - `async def get_amendment(amendment_id: str) -> AmendmentProposal | None`
        - Retrieves single amendment
      - `async def list_pending_amendments() -> list[AmendmentProposal]`
        - All amendments awaiting vote
      - `async def list_votable_amendments() -> list[AmendmentProposal]`
        - Amendments past 14-day visibility
      - `async def get_amendment_history() -> list[AmendmentProposal]`
        - All historical amendments for FR128 protection
      - `async def is_amendment_votable(amendment_id: str) -> tuple[bool, int]`
        - Returns (is_votable, days_remaining)
  - [ ] 3.2 Create `AmendmentProposal` frozen dataclass:
    - `amendment_id: str`
    - `amendment_type: AmendmentType`
    - `title: str`
    - `summary: str`
    - `proposed_at: datetime`
    - `visible_from: datetime`
    - `votable_from: datetime`
    - `proposer_id: str`
    - `is_core_guarantee: bool`
    - `impact_analysis: AmendmentImpactAnalysis | None`
    - `affected_guarantees: tuple[str, ...]`
    - `status: AmendmentStatus` - proposed, voting, approved, rejected
  - [ ] 3.3 Create `AmendmentStatus` enum: PROPOSED, VISIBILITY_PERIOD, VOTABLE, VOTING, APPROVED, REJECTED
  - [ ] 3.4 Export from `src/application/ports/__init__.py`

- [x] Task 4: Create Amendment Visibility Validator Port (AC: #2, #3, #4)
  - [ ] 4.1 Create `src/application/ports/amendment_visibility_validator.py`:
    - `AmendmentVisibilityValidatorProtocol` ABC with methods:
      - `async def validate_visibility_period(amendment_id: str) -> VisibilityValidationResult`
        - Checks if 14-day period complete (FR126)
      - `async def validate_impact_analysis(amendment: AmendmentProposal) -> ImpactValidationResult`
        - Checks if core guarantee amendment has analysis (FR127)
      - `async def validate_history_protection(amendment: AmendmentProposal) -> HistoryProtectionResult`
        - Checks if amendment would hide history (FR128)
      - `async def can_proceed_to_vote(amendment_id: str) -> tuple[bool, str]`
        - Comprehensive check combining all validations
    - `VisibilityValidationResult` dataclass:
      - `is_complete: bool`
      - `days_remaining: int`
      - `votable_from: datetime`
    - `ImpactValidationResult` dataclass:
      - `is_valid: bool`
      - `missing_fields: list[str]`
    - `HistoryProtectionResult` dataclass:
      - `is_valid: bool`
      - `violation_reason: str | None`
  - [ ] 4.2 Export from `src/application/ports/__init__.py`

- [x] Task 5: Create Amendment Visibility Service (AC: #1, #2, #3, #4, #5)
  - [ ] 5.1 Create `src/application/services/amendment_visibility_service.py`:
    - Inject: `HaltChecker`, `AmendmentRepositoryProtocol`, `AmendmentVisibilityValidatorProtocol`, `EventWriterService` (optional)
    - HALT CHECK FIRST at every operation boundary (CT-11)
  - [ ] 5.2 Implement `async def propose_amendment(proposal: AmendmentProposalRequest) -> AmendmentProposal`:
    - HALT CHECK FIRST (CT-11)
    - Validate not hiding history (FR128)
    - If core guarantee, require impact analysis (FR127)
    - Set votable_from = proposed_at + 14 days (FR126)
    - Save to repository
    - Create `AmendmentProposedEvent` with witness attribution
    - Return proposal
  - [ ] 5.3 Implement `async def check_vote_eligibility(amendment_id: str) -> VoteEligibilityResult`:
    - HALT CHECK FIRST (CT-11)
    - Check visibility period (FR126)
    - If not complete, create `AmendmentVoteBlockedEvent`
    - Return eligibility result with details
  - [ ] 5.4 Implement `async def validate_amendment_submission(proposal: AmendmentProposalRequest) -> list[str]`:
    - HALT CHECK FIRST (CT-11)
    - Check FR127 impact analysis if core guarantee
    - Check FR128 history protection
    - Return list of validation errors (empty if valid)
  - [ ] 5.5 Implement `async def get_pending_amendments() -> list[AmendmentSummary]`:
    - HALT CHECK FIRST (CT-11)
    - Query repository for pending
    - Calculate days_remaining for each
    - Return summary list for observers
  - [ ] 5.6 Implement `async def get_amendment_with_visibility_status(amendment_id: str) -> AmendmentWithStatus`:
    - HALT CHECK FIRST (CT-11)
    - Get amendment from repository
    - Calculate visibility status
    - Return with full context
  - [ ] 5.7 Implement history protection check:
    - `_contains_history_hiding_intent(summary: str, affected_guarantees: tuple[str, ...]) -> bool`
    - Check if amendment would hide/restrict access to previous amendments
    - Keywords: "unreviewable", "hide", "restrict access", "remove visibility"
  - [ ] 5.8 Export from `src/application/services/__init__.py`

- [x] Task 6: Create Infrastructure Stubs (AC: #1, #2, #3, #4, #5)
  - [ ] 6.1 Create `src/infrastructure/stubs/amendment_repository_stub.py`:
    - `AmendmentRepositoryStub` implementing `AmendmentRepositoryProtocol`
    - In-memory dict storage: `dict[str, AmendmentProposal]`
    - `inject_amendment(proposal: AmendmentProposal)` for test setup
    - `clear()` for test isolation
    - DEV MODE watermark warning on initialization
  - [ ] 6.2 Create `src/infrastructure/stubs/amendment_visibility_validator_stub.py`:
    - `AmendmentVisibilityValidatorStub` implementing `AmendmentVisibilityValidatorProtocol`
    - Configurable validation results for testing
    - `set_visibility_complete(amendment_id: str, complete: bool)` for test control
    - `set_history_protection_violation(amendment_id: str, violation: bool)` for test control
    - `clear()` for test isolation
  - [ ] 6.3 Export from `src/infrastructure/stubs/__init__.py`

- [x] Task 7: Write Unit Tests (AC: #1, #2, #3, #4, #5)
  - [ ] 7.1 Create `tests/unit/domain/test_amendment_events.py`:
    - Test `AmendmentProposedEventPayload` creation with all fields
    - Test `AmendmentType` enum values (TIER_2, TIER_3)
    - Test `to_dict()` returns expected structure
    - Test `signable_content()` determinism
    - Test `votable_from` calculation (14 days from visible_from)
    - Test `AmendmentImpactAnalysis` required fields
    - Test `AmendmentVoteBlockedEventPayload` creation
    - Test `AmendmentRejectedEventPayload` creation
  - [ ] 7.2 Create `tests/unit/domain/test_amendment_errors.py`:
    - Test `AmendmentVisibilityIncompleteError` message includes FR126 and days_remaining
    - Test `AmendmentImpactAnalysisMissingError` message includes FR127
    - Test `AmendmentHistoryProtectionError` message includes FR128
    - Test error inheritance hierarchy
  - [ ] 7.3 Create `tests/unit/application/test_amendment_visibility_service.py`:
    - Test `propose_amendment()` sets correct votable_from
    - Test `propose_amendment()` rejects history-hiding amendments (FR128)
    - Test `propose_amendment()` requires impact analysis for core guarantees (FR127)
    - Test `check_vote_eligibility()` blocks incomplete visibility (FR126)
    - Test `check_vote_eligibility()` allows complete visibility
    - Test `get_pending_amendments()` returns correct list
    - Test HALT CHECK on all operations
  - [ ] 7.4 Create `tests/unit/infrastructure/test_amendment_repository_stub.py`:
    - Test stub save and retrieve
    - Test list_pending_amendments
    - Test list_votable_amendments filtering
    - Test `inject_amendment()` for test setup
    - Test `clear()` method
  - [ ] 7.5 Create `tests/unit/infrastructure/test_amendment_visibility_validator_stub.py`:
    - Test configurable validation results
    - Test `clear()` method

- [x] Task 8: Write Integration Tests (AC: #1, #2, #3, #4, #5)
  - [ ] 8.1 Create `tests/integration/test_amendment_visibility_integration.py`:
    - Test: `test_fr126_14_day_visibility_enforced` (AC1)
      - Propose amendment
      - Attempt vote immediately
      - Verify blocked with correct days_remaining
    - Test: `test_fr126_vote_allowed_after_14_days` (AC1, AC2)
      - Propose amendment with mocked time
      - Fast forward 14 days
      - Verify vote allowed
    - Test: `test_fr126_vote_blocked_event_created` (AC2)
      - Attempt early vote
      - Verify `AmendmentVoteBlockedEvent` created
      - Verify event is witnessed
    - Test: `test_fr127_impact_analysis_required_for_core_guarantee` (AC3)
      - Propose core guarantee amendment without analysis
      - Verify rejection
    - Test: `test_fr127_impact_analysis_questions_answered` (AC3)
      - Propose with complete impact analysis
      - Verify acceptance
    - Test: `test_fr128_history_hiding_blocked` (AC4)
      - Propose amendment with history-hiding intent
      - Verify rejection with FR128 error
    - Test: `test_fr128_normal_amendment_allowed` (AC4)
      - Propose normal amendment
      - Verify acceptance
    - Test: `test_observer_query_pending_amendments` (AC5)
      - Multiple pending amendments
      - Query returns all with visibility status
    - Test: `test_halt_check_prevents_amendment_operations`
      - Set system halted
      - Attempt operations
      - Verify SystemHaltedError
    - Test: `test_amendment_event_witnessed`
      - Propose amendment
      - Verify event has witness attribution

## Dev Notes

### Constitutional Constraints (CRITICAL)

- **FR126**: Constitutional amendment proposals SHALL be publicly visible minimum 14 days before vote
- **FR127**: Amendments affecting core guarantees SHALL require published impact analysis ("reduces visibility? raises silence probability? weakens irreversibility?")
- **FR128**: Amendments making previous amendments unreviewable are constitutionally prohibited
- **CT-11**: Silent failure destroys legitimacy -> HALT CHECK FIRST at every operation
- **CT-12**: Witnessing creates accountability -> All amendment events MUST be witnessed
- **CT-15**: Legitimacy requires consent -> 14-day period ensures informed consent

### FR Discrepancy Note

The epics.md file references FR119-FR121 for this story, but the PRD.md (source of truth) shows:
- FR119: Topic priority (Topic Drowning Defense)
- FR120: Heartbeat signing (Heartbeat Forgery)
- FR121: Heartbeat canonical hash (Agent Replacement)

The correct FRs for Amendment Visibility are **FR126-FR128** (Amendment Erosion Defense section in PRD). This story implements FR126-FR128.

### ADR-6: Amendment, Ceremony, and Convention Tier

Story 6.7 implements the **visibility enforcement** aspect of ADR-6:

| Tier | Scope | Quorum | Deliberation | Visibility |
|------|-------|--------|--------------|------------|
| **Tier 1: Operational** | Config, parameters | 2 Keepers | None | N/A |
| **Tier 2: Constitutional** | Schema, ADR amendments | 3 Keepers + witness | 24h cooling | **14 days (FR126)** |
| **Tier 3: Convention** | Fundamental changes | Supermajority + external | 7d cooling | **14 days (FR126)** |

The 14-day visibility period applies to both Tier 2 and Tier 3 amendments as a baseline requirement.

### Epic 6 Context - Story 6.7 Position

```
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.6: Witness Pool Anomaly Detection (COMPLETED)           │
│ - Statistical co-occurrence analysis (FR116)                    │
│ - Unavailability pattern detection (FR116)                      │
│ - Witness pool degraded mode (FR117)                            │
│ - ADR-7 Statistics layer integration                            │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Followed by
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.7: Amendment Visibility (THIS STORY)                    │
│ - 14-day public visibility period (FR126)                       │
│ - Impact analysis for core guarantees (FR127)                   │
│ - History protection (FR128)                                    │
│ - ADR-6 Amendment ceremony infrastructure                       │
└─────────────────────────────────────────────────────────────────┘
         │
         │ Enables
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Story 6.8: Breach Collusion Defense (FUTURE)                    │
│ - Collusion investigation triggered from anomalies              │
│ - Hash verification (FR125)                                     │
│ - Keeper impersonation defense (FR126)                          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Dependencies from Previous Stories

From Story 6.6 (Witness Pool Anomaly Detection):
- Pattern for statistical analysis and alert generation
- `WitnessAnomalyEvent` pattern for event creation
- Stub implementation patterns

From Story 6.4 (Constitutional Thresholds):
- `src/domain/primitives/constitutional_thresholds.py` - Threshold patterns
- Constitutional floor enforcement patterns

From Core Infrastructure:
- `src/application/ports/halt_checker.py` - HaltCheckerProtocol
- `src/domain/errors/writer.py` - SystemHaltedError
- `src/domain/events/event.py` - Base event patterns
- `src/application/services/event_writer_service.py` - For creating witnessed events

From Architecture (ADR-6):
- Ceremony tier definitions
- `src/domain/ceremonies/governance/amendment.py` (planned path)
- Amendment ceremony state machine patterns

### Amendment Proposal Workflow

```python
# Amendment proposal workflow (FR126-FR128)

async def propose_amendment(
    proposal: AmendmentProposalRequest,
) -> AmendmentProposal:
    """Submit a constitutional amendment proposal.

    FR126: Must be visible 14 days before vote.
    FR127: Core guarantees require impact analysis.
    FR128: Cannot hide amendment history.

    Returns:
        AmendmentProposal with calculated votable_from date.

    Raises:
        AmendmentHistoryProtectionError: If FR128 violated.
        AmendmentImpactAnalysisMissingError: If FR127 violated.
        SystemHaltedError: If system is halted.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    # FR128: History protection check
    if self._contains_history_hiding_intent(proposal.summary, proposal.affected_guarantees):
        raise AmendmentHistoryProtectionError(
            amendment_id=proposal.amendment_id
        )

    # FR127: Impact analysis for core guarantees
    if proposal.is_core_guarantee and proposal.impact_analysis is None:
        raise AmendmentImpactAnalysisMissingError(
            amendment_id=proposal.amendment_id,
            affected_guarantees=proposal.affected_guarantees,
        )

    # FR126: Calculate votable date (14 days from now)
    now = datetime.now(UTC)
    votable_from = now + timedelta(days=14)

    # Create proposal
    amendment = AmendmentProposal(
        amendment_id=proposal.amendment_id,
        amendment_type=proposal.amendment_type,
        title=proposal.title,
        summary=proposal.summary,
        proposed_at=now,
        visible_from=now,
        votable_from=votable_from,
        proposer_id=proposal.proposer_id,
        is_core_guarantee=proposal.is_core_guarantee,
        impact_analysis=proposal.impact_analysis,
        affected_guarantees=proposal.affected_guarantees,
        status=AmendmentStatus.VISIBILITY_PERIOD,
    )

    # Save and create event
    await self._repository.save_amendment(amendment)

    event = AmendmentProposedEventPayload(
        amendment_id=amendment.amendment_id,
        amendment_type=amendment.amendment_type,
        title=amendment.title,
        summary=amendment.summary,
        proposed_at=amendment.proposed_at,
        visible_from=amendment.visible_from,
        votable_from=amendment.votable_from,
        proposer_id=amendment.proposer_id,
        is_core_guarantee=amendment.is_core_guarantee,
        impact_analysis=amendment.impact_analysis,
        affected_guarantees=amendment.affected_guarantees,
    )

    if self._event_writer:
        await self._event_writer.write_event(event)

    return amendment
```

### Vote Eligibility Check (FR126)

```python
@dataclass(frozen=True)
class VoteEligibilityResult:
    """Result of vote eligibility check (FR126).

    Constitutional Constraint (FR126):
    Amendment proposals SHALL be publicly visible
    minimum 14 days before vote.
    """
    is_eligible: bool
    days_remaining: int
    votable_from: datetime
    reason: str


async def check_vote_eligibility(
    self,
    amendment_id: str,
) -> VoteEligibilityResult:
    """Check if amendment can proceed to vote (FR126).

    Returns:
        VoteEligibilityResult with eligibility status.

    Raises:
        AmendmentNotFoundError: If amendment doesn't exist.
        SystemHaltedError: If system is halted.
    """
    # HALT CHECK FIRST (CT-11)
    if await self._halt_checker.is_halted():
        raise SystemHaltedError("System halted")

    amendment = await self._repository.get_amendment(amendment_id)
    if amendment is None:
        raise AmendmentNotFoundError(amendment_id=amendment_id)

    now = datetime.now(UTC)

    if now >= amendment.votable_from:
        return VoteEligibilityResult(
            is_eligible=True,
            days_remaining=0,
            votable_from=amendment.votable_from,
            reason="Visibility period complete",
        )

    days_remaining = (amendment.votable_from - now).days + 1

    # Create blocked event
    if self._event_writer:
        blocked_event = AmendmentVoteBlockedEventPayload(
            amendment_id=amendment_id,
            blocked_reason=f"FR126: Visibility period incomplete",
            days_remaining=days_remaining,
            votable_from=amendment.votable_from,
            blocked_at=now,
        )
        await self._event_writer.write_event(blocked_event)

    return VoteEligibilityResult(
        is_eligible=False,
        days_remaining=days_remaining,
        votable_from=amendment.votable_from,
        reason=f"FR126: Amendment visibility period incomplete - {days_remaining} days remaining",
    )
```

### Impact Analysis Validator (FR127)

```python
def validate_impact_analysis(
    impact_analysis: AmendmentImpactAnalysis,
) -> list[str]:
    """Validate FR127 impact analysis completeness.

    FR127 requires answering:
    - "reduces visibility?"
    - "raises silence probability?"
    - "weakens irreversibility?"

    Returns:
        List of missing/invalid fields (empty if valid).
    """
    errors = []

    # All three questions must be explicitly answered
    if impact_analysis.reduces_visibility is None:
        errors.append("Missing answer: 'reduces visibility?'")

    if impact_analysis.raises_silence_probability is None:
        errors.append("Missing answer: 'raises silence probability?'")

    if impact_analysis.weakens_irreversibility is None:
        errors.append("Missing answer: 'weakens irreversibility?'")

    # Analysis text required
    if not impact_analysis.analysis_text or len(impact_analysis.analysis_text) < 50:
        errors.append("Impact analysis text must be at least 50 characters")

    # Attribution required
    if not impact_analysis.analyzed_by:
        errors.append("Impact analysis must have attribution")

    return errors
```

### History Protection Check (FR128)

```python
HISTORY_HIDING_KEYWORDS = frozenset({
    "unreviewable",
    "hide previous",
    "restrict access to amendments",
    "remove visibility",
    "delete amendment history",
    "obscure previous",
    "make inaccessible",
    "prevent review",
})


def _contains_history_hiding_intent(
    summary: str,
    affected_guarantees: tuple[str, ...],
) -> bool:
    """Check if amendment would hide history (FR128).

    FR128: Amendments making previous amendments
    unreviewable are constitutionally prohibited.

    Returns:
        True if amendment appears to hide history.
    """
    summary_lower = summary.lower()

    # Check for explicit history-hiding keywords
    for keyword in HISTORY_HIDING_KEYWORDS:
        if keyword in summary_lower:
            return True

    # Check if targeting amendment visibility system
    visibility_targets = {
        "amendment_visibility",
        "amendment_history",
        "fr126",
        "fr128",
    }
    for guarantee in affected_guarantees:
        if guarantee.lower() in visibility_targets:
            return True

    return False
```

### Import Rules (Hexagonal Architecture)

- `domain/events/amendment.py` imports from `domain/`, `typing`, `dataclasses`, `datetime`, `enum`
- `domain/errors/amendment.py` inherits from `ConstitutionalViolationError`
- `application/ports/amendment_repository.py` imports from `abc`, `typing`, domain events
- `application/ports/amendment_visibility_validator.py` imports from `abc`, `typing`, `datetime`
- `application/services/amendment_visibility_service.py` imports from `application/ports/`, `domain/`
- NEVER import from `infrastructure/` in `domain/` or `application/`

### Testing Standards

- ALL tests use `pytest.mark.asyncio`
- Use `AsyncMock` for async dependencies
- Unit tests mock the protocol interfaces
- Integration tests use stub implementations
- FR126 tests MUST verify:
  - 14-day visibility period calculated correctly
  - Votes blocked before period complete
  - Vote blocked events created and witnessed
- FR127 tests MUST verify:
  - Core guarantee amendments require impact analysis
  - Impact analysis validates all three questions answered
  - Missing analysis blocks submission
- FR128 tests MUST verify:
  - History-hiding amendments rejected
  - Rejection event created with correct error
  - Normal amendments allowed

### Files to Create

```
src/domain/events/amendment.py                              # Amendment events
src/domain/errors/amendment.py                              # Amendment errors
src/application/ports/amendment_repository.py               # Repository port
src/application/ports/amendment_visibility_validator.py     # Validator port
src/application/services/amendment_visibility_service.py    # Main service
src/infrastructure/stubs/amendment_repository_stub.py       # Repository stub
src/infrastructure/stubs/amendment_visibility_validator_stub.py  # Validator stub
tests/unit/domain/test_amendment_events.py                  # Event tests
tests/unit/domain/test_amendment_errors.py                  # Error tests
tests/unit/application/test_amendment_visibility_service.py # Service tests
tests/unit/infrastructure/test_amendment_repository_stub.py # Repository stub tests
tests/unit/infrastructure/test_amendment_visibility_validator_stub.py  # Validator stub tests
tests/integration/test_amendment_visibility_integration.py  # Integration tests
```

### Files to Modify

```
src/domain/events/__init__.py                               # Export new events
src/domain/errors/__init__.py                               # Export new errors
src/application/ports/__init__.py                           # Export new ports
src/application/services/__init__.py                        # Export new services
src/infrastructure/stubs/__init__.py                        # Export new stubs
```

### Project Structure Notes

- Amendment visibility service follows existing ceremony patterns from ADR-6
- 14-day period is a hard constitutional requirement (FR126)
- Impact analysis is semantic validation (FR127)
- History protection is structural validation (FR128)
- All operations require halt check (CT-11)
- All events require witnessing (CT-12)

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-6.7] - Story definition
- [Source: _bmad-output/planning-artifacts/prd.md#FR126] - 14-day visibility requirement
- [Source: _bmad-output/planning-artifacts/prd.md#FR127] - Impact analysis requirement
- [Source: _bmad-output/planning-artifacts/prd.md#FR128] - History protection
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-6] - Amendment/Ceremony tier
- [Source: _bmad-output/project-context.md] - Project implementation rules
- [Source: _bmad-output/implementation-artifacts/stories/6-6-witness-pool-anomaly-detection.md] - Previous story patterns
- [Source: src/domain/events/event.py] - Base event patterns
- [Source: src/application/ports/halt_checker.py] - Halt check pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 8 tasks completed successfully
- 88 unit and integration tests passing
- Implements FR126 (14-day visibility period), FR127 (impact analysis for core guarantees), FR128 (history protection)
- All operations follow CT-11 (HALT CHECK FIRST) pattern
- Service, ports, stubs, and tests follow hexagonal architecture

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-01-08 | Story created with comprehensive FR126-FR128 context, visibility period calculation, impact analysis validation, history protection | Create-Story Workflow (Opus 4.5) |
| 2026-01-08 | Story implementation completed - all 8 tasks done, 88 tests passing | Dev Agent (Opus 4.5) |

### File List

**Created:**
- `src/domain/events/amendment.py` - Amendment domain events (AmendmentProposedEventPayload, AmendmentVoteBlockedEventPayload, AmendmentRejectedEventPayload, AmendmentImpactAnalysis)
- `src/domain/errors/amendment.py` - Amendment domain errors (AmendmentVisibilityIncompleteError, AmendmentImpactAnalysisMissingError, AmendmentHistoryProtectionError, AmendmentNotFoundError)
- `src/application/ports/amendment_repository.py` - Repository port (AmendmentRepositoryProtocol, AmendmentProposal)
- `src/application/ports/amendment_visibility_validator.py` - Validator port (AmendmentVisibilityValidatorProtocol)
- `src/application/services/amendment_visibility_service.py` - Main service (AmendmentVisibilityService)
- `src/infrastructure/stubs/amendment_repository_stub.py` - Repository stub
- `src/infrastructure/stubs/amendment_visibility_validator_stub.py` - Validator stub
- `tests/unit/domain/test_amendment_events.py` - Event unit tests
- `tests/unit/domain/test_amendment_errors.py` - Error unit tests
- `tests/unit/application/test_amendment_visibility_service.py` - Service unit tests
- `tests/unit/infrastructure/test_amendment_repository_stub.py` - Repository stub unit tests
- `tests/integration/test_amendment_visibility_integration.py` - Integration tests

**Modified:**
- `src/domain/events/__init__.py` - Export amendment events
- `src/domain/errors/__init__.py` - Export amendment errors
- `src/application/ports/__init__.py` - Export amendment ports
- `src/application/services/__init__.py` - Export amendment service
- `src/infrastructure/stubs/__init__.py` - Export amendment stubs

