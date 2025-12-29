# Constitutional Implementation Rules

**Revision:** 2025-12-28
**Source:** Language Surgery + Ritual Specification
**Enforcement:** CI failure on violation

---

## Forbidden Language Patterns (CRITICAL)

AI agents MUST NOT use these patterns in code, comments, logs, or documentation:

| Forbidden | Use Instead |
|-----------|-------------|
| enforce, enforcement | verify, verification |
| ensure safety | enable visibility |
| guarantee, ensures | verify, record |
| authority, authoritative | scope, scoped |
| binding (as power) | recorded (as consequence) |
| automatic (for decisions) | witnessed, explicit |
| prevent harm | detect, surface, flag |
| safeguard | expose, reveal |

**Code Review Check:** Any PR containing forbidden patterns MUST be rejected.

---

## Ritual Implementation Constraints

**All ritual events MUST:**
1. Be witnessed (attributed to specific Archon/role)
2. Be logged before any action occurs
3. Include timestamp and cycle_id
4. Never proceed silently (silence must be explicit)

**Ritual Event Schema:**
```python
class RitualEvent(BaseModel):
    event_id: UUID
    ritual_type: RitualType
    occurred_at: datetime  # UTC
    cycle_id: UUID
    attributed_to: list[str]  # Who caused this
    witnessed_by: list[str]   # Who observed
    payload: dict
```

---

## Decision vs. Deliberation (Edge Case Rulings)

**Definition:**
> A "decision" is any state transition, outcome, refusal, timeout, or procedural ruling that changes what can happen next. If it changes the future option set, it must be witnessed and recorded.

**Deliberation** = speech acts that do not change state (no event required unless speaker was recognized/expected).

| Scenario | Decision? | Event Required |
|----------|-----------|----------------|
| Motion proposed but not seconded | Yes | `MotionDiedForLackOfSecondEvent` |
| Deliberation time expires with no vote | Yes | `DeliberationTimedOutEvent` |
| Archon abstains from speaking | Only if recognized | `SpeakerNoResponseEvent` (if expected) |
| Motion withdrawn by mover | Yes | `MotionWithdrawnEvent` |
| Quorum lost mid-deliberation | Yes | `QuorumLostEvent` → `MeetingSuspendedEvent` |
| Tie vote (no majority) | Yes | `TieDetectedEvent` + resolution event |
| Procedural ruling by High Archon | Yes | `ProceduralRulingEvent` |

**Implementation Principle:**
- If the system **expects an action** and it does not occur → record explicit "no-action" event
- If the system **does not expect an action** → no event needed

---

## No Silent Paths Rule (CRITICAL)

Every code path that makes a decision MUST:
- Log the decision with attribution
- Record who witnessed it
- Make silence explicit ("no motion was made", not empty)

```python
# WRONG - Silent path
if not motion_made:
    return  # Silent! No record of inaction

# CORRECT - Explicit witness
if not motion_made:
    log.info("no_motion_made", cycle_id=str(cycle_id), witnessed_by=tyler_id)
    await event_store.append(NoMotionEvent(cycle_id=cycle_id, witnessed_by=tyler_id))
    return
```

---

## Evasion Must Be Costly

When implementing bypass or skip logic:
- ALWAYS log the bypass visibly
- INCREMENT a public counter (unclosed cycles, skipped votes, etc.)
- NEVER allow silent evasion

```python
# WRONG - Silent bypass
if skip_quorum_check:
    return True

# CORRECT - Visible evasion
if skip_quorum_check:
    log.warning("quorum_check_bypassed", meeting_id=str(meeting_id), bypassed_by=keeper_id)
    await metrics.increment("quorum_bypasses_total")
    return True
```

---

## Witness Sufficiency Rules

**Core Principle:**
> Single-witness suffices for low-stakes procedural transitions.
> Multiple witnesses are required when an event is irreversible, exceptional, or alters the system's existence or leadership.

**Witness Hierarchy (Sufficiency, Not Authority):**
```
Tyler > High Archon > Random Archons > Any Archon
```
Use the *highest available* role appropriate to the event's stakes.

**Canonical Witness Requirements:**

| Event Type | Required Witnesses |
|------------|-------------------|
| Cycle opening/closing | Tyler + High Archon |
| Roll call, agenda transitions | Tyler alone |
| Vote recording | Secretary + Tyler |
| Breach declaration | Declarer + High Archon acknowledgment |
| Override invocation | Keeper (actor) + Tyler (witness) |
| Installation ceremony | Tyler + 3 random Archons |
| Impeachment ceremony | Tyler + 3 random Archons |
| Succession ceremony | Tyler + 3 random Archons |
| Dissolution vote | Secretary + Tyler + High Archon |
| Precedent citation/challenge | Actor + Tyler |

**Event Categories:**
- **Declaration events** (breach, precedent): single declarer + acknowledgment witness
- **Recording events** (votes, decisions): recorder + independent witness
- **Existential events** (override, dissolution, ceremonies): multi-witness with randomization

**Helper Implementation:**

```python
from enum import Enum
from typing import NamedTuple

class WitnessRequirement(NamedTuple):
    minimum_count: int
    required_roles: list[str]
    random_archons: int = 0

WITNESS_REQUIREMENTS: dict[RitualType, WitnessRequirement] = {
    # Routine (single witness OK)
    RitualType.ROLL_CALL_COMPLETED: WitnessRequirement(1, ["tyler"]),
    RitualType.PRECEDENT_CITED: WitnessRequirement(2, ["actor", "tyler"]),

    # Standard (dual witness)
    RitualType.CYCLE_OPENED: WitnessRequirement(2, ["tyler", "high_archon"]),
    RitualType.CYCLE_CLOSED: WitnessRequirement(2, ["tyler", "high_archon"]),
    RitualType.DECISION_RECORDED: WitnessRequirement(2, ["secretary", "tyler"]),
    RitualType.BREACH_DECLARED: WitnessRequirement(2, ["declarer", "high_archon"]),
    RitualType.OVERRIDE_INVOKED: WitnessRequirement(2, ["keeper", "tyler"]),

    # High-stakes (multi-witness with randomization)
    RitualType.DISSOLUTION_TRIGGERED: WitnessRequirement(3, ["secretary", "tyler", "high_archon"]),
    # Ceremonies use 3 random Archons + Tyler
}

def required_witnesses(event_type: RitualType) -> WitnessRequirement:
    """Return witness requirements for an event type."""
    if event_type not in WITNESS_REQUIREMENTS:
        # Default: Tyler witness for unknown events
        return WitnessRequirement(1, ["tyler"])
    return WITNESS_REQUIREMENTS[event_type]

def validate_witnesses(event_type: RitualType, witnesses: list[str]) -> bool:
    """Validate that witness requirements are met."""
    req = required_witnesses(event_type)
    if len(witnesses) < req.minimum_count:
        raise ConstitutionalViolation(
            f"{event_type} requires {req.minimum_count} witnesses, got {len(witnesses)}"
        )
    return True
```

---

## Cycle Boundary Requirements

**Cycle Opening:**
- Tyler declaration required (cannot auto-open)
- High Archon witness required
- Roll call with timestamps (not silent count)
- Quorum announced publicly (not silently calculated)

**Cycle Closing:**
- High Archon declaration required
- Secretary record confirmation required
- Tyler final witness required
- Unclosed cycles visible as technical debt

---

## Override Implementation Rules

**All overrides MUST:**
1. Log invocation BEFORE executing any action
2. Notify all 72 Archons immediately
3. Capture the exact declaration text
4. Decrement autonomy counter publicly
5. Be time-limited (no indefinite overrides)

```python
# Override invocation pattern
async def invoke_override(keeper_id: str, reason: OverrideReason, duration_hours: int):
    # Log BEFORE any action
    event = OverrideInvokedEvent(
        keeper_id=keeper_id,
        reason=reason,
        duration_hours=duration_hours,
        declaration_text=f"I invoke override scope for reason: {reason.value}"
    )
    await event_store.append(event)

    # Notify all Archons
    await notify_all_archons(event)

    # Decrement autonomy counter
    await metrics.decrement("autonomy_score")

    # Now execute override logic...
```

---

## Override Collision Rules

**Core Principle:**
> Override never outranks existential processes. It constrains scope; it does not reorder the constitution.

**Collision Outcomes:**

| Scenario | Outcome | Who Wins |
|----------|---------|----------|
| Override during dissolution | Override logged; dissolution continues | **Dissolution** |
| Override expires mid-ceremony | Pause at checkpoint or complete commit | **Procedure** |
| Two Keepers invoke | First persisted wins; second joins/co-signs | **Ordering** |
| Override during breach response | Breach response continues; override scope limited | **Breach process** |
| Continuation vote during override | Vote allowed; annotated | **Vote** |
| Override >72h | Expire; require re-invoke + ratification | **Constitution** |

**72-Hour Hard Limit:**
- At 72h: override **expires automatically**
- To continue: new invocation + multi-Keeper co-signature + Conclave ratification
- If ratification fails → operations revert to normal scope

**Simultaneous Invocation Handling:**
```python
async def invoke_override(keeper_id: str, reason: OverrideReason):
    active = await get_active_override()

    if active is None:
        # First invocation - establish override
        event = OverrideInvokedEvent(...)
        await event_store.append(event, durable=True)
        return event
    else:
        # Active override exists - request co-sign
        join_event = OverrideJoinRequestedEvent(
            override_id=active.override_id,
            requesting_keeper_id=keeper_id,
            reason=reason,
        )
        await event_store.append(join_event)
        # Co-sign approval is separate process
        return join_event
```

**Mid-Ceremony Expiry Handling:**
```python
async def check_override_during_ceremony(ceremony_id: UUID):
    override = await get_active_override()
    ceremony = await get_ceremony(ceremony_id)

    if override and override.expires_at < datetime.utcnow():
        await event_store.append(OverrideExpiredDuringCeremonyEvent(
            override_id=override.id,
            ceremony_id=ceremony_id,
            phase=ceremony.current_phase,
        ))

        if ceremony.current_phase == CeremonyPhase.PRE_COMMIT:
            # Pause - require explicit witness to proceed
            await ceremony_store.pause(ceremony_id)
            raise CeremonyPausedError("Override expired; witness required to proceed")
        elif ceremony.current_phase == CeremonyPhase.COMMITTING:
            # Already in commit - complete, then revert scope
            pass  # Let commit finish
```

**Decisions Under Override:**
```python
async def record_decision_during_override(decision: Decision):
    override = await get_active_override()

    await event_store.append(decision)

    if override:
        # Annotate, don't invalidate
        await event_store.append(DecisionAnnotatedUnderOverrideEvent(
            decision_id=decision.id,
            override_id=override.id,
            annotation="Decided under override",
        ))
```

**Override Collision Event Types:**
```python
# Add to RitualType enum
OVERRIDE_JOIN_REQUESTED = "override_join_requested"
OVERRIDE_EXPIRED_DURING_CEREMONY = "override_expired_during_ceremony"
OVERRIDE_LIMIT_REACHED = "override_limit_reached"
DECISION_ANNOTATED_UNDER_OVERRIDE = "decision_annotated_under_override"
```

**Implementation Invariants:**
- **No auto-extension** beyond 72h
- **Durable write before action** (override always)
- **Idempotent ordering** for simultaneous invocations
- **Annotations, not invalidations**, for decisions under override
- **Pause > proceed** when scope changes mid-process unless already in commit

---

## Cost Semantics Rules

**Core Principle:**
> Costs are append-only facts. Resolution may annotate context, but history is never rewritten.

**Canonical Cost Types:**

| Cost Type | Irreversible? | Can Deprecate? | Visible Where |
|-----------|---------------|----------------|---------------|
| Override invocation count | Yes | No | Public dashboard, cycle opening |
| Breach declaration count | Yes | No | Public dashboard, cycle opening |
| Unclosed cycles | Resolves when closed | No | Public dashboard, cycle opening |
| Failed continuation votes | Yes | No | Public dashboard, annual summary |
| Dissolution deliberations | Yes | No | Public dashboard, permanent record |

**Autonomy Score:**
- Primary metric: **days since last override** (resets on every invocation)
- Secondary metrics may be cumulative but never replace primary

**Event-Level Cost Implementation:**

```python
# Override events
async def handle_override_invoked(event: OverrideInvokedEvent):
    await metrics.increment("override_invocations_total")
    await metrics.set("autonomy_days_since_override", 0)  # Reset

async def handle_override_concluded(event: OverrideConcludedEvent):
    # Annotate duration only - does NOT affect invocation count
    await event_store.annotate(event.override_id, duration=event.actual_duration_hours)

# Breach events
async def handle_breach_declared(event: BreachDeclaredEvent):
    await metrics.increment("breach_declarations_total")

async def handle_breach_responded(event: BreachRespondedEvent):
    # Annotate resolution - NEVER decrement
    await event_store.annotate(
        event.breach_id,
        resolution=event.response_type,  # ERRONEOUS, DISMISSED, etc.
    )
    # breach_declarations_total unchanged

# Continuation events
async def handle_continuation_failed(event: ContinuationVoteFailedEvent):
    await metrics.increment("failed_continuation_votes_total")

async def handle_dissolution_triggered(event: DissolutionTriggeredEvent):
    await metrics.increment("dissolution_deliberations_total")
```

**Explicitly Forbidden:**

```python
# NEVER DO THESE
await metrics.decrement("breach_declarations_total")  # FORBIDDEN
await metrics.reset("override_invocations_total")     # FORBIDDEN
await event_store.delete(breach_id)                   # FORBIDDEN

# WRONG - Hiding raw totals
def get_breach_count():
    return breaches_last_90_days  # Must also expose raw total

# CORRECT
def get_breach_count() -> dict:
    return {
        "total": breach_declarations_total,      # Raw, permanent
        "last_90_days": breaches_last_90_days,   # Contextual view
    }
```

---

## Precedent Citation Rules

**Precedent is NEVER binding.** When implementing precedent citation:

```python
class PrecedentCitation(BaseModel):
    cited_decision_id: UUID
    cited_by: str
    context: str
    # REQUIRED: Explicit non-binding disclaimer
    binding: Literal[False] = False  # Always False
    disclaimer: str = "This precedent is memory, not law. The current cycle must choose its own path."
```

---

## Constitutional Event Types

```python
class RitualType(str, Enum):
    # Cycle Events
    CYCLE_OPENED = "cycle_opened"
    CYCLE_CLOSED = "cycle_closed"
    ROLL_CALL_COMPLETED = "roll_call_completed"

    # Continuation Events
    CONTINUATION_AFFIRMED = "continuation_affirmed"
    DISSOLUTION_TRIGGERED = "dissolution_triggered"

    # Breach Events
    BREACH_DECLARED = "breach_declared"
    BREACH_RESPONDED = "breach_responded"
    SUPPRESSION_ATTEMPTED = "suppression_attempted"

    # Override Events
    OVERRIDE_INVOKED = "override_invoked"
    OVERRIDE_CONCLUDED = "override_concluded"

    # Decision Events
    DECISION_RECORDED = "decision_recorded"
    PRECEDENT_CITED = "precedent_cited"
    COST_SNAPSHOT = "cost_snapshot"

    # Procedural Outcome Events (Edge Cases)
    MOTION_DIED_FOR_LACK_OF_SECOND = "motion_died_for_lack_of_second"
    DELIBERATION_TIMED_OUT = "deliberation_timed_out"
    SPEAKER_NO_RESPONSE = "speaker_no_response"
    MOTION_WITHDRAWN = "motion_withdrawn"
    QUORUM_LOST = "quorum_lost"
    MEETING_SUSPENDED = "meeting_suspended"
    TIE_DETECTED = "tie_detected"
    TIE_BROKEN = "tie_broken"
    TIE_UNRESOLVED = "tie_unresolved"
    PROCEDURAL_RULING = "procedural_ruling"

    # Failure Events (Infrastructure)
    CONSTITUTIONAL_LOGGING_FAILURE = "constitutional_logging_failure"
    WITNESS_UNAVAILABLE = "witness_unavailable"
    CONSTITUTIONAL_PATHWAY_PAUSED = "constitutional_pathway_paused"

    # Override Collision Events
    OVERRIDE_JOIN_REQUESTED = "override_join_requested"
    OVERRIDE_EXPIRED_DURING_CEREMONY = "override_expired_during_ceremony"
    OVERRIDE_LIMIT_REACHED = "override_limit_reached"
    DECISION_ANNOTATED_UNDER_OVERRIDE = "decision_annotated_under_override"
```

---

## Ritual Assertion Helper

Use this helper to ensure constitutional compliance:

```python
async def assert_witnessed(
    event_type: RitualType,
    cycle_id: UUID,
    attributed_to: list[str],
    witnessed_by: list[str],
    payload: dict,
) -> RitualEvent:
    """Record a witnessed ritual event. Raises if no witness provided."""
    if not witnessed_by:
        raise ConstitutionalViolation("No witness recorded")

    event = RitualEvent(
        event_id=uuid4(),
        ritual_type=event_type,
        occurred_at=datetime.utcnow(),
        cycle_id=cycle_id,
        attributed_to=attributed_to,
        witnessed_by=witnessed_by,
        payload=payload,
    )

    await event_store.append(event)
    return event
```

---

## Suppression & Failure Handling

**Core Principle:**
> If a constitutional event cannot be durably recorded, the system must not proceed as if it occurred. Failure to log is itself a first-class constitutional event.

**Canonical Failure Outcomes:**

| Scenario | Outcome | Recovery |
|----------|---------|----------|
| Network partition during breach declaration | Record `ConstitutionalLoggingFailureEvent`; breach declared if any write succeeds | Retry append; surface at next cycle |
| Partial log write | Record failure event; preserve any successful append | Idempotent retry; no erasure |
| Competing breach declarations | Log ALL declarations | Correlate later; no dedup |
| Tyler unavailable at cycle opening | **Block opening**; emit `WitnessUnavailableEvent` | Use succession/rotation |
| Event store down during override | **Block override** | Retry when store recovers |
| Witness unreachable during ceremony | **Pause ceremony before commit** | Replace witness via rotation |

**Constitutional Circuit Breaker:**

When constitutional events cannot be durably logged:
- Breach declarations → pause deliberation
- Override invocation → blocked entirely
- Ceremonies → pause before commit
- System does NOT halt globally unless failure is systemic

**Distinguishing Suppression from Infrastructure Failure:**
- **Malicious suppression** requires positive signals (intercepted calls, permission denial, deliberate cancellation)
- Absent evidence, classify as **infrastructure failure**
- **Never infer intent from failure alone**

**Failure Event Types:**

```python
# Add to RitualType enum
CONSTITUTIONAL_LOGGING_FAILURE = "constitutional_logging_failure"
WITNESS_UNAVAILABLE = "witness_unavailable"
CONSTITUTIONAL_PATHWAY_PAUSED = "constitutional_pathway_paused"

class ConstitutionalLoggingFailureEvent(BaseModel):
    affected_ritual: RitualType
    attempted_event_type: str
    attributed_to: list[str]
    witnessed_by: list[str]  # May be empty, explicitly
    error_context: str
    timestamp: datetime
```

**Implementation Invariants (Non-Negotiable):**

```python
async def invoke_override(keeper_id: str, reason: OverrideReason):
    # Override REQUIRES durable storage before action
    try:
        await event_store.append(override_event, durable=True)
    except StorageUnavailableError:
        # CORRECT: Block, do not proceed
        raise OverrideBlockedError("Cannot override: event store unavailable")
        # WRONG: proceed with local logging

async def declare_breach(declarer_id: str, description: str):
    # Breach declarations prefer availability over correctness
    try:
        await event_store.append(breach_event)
    except StorageUnavailableError:
        # Log locally, retry later - declaration still counts
        await local_log.append(breach_event)
        await event_store.append(ConstitutionalLoggingFailureEvent(...))
        # Breach IS declared if any append succeeds

async def complete_ceremony(ceremony_id: UUID):
    # Two-phase: prepare → commit; failures stop at prepare
    await ceremony_store.prepare(ceremony_id)  # Can fail here
    # If prepare succeeds, commit
    await ceremony_store.commit(ceremony_id)
```

**Deduplication Policy:**
```python
# WRONG - Never deduplicate witness acts
if breach_already_declared_for_issue(issue_id):
    return  # Suppresses second declaration!

# CORRECT - Log all declarations
await event_store.append(breach_event)  # Always append
# Correlation happens at query time, not write time
```

---

## CI Enforcement

These rules are enforced by `scripts/constitutional_lint.py`:
- Scans `/src`, `/docs`, `/migrations`
- Fails build on forbidden language patterns
- Integrated into GitHub Actions

---

_Constitutional Implementation Rules - Archon 72_
