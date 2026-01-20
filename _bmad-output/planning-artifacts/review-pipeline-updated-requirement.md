# Review Pipeline Ratification: Updated Requirement

## Context
The current review pipeline uses `simulate_ratification()` for Phase 6. This produces fixed vote counts (e.g., 38/28/6) across all motions, which is why the ratification distribution is identical in `_bmad-output/review-pipeline/*/ratification_results.json` even when `--real-agent` is used.

The real agent path already collects actual review responses, but they are only aggregated and never used for ratification, and the raw responses are not serialized in `pipeline_result.json`.

## Goal
Replace simulated ratification counts with counts derived from actual per-archon review responses when `--real-agent` is enabled.

## Proposed Fix (Option 1)
Use the collected `ReviewResponse` records to compute ratification votes per motion. This requires two changes:

1. **Persist review responses in the pipeline output**
   - Extend `ReviewPipelineResult.to_dict()` to include `review_responses` (or a compact, per-motion vote ledger) so downstream phases and artifacts can reference real votes.
   - Output should be deterministic and traceable: each response should include `archon_id`, `archon_name`, `mega_motion_id`, `stance`, and `confidence`.

2. **Replace simulated ratification with real counts**
   - Introduce a new `derive_ratification_from_reviews()` function that groups `ReviewResponse` by `mega_motion_id` and computes:
     - `yeas` = count of `ReviewStance.ENDORSE`
     - `nays` = count of `ReviewStance.OPPOSE`
     - `abstentions` = count of `ReviewStance.ABSTAIN`
     - `no_response` = assignments expected for the motion minus responses
   - Define how to treat `ReviewStance.AMEND` in ratification:
     - **Recommended**: count as `abstention` (since it signals “conditional support”), but record amendment text separately.
     - Alternative: treat as `nay` for constitutional thresholds (stricter), and `abstention` otherwise.
   - Use the existing threshold rules:
     - constitutional => `SUPERMAJORITY` (48/72)
     - non-constitutional => `SIMPLE_MAJORITY` (37/72)

## Acceptance Criteria
- When `--real-agent` is used, ratification counts must differ across motions if review responses differ.
- `ratification_results.json` should reflect actual per-motion vote totals derived from responses.
- `pipeline_result.json` should include review-response data or a derived vote ledger sufficient to audit ratification.
- When `--real-agent` is not used, the simulation path may remain unchanged.

## Touch Points
- `src/application/services/motion_review_service.py`
  - Replace `simulate_ratification()` call in Phase 6 with a real-response derived method when `use_real_agent` is true.
- `src/domain/models/review_pipeline.py`
  - Extend serialization to include review responses (or per-motion vote ledger) in `to_dict()`.
- Optional: add a unit test that validates ratification vote counts match response counts for a controlled fixture.

## Notes
- The current aggregation output already includes `endorsements`, `oppositions`, `abstentions`, and `no_response` per motion. If we want to avoid serializing raw responses, we can derive ratification directly from these aggregation fields instead, but that would not support per-archon auditability.
