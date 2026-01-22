# Ratification Proposal (Fixing “0 Ratified” in Review Pipeline)

## Summary

The current review pipeline ratification logic makes it **too easy to produce “0 ratified”**, even when the review outcomes strongly indicate “approve with amendments”.

This proposal changes ratification into a **two-stage decision**:

1. **Acceptance**: “Do we have enough support to continue?” (PASS or PASS-WITH-AMENDMENTS)
2. **Final ratification**: only after amendments are synthesized and re-reviewed

It also fixes a core mismatch: the pipeline currently assigns reviews mainly to **gap archons**, but ratification uses an absolute **37-yea threshold** while counting **only explicit `endorse` responses as yeas** (and counting `amend` as abstain). This makes ratification effectively impossible in common cases.

---

## Background (Observed Failure Mode)

In the latest run (`_bmad-output/review-pipeline/f85ba62f-bf7a-4d53-adfa-b953cc6a4aaf/`):

- Reviews were real-agent (`audit_trail.json`: `using_real_agent: true`)
- Stance distribution: `amend` dominated (~65%), then `endorse`, then `abstain`, then `oppose`
- Ratification required `threshold_required=37` (simple majority of 72) for every motion
- Ratification counted only:
  - `endorse` → yea
  - `oppose` → nay
  - `amend` + `abstain` → abstention

Result: **0 ratified, 17 rejected**, despite high “amend” activity indicating “approve but revise”.

Separately, assignments are not “all-Archon votes”; they are targeted (primarily gap-archon review). So a 37-yea absolute threshold is misaligned with the electorate that actually reviewed the motion.

---

## Design Goals

1. **Avoid impossible thresholds** (don’t require 37 yeas from a subset of reviewers).
2. **Treat “AMEND” as supportive-but-not-final**, not as a pure abstention that guarantees rejection.
3. **Preserve auditability**: every decision should be explainable with counts, thresholds, and the list of Archon stances.
4. **Preserve legitimacy**: avoid “ratify with only a handful of votes”.
5. **Stay compatible with current artifacts** (`review_packets`, `aggregations.json`, `ratification_results.json`), by extending rather than replacing where possible.

---

## Proposed Solution

### A) Separate “Acceptance” from “Final Ratification”

Introduce a new motion-level outcome in the review pipeline result model (names flexible):

- `accepted_with_amendments` (or `needs_amendment_synthesis`)

Rule of thumb:
- If a motion has enough support to proceed but many Archons request amendments, it should **not be rejected**. It should be **accepted with amendments** and routed to synthesis + re-review.

### B) Count “Implicit Endorsements” as Votes (optional but recommended)

The pipeline already distinguishes:
- **contributing archons** (implicit supporters / originators), and
- **gap archons** (assigned for review),
and even writes `already_endorsed` in review packets.

Ratification should not ignore those implicit supporters entirely. Two safe options:

1) **Baseline implicit votes (recommended):**
   - Initialize `votes_by_archon` with `endorse` for each `contributing_archon`
   - Then overlay explicit review responses from gap archons
   - Any explicit stance overrides implicit

2) **No implicit baseline (minimal change):**
   - Keep current “only explicit responses count”
   - But change thresholds to be based on **responses/quorum**, not 72

Option (1) keeps the “72-member body” framing while still allowing targeted review assignments.

### C) Replace Absolute “37 Yeas” with a Quorum + Threshold on Eligible Votes

Add two ratification concepts:

- **Quorum requirement**: minimum number of *eligible votes* required to make a binding decision.
- **Pass threshold**: majority or supermajority of eligible votes.

Definitions:
- `eligible_votes = yeas + nays + amends` (exclude abstentions/no-response from eligibility)
- `responses = yeas + nays + amends + abstentions`

Recommended defaults:
- `QUORUM_ELIGIBLE_SIMPLE = 36` (half of 72)
- `QUORUM_ELIGIBLE_CONSTITUTIONAL = 48` (2/3 of 72)

Thresholds:
- Simple majority: `required = floor(eligible_votes/2) + 1`
- Constitutional: `required = ceil((2/3) * eligible_votes)`

This preserves legitimacy while adapting to “who actually engaged”.

### D) Treat “AMEND” as Support for Acceptance, Not for Final Ratification

Split the decision into:

1) **Acceptance decision** (pre-synthesis):
   - `support = yeas + amends`
   - If `eligible_votes` meets quorum and `support >= required`:
     - If `amends` is “small”: motion is `ratified`
     - Else: motion is `accepted_with_amendments`
   - Else: motion is `rejected` or `deferred` (if quorum not met)

2) **Final ratification** (post-synthesis):
   - After synthesizing amendments into a revised motion text, re-run targeted review/ratification.
   - In the final vote:
     - Require `amends == 0` (or below a very small tolerance)
     - Apply the same quorum + threshold logic on eligible votes

Suggested “amendments are small” criterion:
- `amends <= 0.10 * eligible_votes` (10%), OR
- `amends <= 5` (absolute cap), OR
- `amends <= min(5, 0.10 * eligible_votes)`

### E) Use Panel Deliberation as a Tie-breaker, Not a Override

For contested motions that trigger panel deliberation:
- Panel output can:
  - recommend `pass | fail | amend | defer`
  - provide revised text
  - provide rationale

But final acceptance/ratification should still be driven by counted votes, with panel output used to:
- select the best amendment synthesis path, and/or
- resolve “close calls” when support is near threshold.

---

## Proposed Algorithm (Concrete)

Inputs:
- `responses_by_motion` (explicit `ReviewResponse`s)
- `triage` (contains `contributing_archons` / `gap_archons`)
- optional `panel_deliberation` result

1) Build `votes_by_archon`:
- Optionally prefill `endorse` for contributing archons
- Apply explicit responses (override any prefill)
- Unseen archons are `no_response`

2) Count:
- `yeas = count(endorse)`
- `nays = count(oppose)`
- `amends = count(amend)`
- `abstentions = count(abstain) + count(no_response)`
- `eligible_votes = yeas + nays + amends`

3) Check quorum:
- If constitutional: require `eligible_votes >= QUORUM_ELIGIBLE_CONSTITUTIONAL`
- Else: require `eligible_votes >= QUORUM_ELIGIBLE_SIMPLE`
- If not met: `deferred` (and schedule additional reviews)

4) Determine required support threshold:
- Simple: `required = floor(eligible_votes/2) + 1`
- Constitutional: `required = ceil((2/3)*eligible_votes)`

5) Determine outcome:
- If `yeas >= required` AND `amends <= AMEND_TOLERANCE`: `ratified`
- Else if `(yeas + amends) >= required`: `accepted_with_amendments`
- Else: `rejected`

6) If `accepted_with_amendments`:
- Run amendment synthesis (LLM or deterministic merge) into a revised motion text
- Re-run a second targeted review (or panel) and then re-run steps 1–5 on the revised text

---

## Data Model / Artifact Changes (Auditable)

### `ratification_results.json`

Extend each entry to include:
- `amends` (count)
- `eligible_votes` (count)
- `quorum_required` (number)
- `quorum_met` (bool)
- `support_total` = `yeas + amends`
- `support_required` = `required`
- `outcome` extended to allow `accepted_with_amendments` (or similar)

Keep existing fields for backward compatibility.

### `pipeline_result.json`

Add a section that records:
- which motions entered amendment synthesis
- which motions were re-reviewed (and the revision ID)

### Audit trail (`audit_trail.json`)

Add events:
- `ratification_quorum_failed` (motion_id, eligible_votes, required_quorum)
- `accepted_with_amendments` (motion_id, yeas, amends, required, tolerance)
- `amendment_synthesis_completed` (motion_id, amendment_count, revision_id)
- `final_ratification_completed` (motion_id, outcome)

---

## Implementation Touchpoints (Where This Would Change Code)

Primary location:
- `src/application/services/motion_review_service.py`
  - `derive_ratification_from_reviews(...)` (current core logic)

Likely additional work:
- Introduce an “amendment synthesis” phase (or reuse existing synthesis utilities if present)
- Update domain enums if `RatificationOutcome` is currently only `ratified|rejected|deferred`
- Ensure `save_results(...)` writes extended fields

Config knobs (suggested; env or YAML):
- `REVIEW_RATIFICATION_QUORUM_SIMPLE` (default 36)
- `REVIEW_RATIFICATION_QUORUM_CONSTITUTIONAL` (default 48)
- `REVIEW_AMEND_TOLERANCE_RATIO` (default 0.10)
- `REVIEW_AMEND_TOLERANCE_ABS` (default 5)

---

## Why This Fix Works

- It aligns the ratification rule with how the pipeline actually gathers votes (targeted review, not always 72 direct votes).
- It prevents “AMEND-heavy” results from being treated as rejections.
- It makes “pass-with-amendments” a first-class outcome, enabling the system to converge toward ratifiable text.
- It produces auditable artifacts that explain every outcome with explicit counts and thresholds.

---

## Recommended Rollout

1) Implement quorum + threshold-on-eligible-votes (minimal correctness fix).
2) Add `accepted_with_amendments` outcome + record `amends` / `eligible_votes` in outputs.
3) Add amendment synthesis + second pass review (completes the convergence loop).
4) Optionally add implicit baseline endorsements from `contributing_archons` (improves legitimacy in targeted-review setups).

