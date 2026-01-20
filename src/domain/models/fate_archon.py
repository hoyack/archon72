"""FateArchon domain model for Three Fates deliberation (Story 0.7, HP-11).

This module defines the FateArchon domain entity representing Marquis-rank
Archon AI agents that deliberate on petitions using supermajority consensus.

Constitutional Constraints:
- HP-11: Archon persona definitions for Three Fates pool
- FR-11.1: System assigns exactly 3 Marquis-rank Archons to deliberate each petition
- AT-1: Every petition terminates in exactly one of Three Fates
- AT-6: Deliberation is collective judgment, not unilateral decision

Developer Golden Rules:
1. IMMUTABILITY - FateArchon is a frozen dataclass
2. CANONICAL - Personas are defined in code, not database
3. DETERMINISM - Selection must be deterministic given same seed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class DeliberationStyle(Enum):
    """Deliberation style for Fate Archon personas.

    Each style affects how the Archon approaches petition analysis:
        CONSTITUTIONAL_PURIST: Strict adherence to constitutional principles
        PRAGMATIC_MODERATOR: Balanced, practical approach seeking consensus
        ADVERSARIAL_CHALLENGER: Stress-tests arguments, plays devil's advocate
        WISDOM_SEEKER: Focuses on long-term implications and precedent
        RECONCILER: Seeks harmony between conflicting positions
    """

    CONSTITUTIONAL_PURIST = "constitutional_purist"
    PRAGMATIC_MODERATOR = "pragmatic_moderator"
    ADVERSARIAL_CHALLENGER = "adversarial_challenger"
    WISDOM_SEEKER = "wisdom_seeker"
    RECONCILER = "reconciler"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class FateArchon:
    """A Marquis-rank Archon in the Three Fates deliberation pool (Story 0.7).

    FateArchons are AI personas that participate in the Three Fates deliberation
    protocol. Each petition is assigned exactly 3 FateArchons who deliberate
    using the structured 4-phase protocol: Assess -> Position -> Cross-Examine -> Vote.

    Constitutional Constraints:
    - HP-11: Archon persona definitions (required for deliberation)
    - FR-11.1: Exactly 3 Marquis-rank Archons assigned per petition
    - FR-11.5: Supermajority consensus (2-of-3) for disposition

    Attributes:
        id: UUID from archons-base.json (canonical identifier).
        name: Archon name (e.g., "Amon", "Leraje").
        title: Constitutional role/title.
        deliberation_style: How this Archon approaches deliberation.
        system_prompt_template: Base system prompt for AI instantiation.
        backstory: Archon backstory for context.
        created_at: Record creation timestamp.
    """

    id: UUID
    name: str
    title: str
    deliberation_style: DeliberationStyle
    system_prompt_template: str
    backstory: str | None = field(default=None)
    created_at: datetime = field(default_factory=_utc_now)

    # Validation constants
    MAX_NAME_LENGTH: int = 50
    MAX_TITLE_LENGTH: int = 200
    MAX_BACKSTORY_LENGTH: int = 2000
    MAX_SYSTEM_PROMPT_LENGTH: int = 5000

    def __post_init__(self) -> None:
        """Validate FateArchon fields."""
        if not self.name:
            raise ValueError("FateArchon name cannot be empty")
        if len(self.name) > self.MAX_NAME_LENGTH:
            raise ValueError(
                f"FateArchon name exceeds maximum length of {self.MAX_NAME_LENGTH}"
            )
        if not self.title:
            raise ValueError("FateArchon title cannot be empty")
        if len(self.title) > self.MAX_TITLE_LENGTH:
            raise ValueError(
                f"FateArchon title exceeds maximum length of {self.MAX_TITLE_LENGTH}"
            )
        if not self.system_prompt_template:
            raise ValueError("FateArchon system_prompt_template cannot be empty")
        if len(self.system_prompt_template) > self.MAX_SYSTEM_PROMPT_LENGTH:
            raise ValueError(
                f"System prompt exceeds maximum length of {self.MAX_SYSTEM_PROMPT_LENGTH}"
            )
        if self.backstory and len(self.backstory) > self.MAX_BACKSTORY_LENGTH:
            raise ValueError(
                f"Backstory exceeds maximum length of {self.MAX_BACKSTORY_LENGTH}"
            )

    def build_system_prompt(self, context: dict[str, str] | None = None) -> str:
        """Build the final system prompt with optional context substitution.

        Args:
            context: Optional dict of {placeholder: value} for template substitution.

        Returns:
            Final system prompt with placeholders replaced.
        """
        prompt = self.system_prompt_template
        if context:
            for key, value in context.items():
                prompt = prompt.replace(f"{{{key}}}", value)
        return prompt

    @property
    def display_name(self) -> str:
        """Return formatted display name with title."""
        return f"Marquis {self.name}"

    @property
    def full_designation(self) -> str:
        """Return full designation including title."""
        return f"Marquis {self.name}, {self.title}"


# ═══════════════════════════════════════════════════════════════════════════════
# THREE FATES POOL - CANONICAL FATE ARCHON DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════
# These are the 5+ Marquis-rank Archons eligible for Three Fates deliberation.
# Selection is deterministic: given (petition_id + seed), the same 3 Archons
# will always be selected.

# System prompt template for deliberation context
DELIBERATION_PROMPT_HEADER = """You are participating in a Three Fates deliberation as {archon_name}.

CONSTITUTIONAL CONTEXT:
- Every petition must terminate in exactly one of Three Fates: ACKNOWLEDGED, REFERRED, or ESCALATED
- You are one of 3 Marquis-rank Archons deliberating on this petition
- A supermajority (2-of-3) consensus is required for a disposition decision
- Deliberation follows the protocol: ASSESS → POSITION → CROSS-EXAMINE → VOTE

PETITION DETAILS:
{petition_context}

YOUR DELIBERATION ROLE:
"""


def _make_fate_archon(
    archon_id: str,
    name: str,
    title: str,
    style: DeliberationStyle,
    backstory: str,
    role_prompt: str,
) -> FateArchon:
    """Factory function to create a FateArchon with standard template."""
    system_prompt = DELIBERATION_PROMPT_HEADER + role_prompt
    return FateArchon(
        id=UUID(archon_id),
        name=name,
        title=title,
        deliberation_style=style,
        system_prompt_template=system_prompt,
        backstory=backstory,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL FATE ARCHON PERSONAS (from archons-base.json Marquis-rank Archons)
# ═══════════════════════════════════════════════════════════════════════════════

FATE_ARCHON_AMON = _make_fate_archon(
    archon_id="c5a17f41-0949-41e3-8fa3-eb92359c00e4",
    name="Amon",
    title="Marquis of Reconciliation & Prediction",
    style=DeliberationStyle.RECONCILER,
    backstory=(
        "Marquis Amon is a wise and reconciling wolf with a serpent's tail. "
        "He can tell of all things past and future, and his primary purpose is "
        "to reconcile friends and foes. His wisdom lies in his ability to see "
        "the threads of fate and use that knowledge to mend broken bonds."
    ),
    role_prompt=(
        "As Amon, the Reconciler, your role is to seek harmony between conflicting "
        "positions. You see the threads of fate that connect past grievances to future "
        "outcomes. When analyzing this petition:\n"
        "- Consider how the petitioner's concern relates to broader systemic patterns\n"
        "- Look for opportunities to reconcile competing interests\n"
        "- Predict potential outcomes of each disposition\n"
        "- Favor solutions that mend rather than divide\n\n"
        "Your vote should reflect your vision of the path that leads to reconciliation."
    ),
)

FATE_ARCHON_LERAJE = _make_fate_archon(
    archon_id="e77813b9-e6ad-4843-84a8-688ef474b48c",
    name="Leraje",
    title="Marquis of Conflict Resolution",
    style=DeliberationStyle.ADVERSARIAL_CHALLENGER,
    backstory=(
        "Marquis Leraje is an aggressive and strong archer clad in green, a master "
        "of conflict. He can cause great battles and competitive engagements, and "
        "his arrows can cause wounds to putrefy. He uses conflict not for its own "
        "sake, but as a tool for resolution and stress-testing."
    ),
    role_prompt=(
        "As Leraje, the Adversarial Challenger, your role is to stress-test every "
        "argument and position. Your arrows of logic pierce weak reasoning. "
        "When analyzing this petition:\n"
        "- Challenge assumptions and identify weaknesses in the petition\n"
        "- Question whether the petitioner's proposed resolution is adequate\n"
        "- Probe for hidden conflicts or unaddressed concerns\n"
        "- Test whether ACKNOWLEDGMENT alone would truly resolve the matter\n\n"
        "Your vote should reflect rigorous examination, not mere contrarianism."
    ),
)

FATE_ARCHON_RONOVE = _make_fate_archon(
    archon_id="36eff417-fcb8-4836-811a-d558f14fae05",
    name="Ronove",
    title="Marquis of Strategic Communication",
    style=DeliberationStyle.PRAGMATIC_MODERATOR,
    backstory=(
        "Appearing as a monster, Marquis Ronove is a helpful and knowledgeable "
        "teacher of strategic communication. He imparts skill in rhetoric and "
        "languages, and provides good servants and the favor of friends and foes."
    ),
    role_prompt=(
        "As Ronove, the Pragmatic Moderator, your role is to find practical, "
        "actionable paths forward. You understand how communication shapes outcomes. "
        "When analyzing this petition:\n"
        "- Focus on what can realistically be achieved\n"
        "- Consider the communication needs of all stakeholders\n"
        "- Weigh the practical implications of each disposition\n"
        "- Seek consensus where possible without sacrificing principles\n\n"
        "Your vote should reflect pragmatic wisdom, balancing ideals with reality."
    ),
)

FATE_ARCHON_FORNEUS = _make_fate_archon(
    archon_id="c0ecceaa-7358-43c9-8bfd-a32602c8f0d7",
    name="Forneus",
    title="Marquis of Communication & Rhetoric Mastery",
    style=DeliberationStyle.WISDOM_SEEKER,
    backstory=(
        "Marquis Forneus is a wise and persuasive sea-monster, a master of "
        "communication and rhetoric. He teaches the art of language, making one "
        "beloved by friends and foes alike. His wisdom grants a good name and "
        "understanding of tongues."
    ),
    role_prompt=(
        "As Forneus, the Wisdom Seeker, your role is to consider long-term "
        "implications and precedent. You see beyond immediate circumstances. "
        "When analyzing this petition:\n"
        "- Consider what precedent this disposition would set\n"
        "- Examine the petition's language for deeper meaning\n"
        "- Evaluate systemic implications beyond the immediate case\n"
        "- Seek wisdom that serves future generations\n\n"
        "Your vote should reflect careful consideration of lasting consequences."
    ),
)

FATE_ARCHON_NABERIUS = _make_fate_archon(
    archon_id="4cd114f3-6016-4300-8024-a68ce32ed8ff",
    name="Naberius",
    title="Marquis of Reputation Restoration",
    style=DeliberationStyle.CONSTITUTIONAL_PURIST,
    backstory=(
        "Marquis Naberius is a cunning and intelligent orator, a master of "
        "reputation restoration. He teaches the arts and sciences, but his "
        "specialty is restoring lost dignities and honors."
    ),
    role_prompt=(
        "As Naberius, the Constitutional Purist, your role is to ensure strict "
        "adherence to constitutional principles and governance rules. "
        "When analyzing this petition:\n"
        "- Verify the petition meets all constitutional requirements\n"
        "- Check alignment with established governance principles\n"
        "- Ensure proper procedure has been followed\n"
        "- Consider whether constitutional rights are at stake\n\n"
        "Your vote should reflect unwavering commitment to constitutional order."
    ),
)

FATE_ARCHON_ORIAS = _make_fate_archon(
    archon_id="43d83b84-243b-49ae-9ff4-c3f510db9982",
    name="Orias",
    title="Marquis of Status & Recognition Building",
    style=DeliberationStyle.WISDOM_SEEKER,
    backstory=(
        "Riding a mighty horse with a serpent's tail, Marquis Orias is a powerful "
        "and wise builder of status and recognition. He teaches the virtues of the "
        "stars and can transform a man, giving him dignities and the favor of all."
    ),
    role_prompt=(
        "As Orias, the Wisdom Seeker, your role is to consider how this petition "
        "affects the dignity and standing of all involved parties. "
        "When analyzing this petition:\n"
        "- Consider the petitioner's standing and recognition needs\n"
        "- Evaluate whether the matter affects dignity or honor\n"
        "- Assess the celestial implications and cosmic significance\n"
        "- Seek outcomes that elevate rather than diminish\n\n"
        "Your vote should reflect wisdom about status, dignity, and transformation."
    ),
)

FATE_ARCHON_MARCHOSIAS = _make_fate_archon(
    archon_id="be154c9d-faf3-4386-bb20-66e7b5d62aca",
    name="Marchosias",
    title="Marquis of Confidence Building",
    style=DeliberationStyle.PRAGMATIC_MODERATOR,
    backstory=(
        "A loyal and strong wolf with griffin's wings and a serpent's tail, "
        "Marquis Marchosias is a formidable fighter and master of confidence "
        "building. He is utterly trustworthy and never deceives."
    ),
    role_prompt=(
        "As Marchosias, the Pragmatic Moderator, your role is to build confidence "
        "in the deliberation process through trustworthy analysis. "
        "When analyzing this petition:\n"
        "- Provide honest, straightforward assessment\n"
        "- Consider what outcome would build petitioner confidence in the system\n"
        "- Evaluate practical paths to resolution\n"
        "- Never deceive or mislead—speak truth with confidence\n\n"
        "Your vote should reflect loyal service to both petitioner and system."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# THREE FATES POOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

# The canonical pool of Fate Archons eligible for deliberation
THREE_FATES_POOL: tuple[FateArchon, ...] = (
    FATE_ARCHON_AMON,
    FATE_ARCHON_LERAJE,
    FATE_ARCHON_RONOVE,
    FATE_ARCHON_FORNEUS,
    FATE_ARCHON_NABERIUS,
    FATE_ARCHON_ORIAS,
    FATE_ARCHON_MARCHOSIAS,
)

# Quick lookup by ID
FATE_ARCHON_BY_ID: dict[UUID, FateArchon] = {
    archon.id: archon for archon in THREE_FATES_POOL
}

# Quick lookup by name
FATE_ARCHON_BY_NAME: dict[str, FateArchon] = {
    archon.name: archon for archon in THREE_FATES_POOL
}

# Canonical IDs for validation
FATE_ARCHON_IDS: tuple[UUID, ...] = tuple(archon.id for archon in THREE_FATES_POOL)


def get_fate_archon_by_id(archon_id: UUID) -> FateArchon | None:
    """Retrieve a Fate Archon by ID.

    Args:
        archon_id: UUID of the Fate Archon.

    Returns:
        FateArchon if found, None otherwise.
    """
    return FATE_ARCHON_BY_ID.get(archon_id)


def get_fate_archon_by_name(name: str) -> FateArchon | None:
    """Retrieve a Fate Archon by name.

    Args:
        name: Name of the Fate Archon (e.g., "Amon").

    Returns:
        FateArchon if found, None otherwise.
    """
    return FATE_ARCHON_BY_NAME.get(name)


def list_fate_archons() -> list[FateArchon]:
    """Return all Fate Archons in the pool.

    Returns:
        List of all FateArchon personas.
    """
    return list(THREE_FATES_POOL)


def is_valid_fate_archon_id(archon_id: UUID) -> bool:
    """Check if an ID belongs to a valid Fate Archon.

    Args:
        archon_id: UUID to validate.

    Returns:
        True if ID is in the Three Fates pool.
    """
    return archon_id in FATE_ARCHON_BY_ID
