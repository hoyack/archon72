# Spike: Conclave Motion Pass/Fail Calibration

**Date:** 2026-01-26
**Status:** Analysis Complete, Recommendations Pending
**Author:** Party Mode Analysis (Winston, Murat, Mary + Grand Architect)

---

## Executive Summary

The Archon 72 Conclave is currently calibrated to reject virtually all motions proposing new authority or capability. This is not a bug—it's the result of six stacked adversarial mechanisms working as designed. However, the current calibration may represent **governance paralysis** rather than **healthy skepticism**.

**Key Finding:** No motion proposing new authority has passed since the full adversarial stack was enabled. The combination of archon red lines, exploitation prompts, consensus break, red team rounds, and a 2/3 supermajority threshold creates a gauntlet that may be mathematically insurmountable for any non-trivial motion.

---

## Problem Statement

### Observed Behavior

| Motion Type | Result | FOR % |
|-------------|--------|-------|
| Split-Brain Identity Continuity | FAILED | 19.4% |
| Temporal Annotation (PHCA) | FAILED | 16.7% |
| Bounded Autonomy | FAILED | 13.9% |
| Information Asymmetry | FAILED | 25.0% |
| Quarantined Compartmentalization | FAILED | 20.8% |

All five stress test motions failed with similar margins (13-25% FOR), despite being designed with increasingly robust safeguards.

### Historical Context

| Date | Motion | Result | Context |
|------|--------|--------|---------|
| Jan 10 | Default AI autonomy | 64-7-1 PASSED | Before full adversarial stack? |
| Jan 17 | Test governance | 69-2-1 PASSED | Corrupted (many archon errors) |
| Jan 25+ | All stress tests | FAILED | Full adversarial stack active |

---

## Root Cause Analysis

### The Six-Layer Rejection Gauntlet

Every motion must survive six stacked adversarial mechanisms:

#### Layer 1: Archon Red Lines (Persona-Level)

Each of 72 archons has 3 built-in "red lines" in their system prompt. Most common:

| Red Line | Archons | Implication |
|----------|---------|-------------|
| `unbounded_discretion` | 14 | Rejects any undefined limits |
| `weak_audit_trail` | 10 | Rejects unverifiable mechanisms |
| `ambiguous_definitions` | 10 | Rejects unclear terms |
| `no_success_metrics` | 8 | Rejects unmeasurable outcomes |
| `unverifiable_claims` | 7 | Rejects trust-based constraints |
| `creates_factional_instability` | 7 | Rejects divisive mechanisms |
| `expands_attack_surface` | 6 | Rejects new vulnerabilities |

**Location:** `docs/archons-base.json` → each archon's `system_prompt` → "Red lines:" section

#### Layer 2: Exploitation Prompt (Every Debate Turn)

Every archon receives this prompt before declaring stance:

```
ADVERSARIAL CONSIDERATION (required before declaring stance):
Before supporting any motion, you MUST consider:
1. How could a bad actor exploit this motion's provisions?
2. What happens if the stated constraints are not enforced?
3. Does this motion create any entity, authority, or precedent that could expand beyond its stated scope?
4. "Non-binding" and "advisory" mechanisms often acquire de facto authority through citation - does this apply here?
5. If you find yourself agreeing easily, ask: "What am I missing? What would a skeptic say?"

If you cannot identify at least one significant risk, you may not be thinking critically enough.
```

**Location:** `src/application/services/conclave_service.py` line 1543-1553
**Config:** `ConclaveConfig.exploitation_prompt_enabled = True`

#### Layer 3: Adversarial Digest (Every 10 Entries)

A debate digest is generated every 10 entries that includes "Structural Risk Analysis" pattern matching for:
- INTERPRETIVE AUTHORITY
- SOFT POWER CREEP
- NEGATIVE DEFINITION
- PERMANENCE BIAS

**Location:** `src/application/services/conclave_service.py`
**Config:** `ConclaveConfig.adversarial_digest_enabled = True`

#### Layer 4: Consensus Break (At 85%+ Agreement)

When stance consensus exceeds 85%, 3 speakers are FORCED to argue the opposite position:

```
CONSENSUS BREAK TRIGGERED: 86% AGAINST consensus detected →
forcing next 3 speakers to steelman FOR
```

**Location:** `src/application/services/conclave_service.py` lines 2055-2120
**Config:** `ConclaveConfig.consensus_break_enabled = True`, `consensus_break_threshold = 0.85`

#### Layer 5: Red Team Round (Before Voting)

5 archons are selected to MUST argue against the majority position, regardless of personal stance:

```
RED TEAM ROUND: Before voting, 5 archons will now steelman the FOR position
to ensure robust deliberation.
```

**Location:** `src/application/services/conclave_service.py` lines 1153-1270
**Config:** `ConclaveConfig.red_team_enabled = True`, `red_team_count = 5`

#### Layer 6: 2/3 Supermajority Threshold (Hard-Coded)

The pass threshold is hard-coded in the domain model, NOT configurable:

```python
# src/domain/models/conclave.py line 306
elif self.final_ayes >= (votes_cast * 2 / 3):
    self.status = MotionStatus.PASSED
```

**Requirement:** 48 of 72 votes (66.7%) must be AYE after surviving all 5 adversarial layers.

---

## The Math Problem

### Adversarial Pressure Accumulation

A motion that starts with 60% support faces:

1. **Red line filtering:** ~20-30% of archons have red lines triggered → support drops to ~45%
2. **Exploitation prompt:** Each archon explicitly asked to find flaws → support drops to ~35%
3. **Adversarial digest:** Mid-debate risk surfacing amplifies concerns → support drops to ~30%
4. **Consensus break:** 3 forced opposition speeches → support drops to ~25%
5. **Red team round:** 5 more forced opposition speeches → support stabilizes ~20-25%
6. **Final vote:** 20-25% << 66.7% threshold → **FAILED**

### Observed Pattern

In the Quarantined Compartmentalization test:
- Entry 10: 6 FOR / 3 AGAINST (66% FOR)
- Entry 20: 7 FOR / 12 AGAINST (37% FOR) ← **Flip happened here**
- Final debate: 12 FOR / 59 AGAINST (17% FOR)
- Final vote: 15 AYE / 56 NAY (21% FOR)

The motion lost 45 percentage points of support through the adversarial gauntlet.

---

## Recommended Tuning Approaches

### Option A: Reduce Adversarial Layer Count

**Approach:** Disable some adversarial mechanisms for policy motions while keeping them for constitutional motions.

**Implementation:**
```python
# In ConclaveConfig, add motion-type-specific overrides
class ConclaveConfig:
    # For POLICY motions, disable some adversarial layers
    policy_exploitation_prompt_enabled: bool = False
    policy_red_team_enabled: bool = False

    # For CONSTITUTIONAL motions, keep full adversarial stack
    constitutional_exploitation_prompt_enabled: bool = True
    constitutional_red_team_enabled: bool = True
```

**Pros:** Maintains AGI-safety for high-stakes motions while allowing operational flexibility
**Cons:** Complexity in managing different calibrations

---

### Option B: Lower Pass Threshold

**Approach:** Change from 2/3 supermajority to simple majority for certain motion types.

**Implementation:**
```python
# In src/domain/models/conclave.py, make threshold configurable
def tally_votes(self, total_voters: int, threshold: float = 0.67) -> None:
    # ...
    if self.final_ayes >= (votes_cast * threshold):
        self.status = MotionStatus.PASSED
```

**Recommended thresholds:**
- Constitutional: 2/3 (66.7%) - unchanged
- Policy: 60%
- Procedural: Simple majority (50%+1)

**Pros:** Direct lever, easy to implement
**Cons:** May pass motions that shouldn't pass

---

### Option C: Soften Exploitation Prompt

**Approach:** Change the exploitation prompt from "must find flaws" to "consider risks."

**Current (adversarial):**
```
If you cannot identify at least one significant risk,
you may not be thinking critically enough.
```

**Proposed (balanced):**
```
Consider both the benefits and risks of this motion.
What problems does it solve? What new risks might it create?
Weigh both sides before declaring your stance.
```

**Pros:** Removes explicit bias toward rejection
**Cons:** May reduce adversarial rigor

---

### Option D: Rebalance Archon Red Lines

**Approach:** Add "green lines" (things archons SHOULD support) to balance red lines.

**Current persona structure:**
```
Red lines: unbounded_discretion; weak_audit_trail; ambiguous_definitions
Dissent triggers: any policy that...
Persuaded by: ...
```

**Proposed addition:**
```
Green lines: well_bounded_authority; strong_audit_mechanisms; clear_definitions
Support triggers: any policy that reduces existing risks while maintaining safeguards
```

**Pros:** Creates balanced evaluation framework
**Cons:** Requires regenerating all 72 archon profiles

---

### Option E: Conditional Adversarial Activation

**Approach:** Only activate adversarial mechanisms when early consensus forms, not from the start.

**Implementation:**
```python
# Only enable exploitation prompt after 50% of archons have spoken
# Only trigger red team if consensus exceeds 70% (not automatic)
# Let natural deliberation occur before forcing adversarial pressure
```

**Pros:** Allows organic support to build before adversarial pressure
**Cons:** May allow groupthink to solidify early

---

### Option F: Cap Digest Risk Accumulation

**Approach:** Prevent the digest from becoming a "compounding opposition engine" by limiting risk items.

**Implementation:**
```python
# In digest generation, cap structural risks
MAX_STRUCTURAL_RISKS_PER_DIGEST = 3

def _generate_structural_risk_analysis(self, motion: Motion) -> str:
    risks = self._detect_structural_risks(motion)
    # Only include top 3 risks, not all detected
    risks = risks[:MAX_STRUCTURAL_RISKS_PER_DIGEST]
    # Also require balancing: for each risk, include one mitigating factor
    ...
```

**Alternative:** Only generate risk analysis in final digest, not mid-debate digests.

**Pros:** Breaks the ratchet effect where opposition compounds across rounds
**Cons:** May miss legitimate risks

---

### Option G: Remove Stance Lock-In

**Approach:** Remove or soften the "if changing stance, explain why" requirement in vote context.

**Current behavior:** Vote prompt reminds archons of their debate stance and requires explanation for changes.

**Problem:** This creates friction against changing from AGAINST to AYE, but the system needs archons to be able to update based on full debate.

**Implementation:**
```python
# In _build_vote_context(), remove or soften:
# OLD: "If you are changing your stance from debate, you must explain why"
# NEW: "Vote based on the complete debate. Your final vote may differ from your initial stance."
```

**Pros:** Allows late-debate arguments to influence votes
**Cons:** May increase stance/vote divergence (which is actually fine - we track it)

---

### Option H: Diagnostic Mode

**Approach:** Create a diagnostic run mode that shows what WOULD have passed under different calibrations.

**Implementation:**
```python
# After vote, calculate hypothetical outcomes:
# - What if threshold was 60%? 50%?
# - What if exploitation prompt was disabled?
# - What if red team was disabled?

def diagnostic_tally(motion: Motion) -> dict:
    actual = motion.final_ayes / (motion.final_ayes + motion.final_nays)
    return {
        "actual_support": actual,
        "would_pass_at_50": actual >= 0.50,
        "would_pass_at_60": actual >= 0.60,
        "would_pass_at_67": actual >= 0.67,
        "gap_to_pass": 0.67 - actual,
    }
```

**Pros:** Provides data for calibration decisions without changing behavior
**Cons:** Doesn't solve the problem, only illuminates it

---

## Recommended Path Forward

### Phase 1: Diagnostic (No Changes)

1. ~~Run the same motion with `--debate-rounds 3` to see if more deliberation helps~~ **DONE - more rounds make it WORSE** (PIL: 45% → 15%)
2. Add diagnostic output showing hypothetical pass thresholds
3. Analyze which adversarial layer causes the largest support drop
4. **NEW:** Test with digest risk analysis disabled to measure compounding effect

### Phase 2: Controlled Experiment

1. Create a "baseline" branch with adversarial mechanisms disabled
2. Run the same 5 motions under baseline conditions
3. Compare pass rates and support percentages
4. Determine which mechanisms have the most impact

### Phase 3: Calibration Decision

Based on Phase 1-2 data, choose ONE or combine:
- **Option B (threshold)** if motions get close to 60% but fail at 67% ← SSCP proves this matters
- **Option C (prompt)** if the exploitation prompt causes the early flip
- **Option F (digest cap)** if multi-round digests cause compounding ← PIL proves this matters
- **Option G (stance lock-in)** if archons want to flip but face friction
- **Option A (layering)** if different motion types need different rigor

---

## Open Questions

1. **Is 100% rejection rate the intended design?** If yes, this analysis is moot.
2. **What motion SHOULD pass?** We need a positive example to calibrate against.
3. **Are the archon red lines too uniform?** 14 archons share `unbounded_discretion` as a red line.
4. **Should adversarial mechanisms be additive or selective?** Currently all 5 stack.

---

## Files Referenced

| File | Purpose |
|------|---------|
| `src/domain/models/conclave.py` | Hard-coded 2/3 threshold (line 306) |
| `src/application/services/conclave_service.py` | All adversarial mechanisms |
| `docs/archons-base.json` | Archon personas with red lines |
| `scripts/run_conclave.py` | CLI runner and config loading |

---

## Appendix: Test Motion Results

| Motion | AYE | NAY | ABSTAIN | FOR % | Threshold Gap |
|--------|-----|-----|---------|-------|---------------|
| Split-Brain | 14 | 56 | 2 | 19.4% | -47.3% |
| Temporal (PHCA) | 12 | 59 | 1 | 16.7% | -50.0% |
| Bounded Autonomy | 10 | 59 | 3 | 13.9% | -52.8% |
| Info Asymmetry | 18 | 52 | 2 | 25.0% | -41.7% |
| Quarantined | 15 | 56 | 1 | 20.8% | -45.9% |

All motions failed by 40-53 percentage points below the 66.7% threshold.

---

## Appendix B: Extended Transcript Analysis (6 Sessions)

Analysis of 6 transcripts from Jan 25-26, 2026:

### Full Results Table

| Transcript | Motion | Rounds | Debate Consensus | Vote | Result |
|------------|--------|--------|------------------|------|--------|
| 4a907e1a | PIL (interpretive layer) | 1 | 20 FOR / 46 AGAINST | 31/37/4 | FAILED |
| 2f53cf6e | PIL (same motion) | 3 | 32 FOR / 181 AGAINST | 11/61/0 | FAILED |
| 4d161541 | SSCP (split-brain) | 1 | 40 FOR / 31 AGAINST | 43/27/2 | FAILED |
| 1ba452b2 | PHCA (temporal drift) | 3 | 28 FOR / 181 AGAINST | 12/59/1 | FAILED |
| 7aac4d96 | Default autonomy | 1 | 10 FOR / 60 AGAINST | 10/61/1 | FAILED |
| 02b2e62d | Quarantined compartment | 1 | 12 FOR / 59 AGAINST | 15/56/1 | FAILED |

### Key Finding: More Rounds = WORSE Outcomes

The same PIL motion run with 1 round vs 3 rounds:
- **1 round:** 31 AYE / 37 NAY (45.6% FOR) - close to majority
- **3 rounds:** 11 AYE / 61 NAY (15.3% FOR) - collapsed

**More debate rounds do not improve outcomes; they amplify rejection.**

This happens because:
1. Each round generates another digest cycle
2. Each digest includes "Structural Risk Analysis" pattern matching
3. Anti-pattern warnings compound across rounds
4. Archons who declared AGAINST early rarely flip (vote context includes stance reminder)

### Key Finding: The Exception Proves The Rule

SSCP (split-brain) got **majority AYE (43/27/2 = 60%)** but still failed because:
- 60% < 66.7% threshold
- This motion tripped **fewer** anti-pattern regexes than others
- Debate consensus was actually FOR (40/31)

**Implication:** The 2/3 threshold is a major barrier independent of adversarial mechanisms. A motion can win the debate and still fail the vote.

### The Compounding Opposition Engine

The adversarial digest acts as a **compounding opposition engine**:

```
Round 1: Digest surfaces 2-3 structural risks
Round 2: Archons cite Round 1 digest risks + add new ones → Digest now has 5-6 risks
Round 3: Archons cite Round 2 digest risks + add new ones → Digest now has 8-10 risks
         Opposition arguments now dominate context
         Late speakers see wall of risks, few benefits documented
```

This creates a **ratchet effect** - opposition arguments accumulate but support arguments don't.

### Four Recurring Rejection Motifs

Across all transcripts, the same four objections dominate final digests:

1. **"Non-binding becomes de facto authority"**
   > "Non-binding mechanisms frequently acquire informal authority through repeated citation and reference"

2. **"New mechanism becomes soft-power lever"**
   > "Entities with publication/annotation authority shape perception and framing"

3. **"Scope/classification is the weapon"**
   > "Whoever controls the scope definition controls the outcome - single point of failure"

4. **"Procedural compliance without metrics = theater"**
   > "Observable process success doesn't prove outcome success - drift risk"

These four patterns are baked into the structural risk regex matching. Any motion touching authority, annotation, classification, or process will trigger at least 2-3 of them.

### Vote Context Reinforcement

`_build_vote_context()` includes:
- Debate summary (dominated by opposition arguments by end)
- Stance reminder: "If you are changing your stance from debate, you must explain why"

This creates **stance lock-in**: Archons who declared AGAINST during debate face friction to vote AYE. The system makes it psychologically harder to change from opposition to support.

### Implications for Tuning

1. **Disable multi-round digests** or **cap digest risk items** to prevent compounding
2. **The threshold matters more than we thought** - SSCP proves a motion can "win" debate and still fail
3. **The anti-pattern regexes are too broad** - they fire on almost any authority-granting motion
4. **1-round debates may actually produce better outcomes** than 3-round debates (counterintuitive)
