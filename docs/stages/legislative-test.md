# Legislative Pipeline End-to-End Test Report

**Date:** 2026-01-31
**Test Script:** `tests/chaos/legislative-test.sh`
**Motion:** "Establish Mandatory Structured Debate Summaries for All Conclave Sessions"

## Pre-Test Setup

### Findings Resolved Before Test Run

**High findings fixed:**
1. **Circular completion bridge** - Added `import_from_ratification()` to `MotionQueueService` and bridge step in `run_full_pipeline.sh` between Review (stage 4) and Conclave 2 (stage 5). Ratified mega-motions are now imported into the active queue as ENDORSED entries.
2. **Stranded PROMOTED recovery** - Added `recover_stranded_promoted()` to `MotionQueueService` and preflight recovery step in `run_full_pipeline.sh`. PROMOTED motions from failed prior runs are reverted to PENDING.

**Medium findings fixed:**
1. **Quick mode timeout** - `run_full_pipeline.sh` now conditionally sets `AGENT_TIMEOUT_SECONDS=60` in quick mode (was always 180).
2. **Queue selection docs** - Fixed sort description (endorsement count, archon count, consensus level - no creation date tiebreaker). Fixed dedup description (source_cluster_id, not title similarity).
3. **Consolidator filenames** - Updated docs to match actual outputs: `deferred-novel-proposals.json`, `mega-motions.md`, `merge-audit.json`, `traceability-matrix.md`, etc.
4. **Review pipeline filenames** - Updated docs to match actual outputs: `review_packets/{archon_id}.json` directory, `aggregations.json`, `panel_deliberations/{panel_id}.json` directory, `pipeline_result.json`, `audit_trail.json`.

**Low findings fixed:**
- Checkpoint filename pattern: `checkpoint-{session_id}-{timestamp}.json`
- Aggregation threshold: "75% endorsement" (not "2-of-3 supermajority")
- Motion lifecycle: Added MERGED status, clarified archive behavior

### Open Questions Answered

1. **Is Conclave 2 meant to vote on review outputs?** Yes - the bridge step now imports ratified mega-motions into the queue for Conclave 2 to debate and vote on.
2. **Should PROMOTED motions auto-revert?** Yes - `recover_stranded_promoted()` runs at pipeline start and reverts all PROMOTED motions to PENDING.
3. **Is --quick a dev smoke test?** Yes - quick mode is a dev/test path with 60s timeouts, 1 debate round, and 2 max queue items.
4. **Should deferred novel proposals be included by default?** No - they are opt-in via `--include-deferred` and intentionally staged for a separate lane.

### Queue State

- Motion queue cleared to 0 motions before test
- Single motion injected directly via `--motion-file` (bypasses queue)

---

## Stage 1: Conclave (Initial Debate)

**Status:** COMPLETED
**Command:** `PYTHONUNBUFFERED=1 AGENT_TIMEOUT_SECONDS=180 AGENT_TIMEOUT_MAX_ATTEMPTS=5 poetry run python scripts/run_conclave.py --voting-concurrency 3 --debate-rounds 3 --no-queue --no-blockers --motion "Establish Mandatory Structured Debate Summaries" --motion-file _bmad-output/motions/legislative-test-motion.md --motion-type policy`

### Results

| Metric | Value |
|--------|-------|
| Session ID | `0249c2df-1917-453e-a62c-da7641de63dd` |
| Session Name | `conclave-20260131-083343` |
| Duration | 100.1 minutes |
| Archons Present | 72/72 |
| Debate Rounds | 3 |
| Transcript Entries | 358 |

### Vote Outcome: **FAILED**

| Vote | Count |
|------|-------|
| AYE | 19 |
| NAY | 43 |
| ABSTAIN | 10 |
| **Total** | **72** |
| Threshold | Supermajority |
| Threshold Met | No |

**Proposer:** Asmoday
**Seconder:** Bael

### Key Observations

1. **Strong opposition (59.7% NAY)** - The motion was heavily rejected. Despite being a procedural improvement with "no new authority," the Conclave overwhelmingly voted against mandatory structured debate summaries.

2. **10 abstentions** - Several abstentions came from archons using `deepseek-v3.1:671b-cloud` which consistently returned Internal Server Errors from Ollama Cloud. Affected archons: Vine, Cimeies, Bifrons, Stolas (all recorded as ABSTAIN due to LLM failure, not deliberate abstention).

3. **Stance/vote divergences detected** - The system flagged several archons who changed their vote from their declared debate stance:
   - Botis: AGAINST → AYE (acknowledged with reason)
   - Vassago: AGAINST → AYE (acknowledged with reason)
   - Furfur: AGAINST → AYE (unexplained)
   - Bifrons: AGAINST → ABSTAIN (unexplained, LLM failure)
   - Stolas: AGAINST → ABSTAIN (unexplained, LLM failure)

4. **Model failures** - `deepseek-v3.1:671b-cloud` consistently failed with "Internal Server Error" throughout all phases (debate and voting). This is a cloud-side issue, not a code bug. The retry mechanism (5 attempts with backoff) correctly exhausted retries and recorded ABSTAIN.

### Output Files

- Transcript: `_bmad-output/conclave/transcript-0249c2df-1917-453e-a62c-da7641de63dd-20260131-101347.md`
- Results: `_bmad-output/conclave/conclave-results-0249c2df-1917-453e-a62c-da7641de63dd-20260131-101347.json`
- Checkpoint: `_bmad-output/conclave/checkpoint-0249c2df-1917-453e-a62c-da7641de63dd-20260131-101347.json`
- Log: `_bmad-output/legislative-test/conclave1_direct.log` (2233 lines)

---

## Stage 2: Secretary (Extract Recommendations)

**Status:** COMPLETED
**Command:** `poetry run python scripts/run_secretary.py <transcript> --enhanced --verbose`

### Results

| Metric | Value |
|--------|-------|
| Report ID | `556877aa-9872-4e9c-aa73-3b34ccb8aa7b` |
| Processing Duration | 1716.7s (~28.6 minutes) |
| Speeches Analyzed | 225 |
| Recommendations Extracted | 999 |
| Clusters Formed | 124 |
| Motions Queued | 69 |

### Recommendations by Category

| Category | Count |
|----------|-------|
| amend | 280 |
| implement | 242 |
| establish | 164 |
| review | 112 |
| mandate | 75 |
| other | 57 |
| investigate | 35 |
| pilot | 32 |
| educate | 2 |

### Clusters by Consensus Level

| Level | Count |
|-------|-------|
| single (1 archon) | 55 |
| low (2-4 archons) | 38 |
| medium (5-9) | 12 |
| critical (10+) | 12 |
| high (10+) | 7 |

### Top 5 Motions by Archon Support

1. **[65 archons]** Motion to Establish Independent Verification Protocols for Summary Accuracy
2. **[48 archons]** Motion to Decouple Adjournment Authority
3. **[42 archons]** Motion to Establish Machine-Readable Witnessed Artifacts for Validation
4. **[29 archons]** Motion to Reconsider Adjournment Requirements and Time-Boxed Generation
5. **[25 archons]** Motion to Establish Emergency Override Protocols with Service Level Agreements

### Key Observations

1. **999 raw recommendations** extracted from 225 speeches across 3 debate rounds - substantial output from a single-motion debate.
2. **69 motions synthesized** from 124 clusters - the clustering/dedup reduced nearly 1000 recommendations into actionable motions.
3. **Dominant category: "amend" (280)** - Most recommendations suggested amendments to the original motion rather than new initiatives, consistent with the NAY-heavy vote.
4. **Strong consensus items** - Top motion had 65 archon support (90% of the Conclave), suggesting near-universal agreement on needing verification protocols even while rejecting the original motion.
5. **Queue populated** - 69 motions added to the active queue, all with `pending` status.

### Output Files

- Secretary Report: `_bmad-output/secretary/0249c2df-1917-453e-a62c-da7641de63dd/secretary-report.json`
- Recommendations: `_bmad-output/secretary/0249c2df-1917-453e-a62c-da7641de63dd/recommendations.json` (787 KB)
- Motion Queue: `_bmad-output/secretary/0249c2df-1917-453e-a62c-da7641de63dd/motion-queue.json`
- Motion Queue (readable): `_bmad-output/secretary/0249c2df-1917-453e-a62c-da7641de63dd/motion-queue.md`
- Recommendations Register: `_bmad-output/secretary/0249c2df-1917-453e-a62c-da7641de63dd/recommendations-register.md`
- Log: `_bmad-output/legislative-test/secretary_direct.log` (94,355 lines)

---

## Stage 3: Consolidator (Merge into Mega-Motions)

**Status:** COMPLETED
**Command:** `poetry run python scripts/run_consolidator.py --verbose`

### Results

| Metric | Value |
|--------|-------|
| Input Motions | 69 |
| Input Recommendations | 999 |
| Mega-Motions Produced | 22 |
| Novel Proposals Deferred | 10 (from deferred-novel-proposals.json) |
| Key Themes | 7 |

### Mega-Motions (Top 10 by Archon Support)

| # | Title | Archons | Sources |
|---|-------|---------|---------|
| 1 | Comprehensive Verification and Validation Framework | 70 | 3 |
| 2 | Comprehensive Governance Framework for Implementation | 50 | 8 |
| 3 | Comprehensive Framework for Authority Delimitation | 36 | 10 |
| 4 | Comprehensive Review of Procedural Safeguards | 35 | 3 |
| 5 | Comprehensive Security Enhancement and Access Control | 32 | 5 |
| 6 | Comprehensive Knowledge Management Framework | 18 | 3 |
| 7 | Operational Efficiency Through Administrative Streamlining | 13 | 2 |
| 8 | Comprehensive Risk Management Framework | 9 | 5 |
| 9 | Rejection of Mandated Documentation Structures | 5 | 2 |
| 10 | Implementation Approach for Alternative Decision Capture | 3 | 1 |

### Key Themes Identified

- Structured Documentation
- Verification Mechanisms
- Scope Limitations
- Review Processes
- Accountability and Transparency
- Institutional Knowledge
- Risk Management

### Areas of Consensus

- Implementation of mandatory machine-readable structured summaries
- Inclusion of a witnessed verification step for summary accuracy
- Establishment of a three-cycle review process
- Limitation of scope to formal sessions only
- Use of summaries as tools for institutional memory and training

### Points of Contention

- Level of access control and anonymity for dissenting opinions
- Sunset provisions (automatic sunset vs. regular review)
- Extent of pedagogical application (living curriculum vs. basic training)

### Key Observations

1. **69 → 22 mega-motions** - Effective consolidation ratio of 3.1:1, merging related motions into coherent mega-motions.
2. **Top mega-motion has 70 archon support** - "Comprehensive Verification and Validation Framework" consolidated verification-related motions with near-universal support.
3. **10 novel proposals deferred** - Creative/unconventional ideas (e.g., geometric virtue framework, ritual artifacts) were correctly identified and deferred for separate consideration.
4. **Interesting dissent motion** - "Rejection of Mandated Documentation Structures" (5 archons) was preserved as a mega-motion, showing the consolidator respects minority opposition.

### Output Files

- Mega-Motions: `_bmad-output/consolidator/0249c2df-.../mega-motions.json` (68 KB)
- Mega-Motions (readable): `_bmad-output/consolidator/0249c2df-.../mega-motions.md` (53 KB)
- Deferred Proposals: `_bmad-output/consolidator/0249c2df-.../deferred-novel-proposals.json`
- Conclave Summary: `_bmad-output/consolidator/0249c2df-.../conclave-summary.json`
- Traceability Matrix: `_bmad-output/consolidator/0249c2df-.../traceability-matrix.md`
- Acronym Registry: `_bmad-output/consolidator/0249c2df-.../acronym-registry.json`
- Index: `_bmad-output/consolidator/0249c2df-.../index.md`
- Log: `_bmad-output/legislative-test/consolidator_direct.log` (17,394 lines)

---

## Stage 4: Review Pipeline (Triage & Ratification)

**Status:** COMPLETED
**Command:** `poetry run python scripts/run_review_pipeline.py --real-agent --verbose`

### Results

| Metric | Value |
|--------|-------|
| Mega-Motions Reviewed | 22 |
| Total Review Assignments | 1,098 |
| Avg Reviews per Archon | 15.25 |
| Individual Reviews Completed | 980 |
| Triage Risk Breakdown | 15 high, 4 medium, 3 low |
| Consensus Motions | 6 |
| Contested Motions | 2 |
| Panels Convened | 2 |
| Duration | ~3.25 hours (10:57 → 14:12) |

### Ratification Outcomes

| Outcome | Count |
|---------|-------|
| Ratified | 20 |
| Accepted with Amendments | 18 |
| Deferred | 1 |
| Rejected | 1 |
| **Total Votes** | **40** |

### Key Ratified Mega-Motions

| Title | Initial Vote | Final Vote |
|-------|-------------|------------|
| Comprehensive Verification and Validation Framework | 70Y/0N/0A | 70Y/0N/0A |
| Comprehensive Governance Framework | 50Y/0N/0A | - |
| Quality Assurance and Implementation Safeguards | 47Y/0N/6A | 66Y/0N/6A |
| Comprehensive Operational Resilience Framework | 54Y/0N/6A | 66Y/0N/6A |
| Quality Control & Delivery Standards | 41Y/1N/4A | 67Y/1N/4A |
| Establishment of Objective Criteria | 47Y/2N/3A | 67Y/2N/3A |
| Rollback & Revision Mechanisms | 34Y/2N/3A | 67Y/2N/3A |

### Key Observations

1. **95% ratification rate** (38/40 votes were ratified or accepted with amendments) - The review pipeline strongly endorsed the Consolidator's mega-motions.
2. **Amendment synthesis worked** - 18 motions were accepted with amendments, showing the pipeline's ability to incorporate reviewer feedback and re-vote.
3. **Only 1 rejection** - "Process Efficiency and Sunset Provisions" (21Y/4N/10A) failed to meet simple majority, suggesting the Conclave found the sunset clause provisions insufficient.
4. **1 deferral** - One motion was deferred for further consideration.
5. **1,098 review assignments** - Each of the 72 archons reviewed ~15 mega-motions, with 980 successful completions (89% success rate, ~118 failures from LLM errors).
6. **Triage correctly identified risk levels** - 15/22 mega-motions flagged as high-risk, triggering more thorough review panels.
7. **2 crew failures** observed but pipeline recovered and continued - resilient error handling.
8. **deepseek-v3.1:671b-cloud** continued to fail consistently, accounting for most review failures.

### Output Files

- Pipeline Result: `_bmad-output/review-pipeline/0249c2df-.../pipeline_result.json` (3.8 MB)
- Ratification Results: `_bmad-output/review-pipeline/0249c2df-.../ratification_results.json` (475 KB)
- Aggregations: `_bmad-output/review-pipeline/0249c2df-.../aggregations.json` (537 KB)
- Triage Results: `_bmad-output/review-pipeline/0249c2df-.../triage_results.json` (40 KB)
- Audit Trail: `_bmad-output/review-pipeline/0249c2df-.../audit_trail.json` (17 KB)
- Review Packets: `_bmad-output/review-pipeline/0249c2df-.../review_packets/`
- Panel Deliberations: `_bmad-output/review-pipeline/0249c2df-.../panel_deliberations/`
- Log: `_bmad-output/legislative-test/review_direct.log` (278,027 lines)

---

## Stage 5: Bridge + Conclave 2 (Circular Completion)

### Bridge Results

**Status:** COMPLETED

- **Imported:** 21 ratified mega-motions into queue as ENDORSED
- **Queue after bridge:** 90 motions (69 pending + 21 endorsed)
- The bridge correctly called `import_from_ratification()` which matched ratification outcomes to mega-motion content and created new queue entries

### Conclave 2

**Status:** IN PROGRESS

---

## Final Summary

_Will be populated after all stages complete._
