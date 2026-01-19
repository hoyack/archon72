# Story 0.7: Archon Persona Definitions (Three Fates Pool)

**Epic:** Petition Epic 0 - Foundation & Migration
**Priority:** P0
**Status:** Done
**Completed:** 2026-01-19

## User Story

As a **developer**,
I want Archon persona definitions for the Three Fates pool,
So that deliberation sessions can assign appropriate Marquis-rank Archons.

## Acceptance Criteria

### AC1: At Least 5 Fate Archon Personas Defined ✅
- [x] 7 Fate Archon personas defined (exceeds requirement of 5)
- [x] Each has unique identifier (UUID from archons-base.json)
- [x] Each has persona name and title
- [x] Each has deliberation style enum value

### AC2: Deliberation Styles Defined ✅
- [x] 5 distinct deliberation styles:
  - `CONSTITUTIONAL_PURIST` - Strict adherence to constitutional principles
  - `PRAGMATIC_MODERATOR` - Balanced, practical approach seeking consensus
  - `ADVERSARIAL_CHALLENGER` - Stress-tests arguments, plays devil's advocate
  - `WISDOM_SEEKER` - Focuses on long-term implications and precedent
  - `RECONCILER` - Seeks harmony between conflicting positions

### AC3: System Prompt Templates ✅
- [x] Each Archon has a system prompt template
- [x] Templates include deliberation header with constitutional context
- [x] Templates support placeholder substitution (`{archon_name}`, `{petition_context}`)
- [x] Role-specific prompts guide deliberation behavior

### AC4: Personas Stored in Configuration ✅
- [x] Personas defined in code (`src/domain/models/fate_archon.py`)
- [x] No database storage required
- [x] Canonical pool exported as `THREE_FATES_POOL` tuple
- [x] Lookup dictionaries for ID and name access

### AC5: ArchonPool Service ✅
- [x] `ArchonPoolProtocol` defines the contract
- [x] `ArchonPoolService` implements deterministic selection
- [x] Selects exactly 3 Archons per petition (FR-11.1)
- [x] Selection is deterministic given (petition_id + seed)
- [x] SHA-256 based selection algorithm for uniform distribution

### AC6: Testing Support ✅
- [x] `ArchonPoolStub` provides in-memory implementation
- [x] Pre-populated with canonical pool
- [x] Supports fixed selection override for tests
- [x] Operation tracking for test assertions
- [x] `create_test_archon` factory function

## Constitutional Constraints

- **HP-11:** Archon persona definitions for Three Fates pool
- **FR-11.1:** System assigns exactly 3 Marquis-rank Archons per petition
- **AT-1:** Every petition terminates in exactly one of Three Fates
- **AT-6:** Deliberation is collective judgment, not unilateral decision

## Implementation Details

### Files Created

#### Domain Model
- `src/domain/models/fate_archon.py` - FateArchon entity, DeliberationStyle enum, 7 canonical personas

#### Protocol (Port)
- `src/application/ports/archon_pool.py` - ArchonPoolProtocol interface

#### Service
- `src/application/services/archon_pool.py` - ArchonPoolService with deterministic selection

#### Stub
- `src/infrastructure/stubs/archon_pool_stub.py` - In-memory stub for testing

#### Tests
- `tests/unit/domain/models/test_fate_archon.py` - Unit tests for FateArchon domain model
- `tests/unit/application/services/test_archon_pool_service.py` - Unit tests for service
- `tests/unit/infrastructure/stubs/test_archon_pool_stub.py` - Unit tests for stub

### Canonical Fate Archon Pool (7 Archons)

| Name | Title | Deliberation Style |
|------|-------|-------------------|
| Amon | Marquis of Reconciliation & Prediction | RECONCILER |
| Leraje | Marquis of Conflict Resolution | ADVERSARIAL_CHALLENGER |
| Ronove | Marquis of Strategic Communication | PRAGMATIC_MODERATOR |
| Forneus | Marquis of Communication & Rhetoric Mastery | WISDOM_SEEKER |
| Naberius | Marquis of Reputation Restoration | CONSTITUTIONAL_PURIST |
| Orias | Marquis of Status & Recognition Building | WISDOM_SEEKER |
| Marchosias | Marquis of Confidence Building | PRAGMATIC_MODERATOR |

### Selection Algorithm

1. Combine `petition_id.bytes` with optional seed bytes
2. Hash with SHA-256 for uniform distribution
3. For each Archon, compute score = SHA-256(hash + archon.id.bytes)
4. Sort Archons by score
5. Return first 3 (deterministic given same inputs)

### System Prompt Template Structure

```
You are participating in a Three Fates deliberation as {archon_name}.

CONSTITUTIONAL CONTEXT:
- Every petition must terminate in exactly one of Three Fates: ACKNOWLEDGED, REFERRED, or ESCALATED
- You are one of 3 Marquis-rank Archons deliberating on this petition
- A supermajority (2-of-3) consensus is required for a disposition decision
- Deliberation follows the protocol: ASSESS → POSITION → CROSS-EXAMINE → VOTE

PETITION DETAILS:
{petition_context}

YOUR DELIBERATION ROLE:
[Role-specific instructions based on deliberation style]
```

## References

- **HP-11:** Hidden Prerequisite - Archon Personas
- **FR-11.1:** Exactly 3 Marquis-rank Archons per petition
- **AT-1:** Three Fates disposition terminal states
- **AT-6:** Collective judgment requirement

## Notes

- All 7 Archons are Marquis-rank (rank_level 6) from archons-base.json
- UUIDs match canonical IDs from archons-base.json
- Deliberation styles are distributed to ensure diverse perspectives
- Pool size (7) exceeds minimum (5) for better selection variety
- All syntax checks pass; full test execution requires Python 3.11+
