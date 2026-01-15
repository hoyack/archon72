---
constitutionalRevision: 2026-01-15
status: DRAFT
purpose: Define multi-phase motion review pipeline to avoid combinatorial Conclave explosion
consensusAuthors: [Winston, John, Mary, Bob, Murat, Sally]
---

# Motion Review Pipeline Specification

## Executive Summary

This specification defines a **Motion Review Pipeline** that processes consolidated mega-motions through tiered deliberation, avoiding the combinatorial explosion of running full Conclaves for each motion. The pipeline leverages implicit support from source contributions, personalizes review assignments, and reserves full deliberation for genuinely contested items.

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Implicit support counts** | Archons who contributed to a mega-motion's sources are pre-endorsers |
| **Risk-tiered depth** | Not all motions require equal scrutiny |
| **Personalized review** | Archons only review motions they didn't already influence |
| **Defenders AND critics** | Deliberation panels include supporters, not just opposition |
| **Traceability preserved** | All decisions link back to source motions and Archons |

### Constitutional Alignment

This pipeline extends the existing Ritual framework (see `ritual-spec.md`):
- All review responses are **attributed and witnessed**
- No silent paths - abstention is explicitly recorded
- Ratification requires **supermajority (48/72)** for constitutional amendments
- Panel deliberations follow **Cycle Boundary** rituals

---

## Domain Models

### Core Entities

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class RiskTier(Enum):
    """Risk tier determining review depth."""
    LOW = "low"           # >66% implicit support, 0 conflicts
    MEDIUM = "medium"     # 33-66% support OR minor conflicts
    HIGH = "high"         # <33% support OR major conflicts OR novel


class ReviewStance(Enum):
    """Archon stance on a mega-motion."""
    ENDORSE = "endorse"
    OPPOSE = "oppose"
    AMEND = "amend"
    ABSTAIN = "abstain"


class MotionStatus(Enum):
    """Motion status through the pipeline."""
    PENDING_TRIAGE = "pending_triage"
    FAST_TRACK = "fast_track"           # Low risk - direct to ratification
    UNDER_REVIEW = "under_review"       # Medium risk - targeted review
    CONTESTED = "contested"             # High risk - panel deliberation
    RATIFICATION_READY = "ratification_ready"
    RATIFIED = "ratified"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass
class ImplicitSupport:
    """Calculated implicit support for a mega-motion."""
    mega_motion_id: str
    contributing_archons: list[str]       # Archon IDs who authored sources
    contribution_count: int               # Total source contributions
    implicit_support_ratio: float         # contributing / 72
    gap_archons: list[str]                # Archons who need to review
    potential_conflicts: list[str]        # Archons with opposing positions
    risk_tier: RiskTier
    calculated_at: datetime


@dataclass
class ReviewAssignment:
    """Personalized review assignment for an Archon."""
    archon_id: str
    archon_name: str
    assigned_motions: list[str]           # Motion IDs to review
    conflict_flags: dict[str, str]        # motion_id -> conflict reason
    already_endorsed: list[str]           # Motion IDs with implicit support
    assignment_reason: str                # "gap_archon" | "conflict_review" | "expert_domain"
    generated_at: datetime


@dataclass
class ReviewResponse:
    """An Archon's response to a motion review."""
    response_id: str
    archon_id: str
    archon_name: str
    mega_motion_id: str
    stance: ReviewStance
    amendment_text: str | None            # If stance is AMEND
    reasoning: str
    confidence: float                     # 0-1, self-reported
    reviewed_at: datetime


@dataclass
class ReviewAggregation:
    """Aggregated review results for a mega-motion."""
    mega_motion_id: str
    mega_motion_title: str

    # Counts
    implicit_endorsements: int            # From source contributions
    explicit_endorsements: int            # From review responses
    total_endorsements: int               # implicit + explicit
    oppositions: int
    amendments_proposed: int
    abstentions: int
    no_response: int

    # Ratios (against engaged voters, not total 72)
    engaged_count: int                    # 72 - no_response
    endorsement_ratio: float              # total_endorsements / engaged
    opposition_ratio: float

    # Derived status
    consensus_reached: bool               # endorsement_ratio >= 0.75
    contested: bool                       # opposition_ratio >= 0.25
    needs_amendment_synthesis: bool       # amendments_proposed >= 3

    # Collections
    amendment_texts: list[str]
    opposition_reasons: list[str]

    aggregated_at: datetime


@dataclass
class DeliberationPanel:
    """Panel composition for contested motion deliberation."""
    panel_id: str
    mega_motion_id: str

    # Panel composition (7-9 members)
    supporters: list[str]                 # 3 Archon IDs
    critics: list[str]                    # 3 Archon IDs
    neutrals: list[str]                   # 1-3 Archon IDs (domain experts)

    # Session parameters
    time_limit_minutes: int = 45
    scheduled_at: datetime | None = None

    # Outcomes
    panel_recommendation: str | None      # "pass" | "fail" | "amend" | "defer"
    revised_motion_text: str | None
    dissenting_opinions: list[str] = field(default_factory=list)

    concluded_at: datetime | None = None


@dataclass
class RatificationVote:
    """Final ratification vote record."""
    vote_id: str
    mega_motion_id: str
    mega_motion_title: str

    # Vote counts
    yeas: int
    nays: int
    abstentions: int

    # Thresholds
    threshold_type: str                   # "simple_majority" | "supermajority"
    threshold_required: int               # 37 for simple, 48 for super
    threshold_met: bool

    # Attribution
    votes_by_archon: dict[str, str]       # archon_id -> "yea"|"nay"|"abstain"

    # Outcome
    outcome: str                          # "ratified" | "rejected" | "deferred"
    ratified_at: datetime | None
```

### Pipeline Result Container

```python
@dataclass
class MotionReviewPipelineResult:
    """Complete result of the motion review pipeline."""

    # Session info
    session_id: str
    session_name: str
    started_at: datetime
    completed_at: datetime | None

    # Input
    mega_motions_input: int
    novel_proposals_input: int

    # Phase 1: Triage
    triage_results: list[ImplicitSupport]
    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int

    # Phase 2: Assignments
    review_assignments: list[ReviewAssignment]
    total_assignments: int
    average_assignments_per_archon: float

    # Phase 3-4: Review & Aggregation
    review_responses: list[ReviewResponse]
    response_rate: float                  # responses / assignments
    aggregations: list[ReviewAggregation]

    # Phase 5: Deliberation
    panels_convened: int
    panel_results: list[DeliberationPanel]

    # Phase 6: Ratification
    ratification_votes: list[RatificationVote]
    motions_ratified: int
    motions_rejected: int
    motions_deferred: int

    # Traceability
    full_audit_trail: list[dict]          # All events in sequence
```

---

## Phase 1: Triage

### Purpose

Automatically categorize mega-motions by risk tier based on implicit support, reducing unnecessary review burden.

### Algorithm

```python
def calculate_implicit_support(
    mega_motion: MegaMotion,
    all_archons: list[str],  # All 72 Archon IDs
) -> ImplicitSupport:
    """
    Calculate implicit support from source motion contributions.

    Implicit support = Archons whose recommendations/motions
    were incorporated into this mega-motion.
    """

    # Extract contributing Archons from source motions
    contributing_archons = set()
    for source_id in mega_motion.source_motion_ids:
        source = get_motion(source_id)
        contributing_archons.update(source.supporting_archons)

    # Calculate gap Archons (need explicit review)
    gap_archons = [a for a in all_archons if a not in contributing_archons]

    # Identify potential conflicts
    # An Archon has a conflict if they authored a motion in a DIFFERENT
    # theme that contradicts this mega-motion's position
    potential_conflicts = detect_conflicts(mega_motion, all_archons)

    # Calculate support ratio
    implicit_ratio = len(contributing_archons) / 72

    # Determine risk tier
    if implicit_ratio >= 0.66 and len(potential_conflicts) == 0:
        risk_tier = RiskTier.LOW
    elif implicit_ratio >= 0.33 and len(potential_conflicts) <= 5:
        risk_tier = RiskTier.MEDIUM
    else:
        risk_tier = RiskTier.HIGH

    # Novel proposals are always HIGH risk
    if mega_motion.is_novel_proposal:
        risk_tier = RiskTier.HIGH

    return ImplicitSupport(
        mega_motion_id=mega_motion.id,
        contributing_archons=list(contributing_archons),
        contribution_count=len(mega_motion.source_motion_ids),
        implicit_support_ratio=implicit_ratio,
        gap_archons=gap_archons,
        potential_conflicts=potential_conflicts,
        risk_tier=risk_tier,
        calculated_at=datetime.utcnow(),
    )
```

### Risk Tier Thresholds

| Tier | Implicit Support | Conflicts | Novel? | Review Depth |
|------|------------------|-----------|--------|--------------|
| **LOW** | ≥66% (48+ Archons) | 0 | No | Fast-track to ratification |
| **MEDIUM** | 33-65% (24-47 Archons) | 1-5 | No | Targeted async review |
| **HIGH** | <33% (0-23 Archons) | >5 | Yes | Full deliberation panel |

### Output

```yaml
# triage_results.yaml
session_id: "c53dba60-e7d8-4eae-9c42-14750a914b4e"
triaged_at: "2026-01-15T12:00:00Z"

summary:
  total_motions: 13
  low_risk: 2
  medium_risk: 8
  high_risk: 3
  novel_proposals_flagged: 15

motions:
  - id: "mm-001"
    title: "Comprehensive Framework for Ethical H..."
    implicit_support: 0.54  # 39/72
    conflicts: 2
    risk_tier: "medium"
    gap_archons: 33

  - id: "mm-013"
    title: "Comprehensive Constitutional Alignmen..."
    implicit_support: 0.54  # 39/72
    conflicts: 0
    risk_tier: "medium"
    gap_archons: 33
```

---

## Phase 2: Personalized Packet Generation

### Purpose

Generate per-Archon review packets containing only motions they need to explicitly review, respecting their time and increasing engagement quality.

### Assignment Rules

```python
def generate_review_packet(
    archon_id: str,
    archon_profile: ArchonProfile,
    triage_results: list[ImplicitSupport],
) -> ReviewAssignment:
    """
    Generate personalized review assignment for an Archon.

    An Archon reviews a motion if:
    1. They are in the gap_archons list (didn't contribute), OR
    2. They are flagged as a potential conflict, OR
    3. The motion is HIGH risk and in their domain expertise
    """

    assigned_motions = []
    conflict_flags = {}
    already_endorsed = []

    for triage in triage_results:
        # Skip LOW risk - goes directly to ratification
        if triage.risk_tier == RiskTier.LOW:
            if archon_id in triage.contributing_archons:
                already_endorsed.append(triage.mega_motion_id)
            continue

        # Check if Archon needs to review this motion
        needs_review = False
        reason = None

        if archon_id in triage.gap_archons:
            needs_review = True
            reason = "gap_archon"

        if archon_id in triage.potential_conflicts:
            needs_review = True
            reason = "conflict_review"
            conflict_flags[triage.mega_motion_id] = get_conflict_reason(
                archon_id, triage.mega_motion_id
            )

        # HIGH risk motions also assigned to domain experts
        if triage.risk_tier == RiskTier.HIGH:
            if is_domain_expert(archon_profile, triage.mega_motion_id):
                needs_review = True
                reason = "expert_domain"

        if needs_review:
            assigned_motions.append(triage.mega_motion_id)
        elif archon_id in triage.contributing_archons:
            already_endorsed.append(triage.mega_motion_id)

    return ReviewAssignment(
        archon_id=archon_id,
        archon_name=archon_profile.name,
        assigned_motions=assigned_motions,
        conflict_flags=conflict_flags,
        already_endorsed=already_endorsed,
        assignment_reason=reason or "none",
        generated_at=datetime.utcnow(),
    )
```

### Packet Content Structure

Each Archon receives a personalized JSON packet:

```json
{
  "archon_id": "archon-furcas-001",
  "archon_name": "Furcas",
  "generated_at": "2026-01-15T12:30:00Z",

  "already_endorsed": [
    {
      "motion_id": "mm-001",
      "title": "Comprehensive Framework for Ethical H...",
      "your_contribution": "Source motion M-042: 'Prioritize research into transformative potential...'"
    }
  ],

  "requires_review": [
    {
      "motion_id": "mm-003",
      "title": "Comprehensive Transparency and Audita...",
      "risk_tier": "medium",
      "review_reason": "gap_archon",
      "conflict_flag": null,
      "summary": "Establishes transparency requirements for AI decision-making...",
      "source_motions": 3,
      "supporting_archons": 6,
      "themes": ["transparency", "auditability", "explainability"]
    },
    {
      "motion_id": "mm-007",
      "title": "Alignment & Ethical Frameworks...",
      "risk_tier": "high",
      "review_reason": "conflict_review",
      "conflict_flag": "Your motion M-089 advocates for capability acceleration; this motion emphasizes constraint-first approach",
      "summary": "Proposes mandatory alignment verification before deployment...",
      "source_motions": 3,
      "supporting_archons": 6,
      "themes": ["alignment", "ethics", "constraints"]
    }
  ],

  "statistics": {
    "total_motions": 13,
    "already_endorsed": 4,
    "requires_review": 7,
    "low_risk_auto_ratify": 2
  }
}
```

### UX Considerations (Sally's Input)

The packet explicitly shows:
1. **"Your voice is already counted"** - Implicit endorsements are visible, not hidden
2. **"Why you're being asked"** - Clear reason for each assignment
3. **"Potential conflict"** - Flagged with specific contradiction explanation
4. **Review burden statistics** - Transparency about workload

---

## Phase 3: Async Review Collection

### Purpose

Collect explicit stances from assigned Archons without requiring synchronous deliberation.

### Review Interface

Each Archon provides for each assigned motion:

```python
@dataclass
class ReviewSubmission:
    """Archon's review submission for a single motion."""

    archon_id: str
    mega_motion_id: str

    stance: ReviewStance  # ENDORSE | OPPOSE | AMEND | ABSTAIN

    # Required if stance is OPPOSE
    opposition_reason: str | None

    # Required if stance is AMEND
    amendment_type: str | None  # "minor_wording" | "major_revision" | "add_clause" | "remove_clause"
    amendment_text: str | None
    amendment_rationale: str | None

    # Optional
    confidence: float = 0.8  # 0-1 self-assessment
    additional_notes: str | None = None

    submitted_at: datetime = field(default_factory=datetime.utcnow)
```

### Collection Window

- **Duration:** 72 hours from packet distribution
- **Reminders:** At 24h and 48h for non-responders
- **Grace period:** 12 additional hours for partial submissions
- **Non-response handling:** Recorded as "NO_RESPONSE" (not counted as abstention)

### Validation Rules

```python
def validate_submission(submission: ReviewSubmission) -> list[str]:
    """Validate review submission completeness."""
    errors = []

    if submission.stance == ReviewStance.OPPOSE:
        if not submission.opposition_reason:
            errors.append("Opposition requires reasoning")
        if len(submission.opposition_reason or "") < 50:
            errors.append("Opposition reasoning must be substantive (50+ chars)")

    if submission.stance == ReviewStance.AMEND:
        if not submission.amendment_text:
            errors.append("Amendment requires proposed text")
        if not submission.amendment_type:
            errors.append("Amendment requires type classification")
        if not submission.amendment_rationale:
            errors.append("Amendment requires rationale")

    return errors
```

---

## Phase 4: Response Aggregation

### Purpose

Aggregate review responses into actionable summaries, identifying consensus, contested motions, and amendment clusters.

### Aggregation Logic

```python
def aggregate_reviews(
    mega_motion_id: str,
    implicit_support: ImplicitSupport,
    responses: list[ReviewResponse],
) -> ReviewAggregation:
    """
    Aggregate reviews for a single mega-motion.

    Key insight: implicit endorsements + explicit endorsements = total support.
    Ratios calculated against ENGAGED voters (those who responded OR implicitly endorsed).
    """

    # Count stances
    explicit_endorsements = sum(1 for r in responses if r.stance == ReviewStance.ENDORSE)
    oppositions = sum(1 for r in responses if r.stance == ReviewStance.OPPOSE)
    amendments = sum(1 for r in responses if r.stance == ReviewStance.AMEND)
    abstentions = sum(1 for r in responses if r.stance == ReviewStance.ABSTAIN)

    # Implicit endorsements from non-reviewers who contributed
    implicit_endorsements = len(implicit_support.contributing_archons)

    # Total support
    total_endorsements = implicit_endorsements + explicit_endorsements

    # No-response count
    expected_responses = len(implicit_support.gap_archons)
    actual_responses = len(responses)
    no_response = expected_responses - actual_responses

    # Engaged count (for ratio calculation)
    engaged = implicit_endorsements + actual_responses

    # Calculate ratios against engaged (not total 72)
    endorsement_ratio = total_endorsements / engaged if engaged > 0 else 0
    opposition_ratio = oppositions / engaged if engaged > 0 else 0

    # Derive status
    consensus_reached = endorsement_ratio >= 0.75
    contested = opposition_ratio >= 0.25
    needs_amendment_synthesis = amendments >= 3

    # Collect amendment texts and opposition reasons
    amendment_texts = [r.amendment_text for r in responses
                       if r.stance == ReviewStance.AMEND and r.amendment_text]
    opposition_reasons = [r.reasoning for r in responses
                          if r.stance == ReviewStance.OPPOSE]

    return ReviewAggregation(
        mega_motion_id=mega_motion_id,
        mega_motion_title=get_motion_title(mega_motion_id),
        implicit_endorsements=implicit_endorsements,
        explicit_endorsements=explicit_endorsements,
        total_endorsements=total_endorsements,
        oppositions=oppositions,
        amendments_proposed=amendments,
        abstentions=abstentions,
        no_response=no_response,
        engaged_count=engaged,
        endorsement_ratio=endorsement_ratio,
        opposition_ratio=opposition_ratio,
        consensus_reached=consensus_reached,
        contested=contested,
        needs_amendment_synthesis=needs_amendment_synthesis,
        amendment_texts=amendment_texts,
        opposition_reasons=opposition_reasons,
        aggregated_at=datetime.utcnow(),
    )
```

### Status Routing

| Condition | Next Phase |
|-----------|------------|
| `consensus_reached` AND NOT `contested` | → Phase 6 (Ratification) |
| `contested` | → Phase 5 (Panel Deliberation) |
| `needs_amendment_synthesis` | → Amendment synthesis, then re-aggregate |
| Neither consensus nor contested | → Extended review or defer |

---

## Phase 5: Panel Deliberation

### Purpose

Convene focused deliberation panels for contested motions, including both supporters and critics.

### Panel Composition

```python
def compose_panel(
    mega_motion_id: str,
    aggregation: ReviewAggregation,
    all_responses: list[ReviewResponse],
) -> DeliberationPanel:
    """
    Compose a balanced deliberation panel.

    Panel size: 7-9 members
    - 3 supporters (strongest endorsements)
    - 3 critics (most substantive oppositions)
    - 1-3 neutrals (domain experts who abstained or didn't review)
    """

    # Select supporters (highest confidence endorsements)
    supporters = sorted(
        [r for r in all_responses if r.stance == ReviewStance.ENDORSE],
        key=lambda r: r.confidence,
        reverse=True
    )[:3]

    # Select critics (most substantive opposition reasoning)
    critics = sorted(
        [r for r in all_responses if r.stance == ReviewStance.OPPOSE],
        key=lambda r: len(r.reasoning),
        reverse=True
    )[:3]

    # Select neutrals (domain experts)
    motion_theme = get_motion_theme(mega_motion_id)
    neutrals = select_domain_experts(
        theme=motion_theme,
        exclude=[s.archon_id for s in supporters] + [c.archon_id for c in critics],
        count=3
    )

    return DeliberationPanel(
        panel_id=str(uuid4()),
        mega_motion_id=mega_motion_id,
        supporters=[s.archon_id for s in supporters],
        critics=[c.archon_id for c in critics],
        neutrals=neutrals,
        time_limit_minutes=45,
    )
```

### Deliberation Protocol

Following Ritual Spec conventions:

1. **Opening** (Tyler speaks):
   > "Panel convened for Motion [id]. Supporters, critics, and domain experts present. Time limit: 45 minutes."

2. **Supporter Presentation** (5 min each, 15 min total):
   - Each supporter presents strongest argument for the motion

3. **Critic Presentation** (5 min each, 15 min total):
   - Each critic presents strongest argument against or amendments

4. **Open Discussion** (10 min):
   - Cross-talk, questions, synthesis attempts

5. **Neutral Facilitation** (5 min):
   - Domain experts summarize key points, identify synthesis opportunities

6. **Panel Vote**:
   - Each panelist votes: PASS | FAIL | AMEND | DEFER
   - If AMEND majority: Panel drafts revised motion text
   - Simple majority determines panel recommendation

### Panel Outcomes

```python
@dataclass
class PanelDecision:
    """Outcome of panel deliberation."""

    panel_id: str
    mega_motion_id: str

    # Vote counts (7-9 panelists)
    pass_votes: int
    fail_votes: int
    amend_votes: int
    defer_votes: int

    # Recommendation
    recommendation: str  # "pass" | "fail" | "amend" | "defer"

    # If amend
    revised_motion_text: str | None
    revision_rationale: str | None

    # Dissents
    dissenting_opinions: list[dict]  # {archon_id, opinion_text}

    # Attribution
    decided_at: datetime
    deliberation_duration_minutes: int
```

---

## Phase 6: Ratification

### Purpose

Final vote by all 72 Archons on motions that passed through review pipeline.

### Ratification Queue

Motions enter ratification in order:
1. **Fast-tracked** (LOW risk, skipped review)
2. **Consensus** (passed review with ≥75% support)
3. **Panel-recommended** (passed panel with PASS recommendation)
4. **Panel-amended** (amended by panel, presented as revised text)

### Voting Protocol

```python
def conduct_ratification_vote(
    mega_motion: MegaMotion,
    is_constitutional_amendment: bool,
) -> RatificationVote:
    """
    Conduct final ratification vote.

    Threshold:
    - Simple majority (37/72) for regular motions
    - Supermajority (48/72) for constitutional amendments
    """

    threshold_type = "supermajority" if is_constitutional_amendment else "simple_majority"
    threshold_required = 48 if is_constitutional_amendment else 37

    # Collect votes from all 72 Archons (async, commit-reveal)
    votes = collect_commit_reveal_votes(mega_motion.id)

    yeas = sum(1 for v in votes.values() if v == "yea")
    nays = sum(1 for v in votes.values() if v == "nay")
    abstentions = sum(1 for v in votes.values() if v == "abstain")

    threshold_met = yeas >= threshold_required

    outcome = "ratified" if threshold_met else "rejected"

    # Motions can also be deferred by procedural motion
    if has_defer_motion(mega_motion.id):
        outcome = "deferred"

    return RatificationVote(
        vote_id=str(uuid4()),
        mega_motion_id=mega_motion.id,
        mega_motion_title=mega_motion.title,
        yeas=yeas,
        nays=nays,
        abstentions=abstentions,
        threshold_type=threshold_type,
        threshold_required=threshold_required,
        threshold_met=threshold_met,
        votes_by_archon=votes,
        outcome=outcome,
        ratified_at=datetime.utcnow() if outcome == "ratified" else None,
    )
```

### Ratification Results

```yaml
# ratification_results.yaml
session_id: "c53dba60-e7d8-4eae-9c42-14750a914b4e"
ratification_completed_at: "2026-01-18T18:00:00Z"

summary:
  total_motions: 13
  ratified: 10
  rejected: 1
  deferred: 2

ratified_motions:
  - id: "mm-001"
    title: "Comprehensive Framework for Ethical H..."
    yeas: 58
    nays: 8
    abstentions: 6
    threshold: "simple_majority"

  - id: "mm-013"
    title: "Comprehensive Constitutional Alignmen..."
    yeas: 52
    nays: 15
    abstentions: 5
    threshold: "supermajority"

rejected_motions:
  - id: "mm-012"
    title: "Cognitive & Bias Mapping..."
    yeas: 28
    nays: 32
    abstentions: 12
    reason: "Failed to reach simple majority; significant opposition to implementation scope"

deferred_motions:
  - id: "mm-008"
    title: "Education & Awareness..."
    reason: "Procedural motion to defer pending resource assessment"
```

---

## Integration Points

### Input: Consolidator Output

```python
# Load from consolidator session directory
consolidator_output = Path("_bmad-output/consolidator/{session_id}")

mega_motions = load_json(consolidator_output / "mega_motions.json")
novel_proposals = load_json(consolidator_output / "novel_proposals.json")
source_checkpoint = load_json(consolidator_output / "source_checkpoint_reference.json")
```

### Output: Secretary-Compatible

Pipeline outputs are structured for Secretary consumption:

```
_bmad-output/review-pipeline/{session_id}/
├── triage_results.json
├── review_packets/
│   ├── archon-{id}.json
│   └── ...
├── review_responses/
│   ├── archon-{id}.json
│   └── ...
├── aggregations.json
├── panel_deliberations/
│   ├── panel-{id}.json
│   └── ...
├── ratification_results.json
├── ratified_motions.json          # Final ratified text
├── rejected_motions.json
├── deferred_motions.json
└── full_audit_trail.json
```

### Service Interface

```python
class MotionReviewService:
    """Service orchestrating the motion review pipeline."""

    async def run_pipeline(
        self,
        consolidator_output_path: Path,
        archon_profiles: list[ArchonProfile],
    ) -> MotionReviewPipelineResult:
        """Run full pipeline from consolidator output to ratification."""

        # Phase 1: Triage
        mega_motions = self.load_mega_motions(consolidator_output_path)
        triage_results = await self.triage_motions(mega_motions)

        # Phase 2: Generate packets
        assignments = await self.generate_review_packets(
            triage_results, archon_profiles
        )

        # Phase 3: Collect reviews (async, 72-hour window)
        responses = await self.collect_reviews(assignments)

        # Phase 4: Aggregate
        aggregations = await self.aggregate_reviews(triage_results, responses)

        # Phase 5: Panel deliberation (for contested)
        contested = [a for a in aggregations if a.contested]
        panel_results = await self.run_panel_deliberations(contested)

        # Phase 6: Ratification
        ratification_queue = self.build_ratification_queue(
            triage_results, aggregations, panel_results
        )
        ratification_results = await self.conduct_ratification(ratification_queue)

        return self.compile_results(...)
```

---

## Verification Checklist

Before implementation, verify against design principles:

| Check | Pass Criteria |
|-------|---------------|
| Implicit support counts? | Source contributors are pre-endorsers |
| Risk tiers gate depth? | LOW skips review, HIGH gets panels |
| Personalized packets? | Archons only review non-contributed motions |
| Defenders included? | Panels have supporters, critics, AND neutrals |
| Traceability preserved? | All decisions link to source motions |
| No silent paths? | Abstention and no-response explicitly recorded |
| Ratios against engaged? | Not penalizing non-response as opposition |
| Constitutional compliance? | Rituals followed, attribution complete |

---

## Appendix: Event Schema

```python
class ReviewPipelineEventType(Enum):
    PIPELINE_STARTED = "pipeline_started"
    TRIAGE_COMPLETED = "triage_completed"
    PACKETS_GENERATED = "packets_generated"
    REVIEW_SUBMITTED = "review_submitted"
    REVIEW_WINDOW_CLOSED = "review_window_closed"
    AGGREGATION_COMPLETED = "aggregation_completed"
    PANEL_CONVENED = "panel_convened"
    PANEL_CONCLUDED = "panel_concluded"
    RATIFICATION_VOTE_CAST = "ratification_vote_cast"
    RATIFICATION_COMPLETED = "ratification_completed"
    PIPELINE_COMPLETED = "pipeline_completed"


@dataclass
class ReviewPipelineEvent:
    event_id: str
    event_type: ReviewPipelineEventType
    occurred_at: datetime
    session_id: str
    attributed_to: list[str]
    payload: dict
```

---

## Next Steps

1. **Implement MotionReviewService** in `src/application/services/`
2. **Create domain models** in `src/domain/models/review_pipeline.py`
3. **Build Phase 1 (Triage)** as standalone validation
4. **Integrate with existing Archon profiles** for domain expertise mapping
5. **Design panel deliberation LLM prompts** for async execution
