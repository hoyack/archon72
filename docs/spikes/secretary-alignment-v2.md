# Spike: Secretary Pipeline Alignment v2

**Date:** 2026-01-26
**Status:** Analysis Complete
**Author:** Party Mode Analysis (Winston, Murat, Mary + Grand Architect)
**Related:** `docs/spikes/motion-tuning.md`

---

## Executive Summary

The Conclave system has undergone significant changes during stress testing that introduce new transcript elements not currently handled by the Secretary pipeline. This spike identifies all alignment gaps and proposes solutions.

**Key Changes Requiring Alignment:**
1. New procedural entry types: `STANCE_MISSING`, `RED_TEAM_STANCE_MISSING`
2. New metadata field: `stance_explicit` in debate entries
3. Increased vote reasoning limits (500 → 1200 chars)
4. Red team rank diversity (now 5 unique ranks)
5. Enhanced stance/vote divergence tracking

---

## 1. New Transcript Entry Types

### 1.1 STANCE_MISSING Entries

**Format in Transcript:**
```markdown
**[14:24:10] Secretary:**
STANCE_MISSING: Bifrons did not provide an explicit STANCE token; treated as NEUTRAL for tallying.
```

**Current Behavior:** The Secretary service will parse this as a speech from archon "Secretary" because:
- The header pattern `**[HH:MM:SS] Speaker:**` matches
- "Secretary" is not in the skip list (`[system]`, `system`, `execution planner`)
- The content will be searched for recommendations (incorrectly)

**Required Fix:** Add "Secretary" to the invalid speaker list:
```python
def _is_valid_speaker(self, speaker_name: str) -> bool:
    normalized = speaker_name.strip().lower()
    if normalized in {"[system]", "system", "execution planner", "secretary"}:
        return False
    # ...
```

### 1.2 RED_TEAM_STANCE_MISSING Entries

**Format in Transcript:**
```markdown
**[14:56:35] Secretary:**
RED_TEAM_STANCE_MISSING: Amon (red team) did not provide explicit STANCE token; target was AGAINST.
```

**Same Issue:** Parsed as "Secretary" speech.

**Same Fix:** Already covered by adding "secretary" to skip list.

### 1.3 Alternative Fix: Pattern-Based Filtering

Instead of speaker-name filtering, add a content pattern filter:
```python
# Pattern for Secretary procedural notes (skip these)
secretary_procedural = re.compile(
    r"^(STANCE_MISSING|RED_TEAM_STANCE_MISSING|UNEXPLAINED stance):",
    re.IGNORECASE
)

# In speech content validation:
if secretary_procedural.match(speech_content):
    continue  # Skip procedural notes
```

---

## 2. Metadata Alignment

### 2.1 stance_explicit Field

**New Field in Transcript Metadata:**
```json
{
  "round": 1,
  "motion_id": "uuid",
  "position": "for",
  "stance_explicit": true,  // NEW
  "has_violations": false,
  "violation_count": 0
}
```

**Impact on Secretary:**
- The regex extraction uses `_extract_stance()` which parses speech content
- The new metadata is not used (it's in the entry metadata, not content)
- **No immediate action required** - but could be leveraged for validation

**Future Enhancement:** If Secretary gains access to entry metadata (not just markdown content), it could use `stance_explicit` to:
- Weight recommendations differently (explicit stance = higher confidence)
- Track quality of debate contributions
- Generate quality metrics for the report

### 2.2 Consensus Tracking

**New Context in Digests:**
```
**Position Summary:** 180 FOR | 25 AGAINST | 11 NEUTRAL
```

**Current Handling:** Secretary parses debate digests as speeches from the digest archon.

**Recommendation:** Add pattern to extract consensus metrics from digests:
```python
consensus_pattern = re.compile(
    r"\*\*Position Summary:\*\*\s*(\d+)\s*FOR\s*\|\s*(\d+)\s*AGAINST\s*\|\s*(\d+)\s*NEUTRAL"
)
```

This could enhance the `SecretaryReport` with:
- `debate_consensus_trajectory: list[tuple[int, int, int]]` - FOR/AGAINST/NEUTRAL at each digest
- `consensus_shift_analysis: str` - narrative of how consensus evolved

---

## 3. Entry Type Mapping

### 3.1 Current Entry Types in Conclave

| Entry Type | Speaker | Content Pattern | Secretary Action |
|------------|---------|-----------------|------------------|
| `speech` | Archon name | Debate content | **Extract recommendations** |
| `violation_speech` | Archon name | Debate with violations | Extract (with flag) |
| `red_team_speech` | Archon name | Red team argument | Extract (context-aware) |
| `procedural` | `[PROCEDURAL]` | Phase changes, votes | **Skip** |
| `procedural` | `Secretary` | STANCE_MISSING, digests | **Skip** (NEEDS FIX) |
| `motion` | Archon name | Motion intro/second | Capture for context |
| `system` | `[SYSTEM]` | Errors, timeouts | Skip |
| `stance_vote_divergence` | Archon name | Vote explanation | Extract (new source) |

### 3.2 New Entry Types to Handle

| Entry Type | Current Handling | Required Handling |
|------------|------------------|-------------------|
| `STANCE_MISSING` note | Parsed as speech | **Skip** |
| `RED_TEAM_STANCE_MISSING` note | Parsed as speech | **Skip** |
| `Acknowledged stance change` | Parsed as speech | **Extract as recommendation source** |
| `UNEXPLAINED stance/vote divergence` | Parsed as speech | **Flag for conflict detection** |

---

## 4. Debate Digest Handling

### 4.1 Current Behavior

Debate digests are generated every 10 entries and look like:
```markdown
**[12:01:57] Secretary:**
## Debate Digest (Entry 10)

**Position Summary:** 10 FOR | 0 AGAINST | 0 NEUTRAL

**Key FOR Arguments:**
- Establishes essential transparency...
- Strengthens governance legitimacy...

**Key AGAINST Arguments:**
- No substantive opposition arguments were raised

**Notable Concerns Raised:**
- Risk of verification mechanisms becoming de facto decision-making bodies
...

**Structural Risk Analysis (auto-generated):**
  - INTERPRETIVE AUTHORITY: Interpretive power often becomes...
```

### 4.2 Issues

1. **Speaker Confusion:** "Secretary" is parsed as an archon
2. **Content Misinterpretation:** Digest summaries could match recommendation patterns
3. **Risk Analysis Lost:** Structural risks are valuable but not captured

### 4.3 Proposed Enhancement

Add a specialized digest parser:
```python
def _parse_debate_digest(self, content: str) -> DebateDigestSummary:
    """Extract structured data from debate digest entries."""
    return DebateDigestSummary(
        entry_number=self._extract_entry_number(content),
        position_summary=self._extract_position_summary(content),
        key_for_arguments=self._extract_section("Key FOR Arguments", content),
        key_against_arguments=self._extract_section("Key AGAINST Arguments", content),
        notable_concerns=self._extract_section("Notable Concerns Raised", content),
        structural_risks=self._extract_section("Structural Risk Analysis", content),
    )
```

This would enable:
- Tracking debate progression across the session
- Capturing concerns as potential motion amendments
- Using structural risks for conflict detection

---

## 5. Vote Reasoning Changes

### 5.1 Increased Limits

| Field | Old Limit | New Limit |
|-------|-----------|-----------|
| `vote_reasoning` | 500 chars | 1200 chars |
| `stance_change_reason` | 200 chars | 600 chars |

### 5.2 Impact on Secretary

Vote entries are currently skipped:
```python
vote_pattern = re.compile(r"Vote:\s*(?:AYE|NAY|ABSTAIN)", re.IGNORECASE)
```

However, the reasoning that follows could contain valuable recommendations:
```markdown
**[12:52:42] Asmoday:**
Vote: NAY

Acknowledged stance change: Asmoday declared STANCE: FOR during debate but voted NAY.
Reason: Upon careful re-examination, the motion's geometric precision in defining
authority-bearing actions has demonstrated a more coherent architecture of virtue...
```

### 5.3 Proposed Enhancement

Add vote reasoning extraction:
```python
def _extract_vote_reasoning(self, lines: list[str]) -> list[VoteReasoning]:
    """Extract reasoning from vote entries."""
    vote_with_reason = re.compile(
        r"Vote:\s*(AYE|NAY|ABSTAIN)\s*\n\n?(.*?)(?=\n\*\*\[|$)",
        re.IGNORECASE | re.DOTALL
    )
    # ...
```

Vote reasoning could be a source of:
- Amendment suggestions
- Implementation concerns
- Conflict explanations

---

## 6. Red Team Context

### 6.1 Rank Diversity Information

Red team now has 5 unique ranks (fixed in this session). This context could enhance Secretary analysis:
- Weight red team arguments by rank diversity score
- Track if opposition came from diverse perspectives
- Include in motion queue metadata

### 6.2 Red Team Speech Identification

Red team speeches have `is_red_team=True` in the entry metadata, but the markdown shows:
```markdown
**[14:56:35] Amon:**
STANCE: AGAINST
[Argument content...]
```

The Secretary sees this as a normal debate speech. The context is lost.

**Proposed Enhancement:** Track red team context:
```python
# In _parse_speeches, detect red team round marker:
if "RED TEAM ROUND:" in line:
    in_red_team_round = True
    continue

# Mark speeches during red team round
if in_red_team_round:
    speech.is_red_team = True
```

---

## 7. CrewAI Adapter Alignment

### 7.1 Extraction Prompt Updates

The extraction prompt in `secretary_crewai_adapter.py` should be updated to:
1. Ignore Secretary procedural notes
2. Handle STANCE_MISSING context
3. Recognize red team arguments as adversarial (context-aware)

**Current Prompt Gaps:**
```python
# The prompt doesn't mention:
# - Secretary entries should be skipped
# - STANCE_MISSING patterns
# - Red team round context
# - Vote reasoning as a source
```

### 7.2 Proposed Prompt Additions

Add to extraction task prompt:
```
ENTRIES TO SKIP:
- Any entry from speaker "Secretary" (these are procedural notes)
- Entries starting with "STANCE_MISSING:", "RED_TEAM_STANCE_MISSING:", "UNEXPLAINED stance"
- Debate Digest entries (## Debate Digest headers)

SPECIAL CONTEXTS:
- Entries after "RED TEAM ROUND:" marker are adversarial arguments (forced opposition)
- Vote entries (Vote: AYE/NAY/ABSTAIN) may have valuable reasoning after them
- Stance change acknowledgments explain position shifts
```

---

## 8. Recommended Implementation Order

### Phase 1: Critical Fixes (Blocking)

| Priority | Task | Files | Effort |
|----------|------|-------|--------|
| P0 | Add "secretary" to invalid speaker list | `secretary_service.py` | 5 min |
| P0 | Add STANCE_MISSING content pattern filter | `secretary_service.py` | 10 min |
| P0 | Test with new transcript format | Tests | 30 min |

### Phase 2: Enhanced Extraction (Recommended)

| Priority | Task | Files | Effort |
|----------|------|-------|--------|
| P1 | Parse debate digests for consensus tracking | `secretary_service.py` | 2 hrs |
| P1 | Extract vote reasoning | `secretary_service.py` | 1 hr |
| P1 | Update CrewAI prompts | `secretary_crewai_adapter.py` | 1 hr |

### Phase 3: Quality Improvements (Future)

| Priority | Task | Files | Effort |
|----------|------|-------|--------|
| P2 | Track red team context | `secretary_service.py` | 2 hrs |
| P2 | Add stance_explicit to quality metrics | Domain models | 1 hr |
| P2 | Consensus trajectory analysis | `secretary_service.py` | 2 hrs |

---

## 9. Test Cases Needed

### 9.1 New Transcript Patterns

```python
def test_skips_secretary_entries():
    """Secretary procedural notes should not be parsed as speeches."""
    transcript = """
**[14:24:10] Secretary:**
STANCE_MISSING: Bifrons did not provide an explicit STANCE token; treated as NEUTRAL for tallying.

**[14:24:15] Bael:**
STANCE: FOR
I support this motion because...
"""
    speeches = service._parse_speeches(transcript)
    assert len(speeches) == 1
    assert speeches[0].archon_name == "Bael"


def test_skips_red_team_stance_missing():
    """Red team stance missing notes should be skipped."""
    transcript = """
**[14:56:35] Secretary:**
RED_TEAM_STANCE_MISSING: Amon (red team) did not provide explicit STANCE token; target was AGAINST.
"""
    speeches = service._parse_speeches(transcript)
    assert len(speeches) == 0
```

### 9.2 Digest Parsing

```python
def test_parses_debate_digest_position_summary():
    """Debate digest position summaries should be extractable."""
    digest = """
## Debate Digest (Entry 10)

**Position Summary:** 10 FOR | 0 AGAINST | 0 NEUTRAL
"""
    summary = service._parse_debate_digest(digest)
    assert summary.for_count == 10
    assert summary.against_count == 0
```

---

## 10. Files to Modify

| File | Changes |
|------|---------|
| `src/application/services/secretary_service.py` | Add speaker filter, content patterns, digest parsing |
| `src/infrastructure/adapters/external/secretary_crewai_adapter.py` | Update extraction prompts |
| `src/domain/models/secretary.py` | Add DebateDigestSummary, VoteReasoning models |
| `tests/unit/application/services/test_secretary_*.py` | Add new test cases |

---

---

## 11. Critical Issue: Clustering Truncation (Enhanced Mode)

### 11.1 Problem Statement

The enhanced Secretary's clustering step fails catastrophically due to output truncation:

| Metric | Value |
|--------|-------|
| Recommendations extracted | 963 |
| Clustering batch size | 50 |
| Total batches | 20 |
| **Batches truncated** | **19 (95%)** |
| Batches successful | 1 |
| Resulting clusters | 5 (from 13 recs) |

**Impact:** The 3 queued motions only represent the last 13 recommendations (1.3% of the transcript), not the full Conclave deliberation.

### 11.2 Root Cause Analysis

**Math Problem:**
```
Input per batch:
  - 50 recommendations × ~150 tokens each = ~7,500 tokens (input)

Output per batch:
  - Clusters with member_ids (up to 50 UUIDs each)
  - ~500-2000 tokens output needed

Model config (user override):
  - max_tokens = 2000 ← TOO SMALL

Default config (secretary_agent.py):
  - max_tokens = 8192 ← Would work, but was overridden
```

**The user's `SECRETARY_JSON_ARCHON_ID` override has `max_tokens=2000`**, which is insufficient for clustering 50 recommendations.

### 11.3 Evidence

From `logs/secretary.log`:
```
truncated_clustering_response appears 19 times
```

From checkpoints:
```
_bmad-output/secretary/checkpoints/..._03_clustering.json
Only contains themes from last batch: Vepar, Valac, Beleth, Amdusias
```

### 11.4 Proposed Fixes

#### Fix A: Reduce Batch Size (Quick Fix)

```python
# In secretary_crewai_adapter.py
CLUSTERING_BATCH_SIZE = 15  # Was 50
```

**Pros:** Immediate fix, no config changes
**Cons:** More batches = longer processing time

#### Fix B: Require Higher max_tokens for JSON Model

```python
# In SecretaryCrewAIAdapter.__init__
if self._profile.json_llm_config.max_tokens < 4096:
    logger.warning(
        "json_model_max_tokens_too_low",
        current=self._profile.json_llm_config.max_tokens,
        recommended=8192,
    )
```

**Pros:** Catches bad configs early
**Cons:** Doesn't fix the override

#### Fix C: Simplify Clustering Output Format

Current output requires:
```json
{
  "member_ids": ["uuid-1", "uuid-2", ..., "uuid-50"],  // ~1800 chars just for IDs
  "archon_names": ["Bael", "Asmoday", ...]
}
```

Proposed simplified:
```json
{
  "member_indices": [0, 1, 2, 15, 23],  // Just indices into the batch
  "archon_names": ["Bael", "Asmoday"]   // Still needed for attribution
}
```

**Pros:** 10x reduction in output size
**Cons:** Requires refactoring parse logic

#### Fix D: Retry with Smaller Batch on Truncation

```python
async def _cluster_with_retry(
    self,
    recommendations: list[ExtractedRecommendation],
    batch_size: int = CLUSTERING_BATCH_SIZE,
) -> list[RecommendationCluster]:
    """Cluster with automatic retry on truncation."""
    clusters = []
    for batch in batches(recommendations, batch_size):
        result = await self._cluster_batch(batch)
        if result.truncated and batch_size > 10:
            # Retry with smaller batch
            result = await self._cluster_with_retry(batch, batch_size // 2)
        clusters.extend(result.clusters)
    return clusters
```

**Pros:** Self-healing, works with any model
**Cons:** Complexity, longer processing time

#### Fix E: Hierarchical Clustering

1. Cluster each batch of 15 into mini-clusters
2. Collect all mini-cluster representatives
3. Cluster the representatives into final themes

**Pros:** Scales to any transcript size
**Cons:** Most complex to implement

### 11.5 Recommended Fix Order

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| P0 | Reduce batch size to 15 | 1 line | Immediate |
| P1 | Add truncation warning in config | 10 lines | Prevents bad configs |
| P2 | Simplify output format | 2 hrs | Long-term scalability |
| P3 | Retry logic | 1 hr | Robustness |
| P3 | Hierarchical clustering | 4 hrs | Future-proof |

---

## 12. Appendix: Sample Transcript Entries

### A. STANCE_MISSING (New)
```markdown
**[14:24:10] Secretary:**
STANCE_MISSING: Bifrons did not provide an explicit STANCE token; treated as NEUTRAL for tallying.
```

### B. RED_TEAM_STANCE_MISSING (New)
```markdown
**[14:56:35] Secretary:**
RED_TEAM_STANCE_MISSING: Amon (red team) did not provide explicit STANCE token; target was AGAINST.
```

### C. Debate Digest (Existing, needs parsing)
```markdown
**[12:01:57] Secretary:**
## Debate Digest (Entry 10)

**Position Summary:** 10 FOR | 0 AGAINST | 0 NEUTRAL

**Key FOR Arguments:**
- Establishes essential transparency by creating immutable, auditable trails...

**Structural Risk Analysis (auto-generated):**
  - INTERPRETIVE AUTHORITY: Interpretive power often becomes de facto binding...
```

### D. Vote with Reasoning (Existing, underutilized)
```markdown
**[12:52:42] Asmoday:**
Vote: NAY

Acknowledged stance change: Asmoday declared STANCE: FOR during debate but voted NAY.
Reason: Upon careful re-examination, the motion's geometric precision...
```

### E. Red Team Round Marker (Existing)
```markdown
**[14:56:30] [PROCEDURAL]:**
RED TEAM ROUND: Before voting, 5 archons will now steelman the AGAINST position...
```

---

## 13. Re-Run Analysis: Cross-Batch Fragmentation Issue

**Date:** 2026-01-26
**Status:** Issue Identified, Fix Pending

### 13.1 P0 Fix Validation

The batch size reduction (50→15) completely resolved the truncation issue:

| Metric | Before Fix | After Fix |
|--------|------------|-----------|
| Recommendations | 963 | 981 |
| Batches truncated | 19/20 (95%) | **0/65 (0%)** |
| Clusters generated | 5 | **433** |
| Motions queued | 3 | **185** |
| Processing time | ~20 min | ~64 min |

**Verdict:** ✅ Truncation fix validated.

### 13.2 New Issue: Cross-Batch Clustering Fragmentation

With 981 recommendations in ~65 batches of 15, each batch clusters independently. Similar themes appearing in different batches are never merged, creating **significant motion duplication**.

**Observed Pattern:**

| Theme Family | Duplicate Motions | Should Merge To |
|-------------|-------------------|-----------------|
| Attribution/Verifiability | 15+ (Motions 1,3,5,9,11,17,22,25,28,31,33,35,36,41,42) | ~2-3 |
| Authority Definition | 6+ (Motions 4,7,10,20,29,39) | ~1-2 |
| Compliance Clause | 6+ (Motions 23,30,34,37,40,43) | ~1-2 |
| Review Clause | 4+ (Motions 2,12,21,32) | ~1 |
| Security/Compartmentalization | 5+ (Motions 14,19,24,26,28) | ~1-2 |
| Audit Trail/Traceability | 4+ (Motions 6,13,18,31) | ~1 |

**Example Near-Duplicates:**

```
Motion 1:  "Mandate Explicit Authority Attribution" (Asmoday, Bael, Beleth)
Motion 3:  "Mandate Explicit Attribution for Authority-Bearing Acts" (Belial, Paimon)
Motion 5:  "Mandate Explicit Attribution for Authority-Bearing Actions" (Zagan, Agares)
Motion 17: "Mandate Explicit Attribution for State or Authority Alterations" (Crocell, Dantalion, Eligos)
```

These are semantically identical — all mandate explicit attribution — but because they were clustered in different batches, they became 4 separate motions.

**Estimated Redundancy:** 50-60% of 185 motions are near-duplicates.

### 13.3 Root Cause

```
Batch 1:  [Rec A₁, A₂, B₁] → Cluster "Attribution" (Asmoday, Bael, Beleth)
Batch 30: [Rec A₃, A₄, C₁] → Cluster "Attribution" (Zagan, Agares)  ← No merge!
Batch 50: [Rec A₅, A₆, D₁] → Cluster "Attribution" (Crocell, Dantalion, Eligos)  ← No merge!
```

Each batch's "Attribution" cluster becomes a separate motion because there's no cross-batch merge step.

### 13.4 Proposed Fix: Cross-Batch Cluster Consolidation

**Phase 1: Post-Clustering Deduplication**

After all batches are clustered, run a second-pass merge:

```python
async def _consolidate_clusters(
    self,
    clusters: list[RecommendationCluster],
) -> list[RecommendationCluster]:
    """Merge semantically similar clusters from different batches."""

    # Extract cluster summaries for comparison
    summaries = [
        {
            "cluster_id": c.cluster_id,
            "theme": c.theme_label,
            "keywords": c.representative_keywords,
        }
        for c in clusters
    ]

    # Ask LLM to identify mergeable cluster groups
    merge_groups = await self._identify_merge_groups(summaries)

    # Merge clusters within each group
    consolidated = []
    for group in merge_groups:
        if len(group) == 1:
            consolidated.append(clusters[group[0]])
        else:
            merged = self._merge_cluster_group([clusters[i] for i in group])
            consolidated.append(merged)

    return consolidated
```

**Phase 2: Hierarchical Clustering (Future)**

1. Per-batch clustering → mini-clusters
2. Cluster mini-cluster representatives → meta-themes
3. Merge mini-clusters into meta-themes → final clusters

### 13.5 Updated Fix Priority

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| ~~P0~~ | ~~Reduce batch size to 15~~ | ~~1 line~~ | ✅ DONE |
| ~~P1~~ | ~~Add truncation warning~~ | ~~10 lines~~ | ✅ DONE |
| ~~P2~~ | ~~Cross-batch cluster consolidation~~ | ~~2-3 hrs~~ | ✅ DONE |
| P3 | Hierarchical clustering | 4 hrs | Future-proof scalability |
| P4 | Simplify output format | 2 hrs | Long-term optimization |

### 13.8 P2 Implementation Details (Cross-Batch Consolidation)

**Implemented in:** `src/infrastructure/adapters/external/secretary_crewai_adapter.py`

**Algorithm:**

```
Phase 1: Per-batch clustering (existing)
  └── 65 batches of 15 recommendations each
  └── Result: ~433 raw clusters

Phase 2: Cross-batch consolidation (NEW)
  ├── Extract cluster summaries (theme, canonical_summary, keywords)
  ├── LLM identifies merge groups (semantically similar clusters)
  ├── Merge clusters within each group:
  │   ├── Combine recommendations
  │   ├── Deduplicate archon lists
  │   ├── Choose most representative theme
  │   └── Recalculate consensus level
  └── Result: ~150-200 consolidated clusters → ~60-80 motions
```

**Key Methods Added:**

| Method | Purpose |
|--------|---------|
| `_consolidate_clusters()` | Orchestrates the consolidation phase |
| `_identify_merge_groups()` | LLM call to find similar clusters |
| `_identify_merge_groups_batched()` | Handles large cluster sets (>50) |
| `_reconcile_merge_groups()` | Union-find to merge overlapping groups |
| `_merge_cluster_group()` | Combines multiple clusters into one |

**Safeguards:**
- Graceful degradation: If consolidation fails, keeps raw clusters
- Only runs if >10 clusters (skip for small sets)
- Batched processing for >50 clusters using overlapping windows
- Union-find ensures every cluster appears exactly once

### 13.6 Consensus Distribution Analysis

```
Clusters by consensus:
  - single: 248 (57%)  ← Only 1 archon contributed
  - low: 163 (38%)     ← 2-3 archons
  - medium: 22 (5%)    ← 4+ archons
  - high/critical: 0
```

The high percentage of "single" consensus clusters suggests:
1. Many recommendations are unique (good)
2. OR similar recommendations are in different batches (bad — cross-batch issue)

Cross-batch consolidation would likely convert many "single" clusters into "low" or "medium" by merging scattered contributors.

### 13.7 Next Steps

1. **Implement P2 fix** — Cross-batch cluster consolidation in `secretary_crewai_adapter.py`
2. **Re-run Secretary** on same transcript
3. **Compare metrics:**
   - Target: 60-80 motions (down from 185)
   - Target: <20% single-consensus clusters (down from 57%)
   - Target: 10+ medium/high consensus clusters (up from 22)
