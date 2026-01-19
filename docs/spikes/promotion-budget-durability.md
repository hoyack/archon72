Promotion Budget Durability and Atomicity Specification
Scope

Hardens the King promotion budget so the per-cycle ceiling holds under:

process restart / service reinstantiation

concurrent promotion attempts

(optionally) horizontal scaling

This spec does not change Motion/Seed semantics.

P1 — PromotionBudgetTracker Interface (Stable Contract)
Requirement

The PromotionService MUST depend on an injected PromotionBudgetTracker abstraction, not a concrete in-memory counter.

Interface

can_promote(king_id: str, cycle_id: str) -> bool

consume(king_id: str, cycle_id: str) -> None

Invariant

A promotion attempt MUST only succeed if the tracker performs an atomic “check+consume” effect (see P3).

P2 — File-backed Budget Store (MVP Persistence)
Requirement

Provide a file-backed implementation that persists consumption per (cycle_id, king_id) such that restarts cannot reset budget usage.

Storage layout

Path pattern: /_bmad-output/budget-ledger/{cycle_id}/{king_id}.json

Write semantics

Must be append-only in effect (history never decreases).

Must be crash-safe:

write temp file

fsync

atomic rename() into place

Read semantics

On startup or first access, can_promote and consume MUST reflect prior consumed counts for that (cycle_id, king_id).

Acceptance criteria

Spend 3 promotions → restart process → a 4th promotion in same (cycle_id, king_id) is denied.

No state reset is possible without deleting the ledger directory (which must be treated as an explicit breach / out-of-band action if you want to formalize it later).

P3 — Atomicity Under Concurrency (Non-Negotiable)
Requirement

Budget consumption MUST be atomic: under concurrent promotion attempts, exactly N promotions succeed for budget N.

MVP atomicity options

Single-node file store:

Use a lock primitive:

lockfile via os.open(..., O_CREAT | O_EXCL); retry/backoff; release on completion

or fcntl-based lock (platform dependent)

Redis store (for scale):

Use atomic increment:

INCR on key (cycle_id, king_id) with budget compare

or Lua script to atomically “increment if below budget”

Acceptance criteria (tripwire)

With budget=3:

spawn 10 concurrent promotion attempts for same (cycle_id, king_id)

exactly 3 succeed, 7 fail with PROMOTION_BUDGET_EXCEEDED

P4 — Redis Budget Store (Scale Path)
Requirement

Provide a Redis-backed tracker with the same interface as file store.

Behavior

Must enforce atomic check+consume.

Keys must be namespaced:

motion_gates:budget:{cycle_id}:{king_id}

Acceptance criteria

Same as P3, using Redis store.

P5 — Promotion Budget Configuration (Policy Knob)
Requirement

Expose promotion budget as a configurable governance parameter (not hardcoded).

Configuration surface

A config file or env-backed policy (example shape):

motion_gates:
  promotion_budget_per_king: 3
  cross_realm_escalation_threshold: 3   # 4+ requires escalation marker

Acceptance criteria

Changing promotion_budget_per_king changes observed ceiling without code changes.

The system reports the effective budget in logs/events when enforcing denials.

P6 — “Target Agenda Capacity” Is a Separate Policy Metric
Requirement

If you choose to include target_agenda_capacity, it MUST NOT affect admission/promotion semantics by default. It is an agenda planning metric, not a gate.

Rationale

This avoids reintroducing a hidden prioritization layer that can be mistaken for admission control.

(If later you want it to shape scheduling quotas, that’s a separate spec in agenda policy—not Motion Gates.)