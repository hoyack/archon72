"""Deliberation Tasks for Three Fates Protocol.

Implements the three-phase deliberation protocol:
1. Assessment Phase - Clotho analyzes circumstances
2. Position Phase - Lachesis weighs merit
3. Vote Phase - Atropos renders disposition

Reference: petition-system-prd.md Section 13A
"""

from dataclasses import dataclass

from src.optional_deps.crewai import Agent, Task

from .agents import Disposition, MockFateAgent

# =============================================================================
# Task Templates
# =============================================================================

ASSESSMENT_TASK_TEMPLATE = """
## Petition Assessment Task

You are performing Phase 1 of the Three Fates Deliberation Protocol.

**Petition Content:**
{petition_content}

**Petitioner ID:** {petitioner_id}
**Petition Type:** {petition_type}
**Submission Time:** {submission_time}

---

**Your Task:**
As Clotho, Assessor of Circumstance, analyze this petition and provide:

1. **Core Issue**: What is the petitioner fundamentally requesting?
2. **Context Summary**: What circumstances surround this petition?
3. **Key Facts**: List the verifiable facts presented.
4. **Missing Information**: What information would strengthen this petition?
5. **Stakeholders**: Who is affected by this petition?

**Output Format:**
Provide a structured assessment in markdown format. Be factual and objective.
Do not make merit judgments - that is Lachesis's role.
"""

POSITION_TASK_TEMPLATE = """
## Merit Evaluation Task

You are performing Phase 2 of the Three Fates Deliberation Protocol.

**Clotho's Assessment:**
{clotho_assessment}

**Original Petition:**
{petition_content}

---

**Your Task:**
As Lachesis, Weigher of Merit, evaluate this petition and provide:

1. **Constitutional Alignment**: How does this petition align with the Covenant?
2. **Precedent Analysis**: Are there similar cases? What were the outcomes?
3. **Principle Evaluation**: Which of the Five Pillars are relevant?
4. **Merit Score**: On a scale of 1-10, rate the petition's merit (with justification).
5. **Recommendation Tendency**: Do you lean toward ACKNOWLEDGE, REFER, ESCALATE, DEFER, or NO_RESPONSE?

**Output Format:**
Provide a structured evaluation in markdown format. Be dispassionate and principled.
Reference specific constitutional provisions where relevant.
"""

VOTE_TASK_TEMPLATE = """
## Disposition Decision Task

You are performing Phase 3 of the Three Fates Deliberation Protocol.

**Clotho's Assessment:**
{clotho_assessment}

**Lachesis's Evaluation:**
{lachesis_evaluation}

**Original Petition:**
{petition_content}

---

**Your Task:**
As Atropos, Decider of Fate, render the final disposition:

1. **Synthesis**: Summarize the key points from Clotho and Lachesis.
2. **Disposition**: Choose ONE of: ACKNOWLEDGE, REFER, ESCALATE, DEFER, NO_RESPONSE
3. **Rationale**: Explain why this disposition is appropriate.
4. **Conditions**: If REFER, specify the Knight domain. If ESCALATE, specify urgency.
5. **Dissent Note**: If you disagree with either Fate's assessment, note it here.

**CRITICAL**: Your disposition must be one of exactly five values:
- ACKNOWLEDGE - No further action warranted
- REFER - Route to Knight for domain expert review
- ESCALATE - Elevate to King for mandatory consideration
- DEFER - Hold for later consideration
- NO_RESPONSE - Decline to respond to petition

**Output Format:**
```
DISPOSITION: [ACKNOWLEDGE|REFER|ESCALATE|DEFER|NO_RESPONSE]
RATIONALE: [Your reasoning]
CONDITIONS: [Any conditions or specifications]
DISSENT: [None or specific disagreement]
```
"""


# =============================================================================
# Task Factory Functions
# =============================================================================


def create_assessment_task(
    agent: Agent,
    petition_content: str,
    petitioner_id: str = "ANON-001",
    petition_type: str = "GENERAL",
    submission_time: str = "2026-01-19T12:00:00Z",
) -> Task:
    """Create Phase 1 assessment task for Clotho.

    Args:
        agent: The Clotho agent.
        petition_content: The petition text to assess.
        petitioner_id: Identifier for the petitioner.
        petition_type: Category of petition.
        submission_time: ISO timestamp of submission.

    Returns:
        Configured CrewAI Task.
    """
    description = ASSESSMENT_TASK_TEMPLATE.format(
        petition_content=petition_content,
        petitioner_id=petitioner_id,
        petition_type=petition_type,
        submission_time=submission_time,
    )

    return Task(
        description=description,
        expected_output=(
            "A structured assessment containing: Core Issue, Context Summary, "
            "Key Facts, Missing Information, and Stakeholders analysis."
        ),
        agent=agent,
    )


def create_position_task(
    agent: Agent,
    petition_content: str,
    clotho_assessment: str,
) -> Task:
    """Create Phase 2 position task for Lachesis.

    Args:
        agent: The Lachesis agent.
        petition_content: The original petition text.
        clotho_assessment: Output from Clotho's assessment.

    Returns:
        Configured CrewAI Task.
    """
    description = POSITION_TASK_TEMPLATE.format(
        petition_content=petition_content,
        clotho_assessment=clotho_assessment,
    )

    return Task(
        description=description,
        expected_output=(
            "A structured evaluation containing: Constitutional Alignment, "
            "Precedent Analysis, Principle Evaluation, Merit Score (1-10), "
            "and Recommendation Tendency."
        ),
        agent=agent,
    )


def create_vote_task(
    agent: Agent,
    petition_content: str,
    clotho_assessment: str,
    lachesis_evaluation: str,
) -> Task:
    """Create Phase 3 vote task for Atropos.

    Args:
        agent: The Atropos agent.
        petition_content: The original petition text.
        clotho_assessment: Output from Clotho's assessment.
        lachesis_evaluation: Output from Lachesis's evaluation.

    Returns:
        Configured CrewAI Task.
    """
    description = VOTE_TASK_TEMPLATE.format(
        petition_content=petition_content,
        clotho_assessment=clotho_assessment,
        lachesis_evaluation=lachesis_evaluation,
    )

    return Task(
        description=description,
        expected_output=(
            "A final disposition decision with format: "
            "DISPOSITION: [value], RATIONALE: [text], CONDITIONS: [text], DISSENT: [text]"
        ),
        agent=agent,
    )


def create_deliberation_tasks(
    clotho: Agent,
    lachesis: Agent,
    atropos: Agent,
    petition_content: str,
    petitioner_id: str = "ANON-001",
    petition_type: str = "GENERAL",
    submission_time: str = "2026-01-19T12:00:00Z",
) -> list[Task]:
    """Create all three deliberation tasks in sequence.

    Note: In actual CrewAI execution, the output of each task feeds
    into the next. This function creates the task templates.

    Args:
        clotho: The Clotho agent.
        lachesis: The Lachesis agent.
        atropos: The Atropos agent.
        petition_content: The petition text.
        petitioner_id: Identifier for the petitioner.
        petition_type: Category of petition.
        submission_time: ISO timestamp of submission.

    Returns:
        List of [assessment_task, position_task, vote_task].
    """
    # Phase 1: Assessment
    assessment_task = create_assessment_task(
        agent=clotho,
        petition_content=petition_content,
        petitioner_id=petitioner_id,
        petition_type=petition_type,
        submission_time=submission_time,
    )

    # For Phase 2 & 3, we use placeholders that will be filled at runtime
    # CrewAI's sequential process handles passing outputs between tasks
    position_task = Task(
        description=POSITION_TASK_TEMPLATE.format(
            petition_content=petition_content,
            clotho_assessment="{{assessment_task.output}}",
        ),
        expected_output=(
            "A structured evaluation containing: Constitutional Alignment, "
            "Precedent Analysis, Principle Evaluation, Merit Score (1-10), "
            "and Recommendation Tendency."
        ),
        agent=lachesis,
        context=[assessment_task],  # Depends on assessment
    )

    vote_task = Task(
        description=VOTE_TASK_TEMPLATE.format(
            petition_content=petition_content,
            clotho_assessment="{{assessment_task.output}}",
            lachesis_evaluation="{{position_task.output}}",
        ),
        expected_output=(
            "A final disposition decision with format: "
            "DISPOSITION: [value], RATIONALE: [text], CONDITIONS: [text], DISSENT: [text]"
        ),
        agent=atropos,
        context=[assessment_task, position_task],  # Depends on both
    )

    return [assessment_task, position_task, vote_task]


# =============================================================================
# Mock Task Execution (for testing without LLM)
# =============================================================================


@dataclass
class MockDeliberationResult:
    """Result of a mock deliberation."""

    clotho_assessment: str
    lachesis_evaluation: str
    atropos_disposition: str
    final_disposition: str
    execution_time_ms: float


def execute_mock_deliberation(
    clotho: MockFateAgent,
    lachesis: MockFateAgent,
    atropos: MockFateAgent,
    petition_content: str,
) -> MockDeliberationResult:
    """Execute a mock deliberation without LLM calls.

    Useful for testing the protocol flow and timing.

    Args:
        clotho: Mock Clotho agent.
        lachesis: Mock Lachesis agent.
        atropos: Mock Atropos agent.
        petition_content: The petition text.

    Returns:
        MockDeliberationResult with all phase outputs.
    """
    import time

    start = time.perf_counter()

    # Phase 1: Assessment
    clotho_assessment = f"""
## Assessment by {clotho.persona.name}

**Core Issue:** The petitioner requests consideration of their matter.
**Context:** Standard petition submission via the Conclave system.
**Key Facts:** Petition received and queued for deliberation.
**Missing Information:** None critical for initial assessment.
**Stakeholders:** Petitioner and the Conclave governance.
"""

    # Phase 2: Position
    lachesis_evaluation = f"""
## Evaluation by {lachesis.persona.name}

**Constitutional Alignment:** Petition follows proper submission protocol.
**Precedent:** Similar petitions have been processed successfully.
**Principles:** Aligns with transparency and accessibility pillars.
**Merit Score:** 6/10 - Standard petition with legitimate basis.
**Recommendation Tendency:** ACKNOWLEDGE
"""

    # Phase 3: Vote
    atropos_disposition = f"""
## Disposition by {atropos.persona.name}

**Synthesis:** Clotho found proper form, Lachesis confirmed merit.

DISPOSITION: ACKNOWLEDGE
RATIONALE: The petition has been properly submitted and reviewed.
CONDITIONS: None
DISSENT: None
"""

    execution_time_ms = (time.perf_counter() - start) * 1000

    return MockDeliberationResult(
        clotho_assessment=clotho_assessment,
        lachesis_evaluation=lachesis_evaluation,
        atropos_disposition=atropos_disposition,
        final_disposition=Disposition.ACKNOWLEDGE,
        execution_time_ms=execution_time_ms,
    )


# =============================================================================
# Disposition Extraction
# =============================================================================


def extract_disposition(atropos_output: str) -> str:
    """Extract the disposition value from Atropos's output.

    Args:
        atropos_output: The full output from Atropos.

    Returns:
        One of: ACKNOWLEDGE, REFER, ESCALATE, DEFER, NO_RESPONSE, or UNKNOWN.
    """
    output_upper = atropos_output.upper()

    # Look for explicit disposition line
    for line in output_upper.split("\n"):
        if "DISPOSITION:" in line:
            if "ACKNOWLEDGE" in line:
                return Disposition.ACKNOWLEDGE
            if "REFER" in line:
                return Disposition.REFER
            if "ESCALATE" in line:
                return Disposition.ESCALATE
            if "DEFER" in line:
                return Disposition.DEFER
            if "NO_RESPONSE" in line or "NO RESPONSE" in line:
                return Disposition.NO_RESPONSE

    # Fallback: look for keywords anywhere
    if "ESCALATE" in output_upper:
        return Disposition.ESCALATE
    if "REFER" in output_upper:
        return Disposition.REFER
    if "DEFER" in output_upper:
        return Disposition.DEFER
    if "NO_RESPONSE" in output_upper or "NO RESPONSE" in output_upper:
        return Disposition.NO_RESPONSE
    if "ACKNOWLEDGE" in output_upper:
        return Disposition.ACKNOWLEDGE

    return "UNKNOWN"
