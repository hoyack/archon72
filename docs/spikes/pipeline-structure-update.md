# Pipeline Structure Update: Motion Execution vs. Work Discovery

**Status**: Implemented (2025-01-27)

## Implementation Summary

The Two Wheels architecture is now in place:

| Component | Status | Notes |
|-----------|--------|-------|
| Conclave results export | ✅ Done | `conclave-results-<session>-<timestamp>.json` |
| Registrar script | ✅ Done | `scripts/run_registrar.py` |
| Motion Ledger | ✅ Done | `_bmad-output/motion-ledger/` |
| Executive `--from-ledger` | ✅ Done | Consumes mandates directly |
| Secretary → Queue redirect | ⏳ Pending | Discovery loop unchanged for now |

### New Flow

```bash
# 1. Conclave (now emits structured results)
python scripts/run_conclave.py

# 2. Registrar (records mandates in ledger)
python scripts/run_registrar.py _bmad-output/conclave

# 3. Executive from ledger (direct mandate execution)
python scripts/run_executive_pipeline.py --from-ledger _bmad-output/motion-ledger/<session_id> --mode llm
```

---

## Problem Statement

The current pipeline conflates two distinct concerns:
1. **Execution of formal Conclave decisions** (passed motions)
2. **Discovery of emergent work items** (recommendations from debate)

When Conclave passes a motion, that motion represents a constitutional mandate. However, the current flow sends the transcript to Secretary, which extracts debate themes and recommendations—not the formal decision itself. These extracted items then flow through Consolidator → Review → Executive, meaning we're creating Epics for *side-effects of debate* rather than the *motion that was actually approved*.

## Current Flow Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT PIPELINE                                   │
└─────────────────────────────────────────────────────────────────────────────┘

  Motion Input
       │
       ▼
  ┌─────────┐
  │Conclave │ ──── Motion PASSED/FAILED
  └────┬────┘
       │
       ▼ (transcript.md)
  ┌─────────┐
  │Secretary│ ──── Extracts recommendations from DEBATE
  └────┬────┘      (not the passed motion itself)
       │
       ▼ (recommendations.json)
  ┌───────────┐
  │Consolidator│ ──── Merges into mega-motions
  └─────┬─────┘
        │
        ▼ (consolidated_motions.json)
  ┌────────────────┐
  │Review Pipeline │ ──── Triage, review, ratify
  └───────┬────────┘
          │
          ▼ (ratification_results.json)
  ┌──────────────────┐
  │Executive Pipeline│ ──── Creates Epics
  └──────────────────┘
```

### The Gap

| What We Have | What We Need |
|--------------|--------------|
| Secretary extracts debate themes | Secretary should forward the passed motion |
| Consolidator groups extracted items | Passed motion is already consolidated |
| Review re-ratifies extracted items | Passed motion is already ratified by Conclave |
| Executive creates Epics from derived work | Executive should create Epics from the mandate |

**Key Insight**: A motion that passes Conclave has already been:
- Proposed and seconded (by Kings)
- Debated (by all Archons)
- Voted on (supermajority threshold)
- Ratified (by the constitutional process)

Running it through Secretary → Consolidator → Review is redundant and loses fidelity to the original decision.

## Proposed Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROPOSED PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────┘

  Motion Input
       │
       ▼
  ┌─────────┐
  │Conclave │
  └────┬────┘
       │
       ├──────────────────────────────────────┐
       │                                      │
       ▼ PASSED                               ▼ DEBATE TRANSCRIPT
  ┌──────────────┐                      ┌─────────┐
  │Passed Motion │                      │Secretary│
  │  (mandate)   │                      └────┬────┘
  └──────┬───────┘                           │
         │                                   ▼ (recommendations)
         │                              ┌─────────────┐
         │                              │Motion Queue │ ◄── For FUTURE Conclave
         │                              └─────────────┘
         │
         ▼
  ┌──────────────────┐
  │Executive Pipeline│ ◄── Direct path from mandate
  └────────┬─────────┘
           │
           ▼
  ┌────────────────────────┐
  │Administrative Pipeline │
  └────────────────────────┘
```

### Two Distinct Paths

#### Path 1: Mandate Execution (passed motions)
```
Conclave PASS → Executive Pipeline → Administrative Pipeline → Earl Tasking
```
- The passed motion IS the work
- No re-ratification needed
- Direct transformation into Epics

#### Path 2: Work Discovery (emergent recommendations)
```
Conclave Debate → Secretary → Motion Queue → Future Conclave
```
- Recommendations are NOT yet approved
- They enter the queue for consideration
- Future Conclave will vote on them

## Implementation Changes

### 1. Conclave Output Enhancement

**Current**: Saves transcript only
**Proposed**: Also emit `passed_motions.json`

```json
{
  "session_id": "conclave-20240127",
  "passed_motions": [
    {
      "motion_id": "m-123",
      "title": "Establish AI Ethics Committee",
      "text": "WHEREAS... BE IT RESOLVED...",
      "motion_type": "policy",
      "vote_result": {
        "ayes": 48,
        "nays": 12,
        "abstentions": 12,
        "passed": true,
        "supermajority_met": true
      },
      "proposer": { "id": "...", "name": "Paimon" },
      "seconder": { "id": "...", "name": "Bael" }
    }
  ],
  "failed_motions": [...],
  "died_no_second": [...]
}
```

### 2. Executive Pipeline Input Change

**Current**: Reads `ratification_results.json` from Review Pipeline
**Proposed**: Can also read `passed_motions.json` directly from Conclave

```bash
# New: Direct mandate execution
python scripts/run_executive_pipeline.py --from-conclave _bmad-output/conclave/<session>

# Existing: From review pipeline (for non-Conclave work)
python scripts/run_executive_pipeline.py _bmad-output/review-pipeline/<session>
```

### 3. Secretary Role Clarification

**Current**: Extract recommendations → Send to Consolidator
**Proposed**: Extract recommendations → Send to Motion Queue

The Secretary becomes a "work discovery" tool, not a mandate transformer.

### 4. Motion Queue Integration

Recommendations from Secretary should create queued motions:
```json
{
  "source": "secretary_extraction",
  "source_session": "conclave-20240127",
  "recommendation": "Create oversight board for AI decisions",
  "consensus_tier": "medium",
  "status": "queued"
}
```

These wait for a future Conclave to vote on them.

## Migration Path

### Phase 1: Emit Passed Motions
- Update `run_conclave.py` to emit `passed_motions.json`
- No breaking changes to existing flow

### Phase 2: Add Direct Execution Path
- Add `--from-conclave` flag to Executive Pipeline
- Allows direct mandate execution alongside existing flow

### Phase 3: Redirect Secretary Output
- Secretary recommendations go to Motion Queue
- Remove Secretary → Consolidator → Review path for Conclave outputs

### Phase 4: Deprecate Redundant Path
- For Conclave sessions, the Secretary → Consolidator → Review path becomes optional
- Keep it for non-Conclave work discovery (e.g., brainstorming sessions)

## Implications

### What This Preserves
- Conclave's constitutional authority
- The formal voting record
- Traceability from mandate to Epic

### What This Fixes
- Passed motions no longer get "lost in translation"
- Emergent recommendations don't skip the voting process
- Clear separation between decided work and proposed work

### Open Questions

1. **Multiple passed motions per session**: Should they become one mega-Epic or separate Epics?
2. **Failed motions**: Should they go to a "rejected" archive for reference?
3. **Died-no-second motions**: Back to queue with lower priority, or discarded?
4. **Cross-motion dependencies**: If Motion B references Motion A, how do we handle?

## Summary

| Concern | Current Owner | Proposed Owner |
|---------|---------------|----------------|
| Passed motion execution | Review Pipeline (indirect) | Executive Pipeline (direct) |
| Debate recommendation extraction | Secretary | Secretary (unchanged) |
| Recommendation disposition | Consolidator → Review | Motion Queue |
| Re-ratification of Conclave decisions | Review Pipeline | None (already ratified) |

**Principle**: "Conclave decides. Executive executes. Secretary discovers. Queue holds."

---

## Addendum: Two Wheels Architecture

### Wheel 1: Discovery Loop (unchanged)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DISCOVERY LOOP                                       │
│                  (emergent recommendations need approval)                    │
└─────────────────────────────────────────────────────────────────────────────┘

  Debate Transcript
       │
       ▼
  ┌─────────┐
  │Secretary│ ──── Extract recommendations from debate
  └────┬────┘
       │
       ▼
  ┌───────────┐
  │Consolidator│ ──── Group similar recommendations
  └─────┬─────┘
        │
        ▼
  ┌────────────────┐
  │Review Pipeline │ ──── Pre-screen before Conclave
  └───────┬────────┘
          │
          ▼
  ┌─────────┐
  │Conclave │ ──── Vote on recommendations (PASS/FAIL)
  └─────────┘
       │
       └──────► (back to Discovery if more debate)
```

This loop handles ideas that emerged during debate but haven't been formally approved.

### Wheel 2: Execution Loop (needs entry point)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LOOP                                       │
│                    (mandates become reality)                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  Conclave PASS
       │
       ▼
  ┌──────────┐
  │ Clerk/   │ ──── Record mandate in ledger, assign ID
  │Registrar │
  └────┬─────┘
       │
       ▼ (ratified_mandate.json)
  ┌──────────────────┐
  │Executive Pipeline│ ──── Transform mandate into Epics
  └────────┬─────────┘
           │
           ▼
  ┌────────────────────────┐
  │Administrative Pipeline │ ──── Resource allocation, tactics
  └────────────┬───────────┘
               │
               ▼
  ┌─────────────┐
  │Earl Tasking │ ──── Work execution
  └─────────────┘
```

### The Missing Piece: Clerk/Registrar

After Conclave, we only have a transcript. We need a step that:

1. **Extracts passed motions** from the vote record (not LLM - deterministic)
2. **Records in Motion Ledger** (persistent historical record)
3. **Assigns Mandate ID** (canonical reference for traceability)
4. **Creates handoff artifact** (input to Executive Pipeline)

#### Option A: Conclave Emits Directly

Conclave already knows what passed. It could emit `passed_motions.json`:

```json
{
  "session_id": "conclave-20240127",
  "passed_motions": [
    {
      "motion_id": "m-123",
      "title": "Establish AI Ethics Committee",
      "text": "WHEREAS... BE IT RESOLVED...",
      "motion_type": "policy",
      "vote_result": { "ayes": 48, "nays": 12, "passed": true }
    }
  ]
}
```

**Pros**: Simple, no new component
**Cons**: No ledger, no canonical mandate ID, transient artifact

#### Option B: Secretary "Clerk Mode"

Add `--clerk` flag to Secretary that:
- Parses transcript for PASSED motions (deterministic, not LLM)
- Records in ledger
- Emits `ratified_mandate.json`

```bash
python scripts/run_secretary.py <transcript> --clerk
```

**Pros**: Reuses existing infrastructure
**Cons**: Conflates two concerns (discovery vs. recording)

#### Option C: Separate Registrar Step (Recommended)

New script: `scripts/run_registrar.py`

```bash
python scripts/run_registrar.py _bmad-output/conclave/<session>
```

Responsibilities:
1. Read Conclave output (transcript + vote records)
2. Extract all PASSED motions
3. Assign canonical Mandate IDs (`mandate-<uuid>`)
4. Record in Motion Ledger (`_bmad-output/motion-ledger/`)
5. Emit `ratified_mandates.json` for Executive consumption

```json
{
  "schema_version": "1.0",
  "recorded_at": "ISO8601",
  "conclave_session_id": "conclave-20240127",
  "mandates": [
    {
      "mandate_id": "mandate-a1b2c3d4",
      "motion_id": "m-123",
      "title": "Establish AI Ethics Committee",
      "text": "WHEREAS... BE IT RESOLVED...",
      "motion_type": "policy",
      "passed_at": "ISO8601",
      "vote_result": {
        "ayes": 48,
        "nays": 12,
        "abstentions": 12,
        "threshold": "supermajority",
        "threshold_met": true
      },
      "proposer": { "id": "...", "name": "Paimon" },
      "seconder": { "id": "...", "name": "Bael" },
      "ledger_entry_id": "ledger-xyz789"
    }
  ]
}
```

#### Motion Ledger Structure

```
_bmad-output/motion-ledger/
├── ledger.json              # Index of all recorded mandates
├── mandates/
│   ├── mandate-a1b2c3d4.json
│   ├── mandate-e5f6g7h8.json
│   └── ...
└── archive/
    └── 2024/
        └── Q1/
            └── ...
```

The ledger provides:
- **Immutable record** of constitutional decisions
- **Historical tracking** across sessions
- **Audit trail** for governance
- **Canonical IDs** for downstream traceability

### Updated Full Pipeline

```bash
# Wheel 1: Discovery (emergent recommendations)
python scripts/run_secretary.py <transcript> --enhanced
python scripts/run_consolidator.py
python scripts/run_review_pipeline.py --real-agent
# → outputs go to Motion Queue for next Conclave

# Conclave (both wheels start here)
python scripts/run_conclave.py

# Wheel 2: Execution (mandates)
python scripts/run_registrar.py _bmad-output/conclave/<session>
python scripts/run_executive_pipeline.py --from-ledger
python scripts/run_administrative_pipeline.py
# → outputs go to Earl tasking
```

### Traceability Chain

```
Motion Text → Conclave Vote → Mandate ID → Epic ID → Work Package ID → Task ID
     ↑              ↑              ↑           ↑            ↑            ↑
   Input        Decision       Record      Planning    Resources     Execution
```

Every Epic traces back to a Mandate ID, which traces back to a Conclave vote.
