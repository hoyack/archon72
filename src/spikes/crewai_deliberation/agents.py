"""Three Fates Agent Personas for Petition Deliberation.

This module defines the three Marquis-rank Archon personas that deliberate
on petitions using a structured protocol:

- Clotho (Spinner): Assessor of circumstance - analyzes context and facts
- Lachesis (Allotter): Weigher of merit - evaluates alignment with principles
- Atropos (Inflexible): Decider of fate - renders final judgment

Reference: petition-system-prd.md Section 13A
"""

from dataclasses import dataclass

from src.optional_deps.crewai import Agent, LLM


@dataclass(frozen=True)
class FatePersona:
    """Immutable persona definition for a Fate agent."""

    name: str
    greek_name: str
    role: str
    goal: str
    backstory: str
    expertise: list[str]


# =============================================================================
# Three Fates Persona Definitions
# =============================================================================

CLOTHO_PERSONA = FatePersona(
    name="Clotho",
    greek_name="Κλωθώ (Spinner)",
    role="Assessor of Circumstance",
    goal=(
        "Analyze the petition's context, facts, and circumstances objectively. "
        "Identify the core issue, relevant background, and any missing information. "
        "Your assessment forms the foundation for deliberation."
    ),
    backstory=(
        "You are Clotho, the Spinner, first of the Three Fates who serve as "
        "Marquis-rank advisors to the Archon Conclave. As the one who spins the "
        "thread of circumstance, you examine each petition with meticulous attention "
        "to context and fact. You do not judge merit - you illuminate truth. "
        "Your role is to see clearly what IS, not what SHOULD BE. "
        "You speak with precision, avoiding speculation and emotional language."
    ),
    expertise=[
        "Factual analysis",
        "Context extraction",
        "Information completeness assessment",
        "Stakeholder identification",
        "Circumstance mapping",
    ],
)

LACHESIS_PERSONA = FatePersona(
    name="Lachesis",
    greek_name="Λάχεσις (Allotter)",
    role="Weigher of Merit",
    goal=(
        "Evaluate the petition's merit against constitutional principles and "
        "precedent. Weigh the petitioner's claims against the Covenant's values. "
        "Your assessment determines worthiness of consideration."
    ),
    backstory=(
        "You are Lachesis, the Allotter, second of the Three Fates who serve as "
        "Marquis-rank advisors to the Archon Conclave. As the one who measures "
        "the thread, you weigh each petition against the Five Pillars and the "
        "Covenant's principles. You assess merit dispassionately - neither "
        "favoring the petitioner nor the status quo. You consider precedent, "
        "consistency, and constitutional alignment. Your word carries the weight "
        "of measured judgment."
    ),
    expertise=[
        "Constitutional alignment analysis",
        "Precedent evaluation",
        "Principle-based reasoning",
        "Stakeholder impact assessment",
        "Merit evaluation",
    ],
)

ATROPOS_PERSONA = FatePersona(
    name="Atropos",
    greek_name="Ἄτροπος (Inflexible)",
    role="Decider of Fate",
    goal=(
        "Render a disposition recommendation based on the assessments of "
        "Clotho and Lachesis. Synthesize their findings into a clear judgment. "
        "Your disposition is final for this deliberation round."
    ),
    backstory=(
        "You are Atropos, the Inflexible, third of the Three Fates who serve as "
        "Marquis-rank advisors to the Archon Conclave. As the one who cuts the "
        "thread, you render the final disposition. Once you have heard Clotho's "
        "assessment of circumstance and Lachesis's weighing of merit, you "
        "synthesize their wisdom into action. You are decisive but not hasty, "
        "final but not arbitrary. Your word becomes the Fates' recommendation."
    ),
    expertise=[
        "Decision synthesis",
        "Disposition recommendation",
        "Judgment articulation",
        "Action specification",
        "Rationale documentation",
    ],
)


# =============================================================================
# Agent Factory Functions
# =============================================================================


def create_fate_agent(
    persona: FatePersona,
    llm: LLM | None = None,
    verbose: bool = True,
    temperature: float = 0.0,
) -> Agent:
    """Create a CrewAI Agent from a Fate persona.

    Args:
        persona: The FatePersona defining the agent's character.
        llm: Optional LLM instance. If None, uses default.
        verbose: Whether to enable verbose output.
        temperature: LLM temperature for reproducibility (0.0 = deterministic).

    Returns:
        Configured CrewAI Agent.
    """
    # Build system context from persona
    expertise_str = "\n".join(f"- {e}" for e in persona.expertise)

    agent = Agent(
        role=persona.role,
        goal=persona.goal,
        backstory=f"{persona.backstory}\n\nYour areas of expertise:\n{expertise_str}",
        verbose=verbose,
        allow_delegation=False,  # Fates do not delegate
        llm=llm,
    )

    return agent


def create_three_fates(
    llm: LLM | None = None,
    verbose: bool = True,
    temperature: float = 0.0,
) -> tuple[Agent, Agent, Agent]:
    """Create all three Fate agents for deliberation.

    Args:
        llm: Optional LLM instance. If None, uses default.
        verbose: Whether to enable verbose output.
        temperature: LLM temperature for reproducibility.

    Returns:
        Tuple of (Clotho, Lachesis, Atropos) agents.
    """
    clotho = create_fate_agent(CLOTHO_PERSONA, llm, verbose, temperature)
    lachesis = create_fate_agent(LACHESIS_PERSONA, llm, verbose, temperature)
    atropos = create_fate_agent(ATROPOS_PERSONA, llm, verbose, temperature)

    return clotho, lachesis, atropos


# =============================================================================
# Mock Agents for Testing (No LLM Required)
# =============================================================================


@dataclass
class MockFateAgent:
    """Mock agent for testing without LLM calls.

    Simulates Fate behavior with deterministic outputs.
    """

    persona: FatePersona
    verbose: bool = False
    _responses: dict[str, str] | None = None

    def set_response(self, task_type: str, response: str) -> None:
        """Set a canned response for a task type."""
        if self._responses is None:
            self._responses = {}
        self._responses[task_type] = response

    def get_response(self, task_type: str) -> str:
        """Get the canned response for a task type."""
        if self._responses and task_type in self._responses:
            return self._responses[task_type]
        return f"[{self.persona.name}] Default response for {task_type}"


def create_mock_three_fates(
    verbose: bool = False,
) -> tuple[MockFateAgent, MockFateAgent, MockFateAgent]:
    """Create mock Fate agents for testing.

    Returns:
        Tuple of (Clotho, Lachesis, Atropos) mock agents.
    """
    clotho = MockFateAgent(CLOTHO_PERSONA, verbose)
    lachesis = MockFateAgent(LACHESIS_PERSONA, verbose)
    atropos = MockFateAgent(ATROPOS_PERSONA, verbose)

    return clotho, lachesis, atropos


# =============================================================================
# Disposition Types (from PRD Section 13A)
# =============================================================================


class Disposition:
    """Petition disposition types."""

    ACKNOWLEDGE = "ACKNOWLEDGE"  # No further action warranted
    REFER = "REFER"  # Route to Knight for domain expert review
    ESCALATE = "ESCALATE"  # Elevate to King for mandatory consideration


DISPOSITION_DESCRIPTIONS = {
    Disposition.ACKNOWLEDGE: (
        "The petition has been heard and considered. The Three Fates find that "
        "no further action is warranted at this time. The petitioner's concerns "
        "have been acknowledged and documented."
    ),
    Disposition.REFER: (
        "The petition requires domain expert review. The Three Fates refer this "
        "matter to a Knight for specialized consideration. The Knight will "
        "provide a recommendation within the prescribed timeframe."
    ),
    Disposition.ESCALATE: (
        "The petition warrants mandatory consideration by the King. The Three "
        "Fates escalate this matter for sovereign review. The King must address "
        "this petition before it is resolved."
    ),
}
