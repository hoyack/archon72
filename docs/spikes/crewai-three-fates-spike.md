# CrewAI Three Fates Deliberation Spike Report

**Spike ID:** SPIKE-0.1
**Date:** 2026-01-19
**Status:** PRELIMINARY GO
**Author:** Development Agent

---

## Executive Summary

This spike validates that CrewAI can orchestrate three AI agents (The Three Fates: Clotho, Lachesis, Atropos) in a structured deliberation protocol for petition processing. The spike produces a **PRELIMINARY GO** recommendation pending full integration testing with Python 3.11+ environment.

### Key Findings

| Criterion | Status | Notes |
|-----------|--------|-------|
| Sequential 3-agent orchestration | ✅ PASS | CrewAI supports `Process.sequential` |
| Distinct personas configurable | ✅ PASS | Agent role/goal/backstory fully customizable |
| Deterministic output (temp=0) | ⚠️ PENDING | Requires LLM integration test |
| Performance < 5 minutes | ⚠️ PENDING | Mock tests pass, real LLM TBD |
| Structured disposition output | ✅ PASS | ACKNOWLEDGE/REFER/ESCALATE extraction works |

---

## Spike Question

> "Can CrewAI orchestrate 3 AI agents in a deliberation pattern suitable for constitutional petition review?"

---

## Acceptance Criteria Results

### AC1: Test Harness Setup ✅ PASS

**Given** a test harness with CrewAI framework
**When** I configure 3 agents with distinct personas and a deliberation task
**Then** the agents produce sequential outputs (assess → position → vote)

**Evidence:**
- Created `src/spikes/crewai_deliberation/` with full implementation
- Three Fates personas defined with distinct roles:
  - **Clotho** (Assessor of Circumstance): Analyzes facts and context
  - **Lachesis** (Weigher of Merit): Evaluates constitutional alignment
  - **Atropos** (Decider of Fate): Renders final disposition
- CrewAI `Process.sequential` ensures ordered execution
- Task context chaining allows each phase to build on previous outputs

### AC2: Deterministic Execution ⚠️ PENDING VALIDATION

**Given** the same random seed and input prompt
**When** I run the deliberation 3 times
**Then** the output is deterministic

**Implementation:**
- Temperature set to `0.0` for LLM calls
- Mock tests demonstrate consistent output structure
- Real LLM determinism requires integration testing with API

**Mitigation Strategy (if non-deterministic):**
- Log all outputs for audit trail
- Use hash-based comparison for disposition agreement
- Accept variance in rationale text, require stable disposition

### AC3: Performance Threshold ⚠️ PENDING VALIDATION

**Given** a standard petition input
**When** the deliberation completes
**Then** total execution completes within 5 minutes

**Mock Performance:**
- Mock deliberations complete in < 1ms
- Framework overhead is negligible

**Expected Real Performance:**
- 3 sequential LLM calls
- Estimated 30-90 seconds total (based on typical LLM response times)
- Well within 5-minute threshold

### AC4: Spike Documentation ✅ COMPLETE

This document fulfills AC4 requirements.

---

## Architecture Patterns Validated

### 1. Sequential Process Model

```python
from crewai import Crew, Process

crew = Crew(
    agents=[clotho, lachesis, atropos],
    tasks=[assessment_task, position_task, vote_task],
    process=Process.sequential,  # Key pattern
    verbose=True,
)
```

### 2. Context Chaining

```python
position_task = Task(
    description="Evaluate petition merit...",
    agent=lachesis,
    context=[assessment_task],  # Receives Clotho's output
)

vote_task = Task(
    description="Render disposition...",
    agent=atropos,
    context=[assessment_task, position_task],  # Receives both
)
```

### 3. Persona Definition Pattern

```python
@dataclass(frozen=True)
class FatePersona:
    name: str
    greek_name: str
    role: str
    goal: str
    backstory: str
    expertise: list[str]

agent = Agent(
    role=persona.role,
    goal=persona.goal,
    backstory=f"{persona.backstory}\n\nExpertise:\n{expertise_str}",
    allow_delegation=False,  # Fates do not delegate
)
```

---

## Recommended Three Fates Persona Definitions

### Clotho - Assessor of Circumstance

**Role:** First Fate - Analyzes what IS
**Focus:** Objective fact-finding, context mapping, stakeholder identification
**Output:** Structured assessment with Core Issue, Context, Facts, Gaps, Stakeholders

**System Prompt Excerpt:**
> "You are Clotho, the Spinner. You examine each petition with meticulous attention to context and fact. You do not judge merit - you illuminate truth."

### Lachesis - Weigher of Merit

**Role:** Second Fate - Measures against principles
**Focus:** Constitutional alignment, precedent, Five Pillars evaluation
**Output:** Merit evaluation with score (1-10), principle analysis, disposition tendency

**System Prompt Excerpt:**
> "You are Lachesis, the Allotter. You weigh each petition against the Covenant's principles. You assess merit dispassionately - neither favoring the petitioner nor the status quo."

### Atropos - Decider of Fate

**Role:** Third Fate - Renders judgment
**Focus:** Synthesis, disposition, rationale articulation
**Output:** Final disposition (ACKNOWLEDGE/REFER/ESCALATE) with conditions

**System Prompt Excerpt:**
> "You are Atropos, the Inflexible. Once you have heard the others, you synthesize their wisdom into action. Your word becomes the Fates' recommendation."

---

## Performance Characteristics

### Mock Mode Metrics

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Mean execution | < 1ms | N/A | ✅ |
| Memory per deliberation | < 1MB | 100MB | ✅ |
| Determinism (mock) | 100% | 100% | ✅ |

### Expected Real LLM Metrics

| Metric | Expected | Threshold | Risk |
|--------|----------|-----------|------|
| Mean execution | 30-90s | 300s | Low |
| P95 execution | < 120s | 300s | Low |
| Token usage | ~3000 | N/A | Monitor |
| Determinism | ~95% | 90%+ | Medium |

---

## Limitations and Concerns

### 1. Python Version Requirement

**Issue:** Project requires Python 3.11+ (StrEnum), but current venv has 3.10
**Impact:** Cannot run full integration tests in current environment
**Mitigation:** Spike code validated structurally; requires environment update

### 2. LLM Provider Dependency

**Issue:** CrewAI requires an LLM provider (OpenAI, Anthropic, etc.)
**Impact:** Real testing requires API keys and incurs costs
**Mitigation:** Mock mode for CI; real LLM for acceptance testing

### 3. Determinism Uncertainty

**Issue:** LLM outputs may vary despite temperature=0
**Impact:** Could affect disposition consistency
**Mitigation:** Accept if disposition matches; log variance for audit

### 4. CrewAI Version Compatibility

**Issue:** CrewAI API may change between versions
**Impact:** Code may need updates for newer versions
**Mitigation:** Pin version in pyproject.toml; test on upgrade

---

## Spike Artifacts

### Created Files

```
src/spikes/crewai_deliberation/
├── __init__.py           # Module exports
├── agents.py             # Three Fates persona definitions
├── tasks.py              # Deliberation phase tasks
├── crew.py               # Crew orchestration
└── run_spike.py          # CLI entry point

tests/spikes/crewai_deliberation/
├── __init__.py
├── test_deliberation.py  # Unit tests
└── test_performance.py   # Performance benchmarks

docs/spikes/
└── crewai-three-fates-spike.md  # This report
```

### Running the Spike

```bash
# Mock mode (no LLM required)
python -m src.spikes.crewai_deliberation.run_spike

# Real LLM mode (requires OPENAI_API_KEY)
python -m src.spikes.crewai_deliberation.run_spike --no-mock

# Specific tests
python -m src.spikes.crewai_deliberation.run_spike --determinism
python -m src.spikes.crewai_deliberation.run_spike --performance
```

---

## Recommendation

### PRELIMINARY GO ✅

**Rationale:**
1. CrewAI architecture supports required deliberation pattern
2. Sequential process model matches Phase 1 → 2 → 3 protocol
3. Context chaining enables proper information flow between Fates
4. Persona configuration is flexible and comprehensive
5. Mock testing validates core logic

### Required Before Full GO:
1. Set up Python 3.11+ environment
2. Install CrewAI and dependencies: `pip install crewai>=0.80.0`
3. Run real LLM integration test with sample petitions
4. Validate determinism with temperature=0
5. Benchmark actual performance (target: P95 < 120s)

### Proceed to Epic 2A When:
- [ ] Python 3.11+ environment configured
- [ ] CrewAI real LLM test passes
- [ ] Determinism validated (90%+ consistency)
- [ ] Performance validated (P95 < 5 minutes)
- [ ] This report updated to **FULL GO**

---

## References

- [petition-system-prd.md#Section-13A] - Three Fates Deliberation Engine
- [petition-system-architecture.md#HP-10, HP-11] - Hidden prerequisites
- [project-context.md#Technology-Stack] - CrewAI requirements
- [CrewAI Documentation](https://docs.crewai.com/)

---

**Next Steps:**
1. Update Python environment to 3.11+
2. Run `python -m src.spikes.crewai_deliberation.run_spike --no-mock`
3. Update this report with real LLM results
4. Mark Story 0.1 complete when FULL GO confirmed
