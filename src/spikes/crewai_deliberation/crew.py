"""Deliberation Crew Orchestration.

Orchestrates the Three Fates in a sequential deliberation process.

Reference: petition-system-prd.md Section 13A
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task

from .agents import (
    ATROPOS_PERSONA,
    CLOTHO_PERSONA,
    LACHESIS_PERSONA,
    Disposition,
    create_three_fates,
)
from .tasks import (
    create_assessment_task,
    create_deliberation_tasks,
    create_position_task,
    create_vote_task,
    extract_disposition,
)


# =============================================================================
# Deliberation Result Types
# =============================================================================


@dataclass
class PhaseResult:
    """Result of a single deliberation phase."""

    phase_name: str
    agent_name: str
    output: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeliberationResult:
    """Complete result of a Three Fates deliberation."""

    petition_id: str
    petition_content: str

    # Phase results
    assessment: PhaseResult | None = None
    evaluation: PhaseResult | None = None
    decision: PhaseResult | None = None

    # Final outcome
    disposition: str = "PENDING"
    rationale: str = ""

    # Timing
    total_execution_time_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # Metadata
    crew_output_raw: str = ""
    error: str | None = None

    @property
    def is_complete(self) -> bool:
        """Check if deliberation completed successfully."""
        return (
            self.assessment is not None
            and self.evaluation is not None
            and self.decision is not None
            and self.disposition != "PENDING"
        )


# =============================================================================
# Deliberation Crew
# =============================================================================


class DeliberationCrew:
    """Orchestrates Three Fates deliberation on petitions.

    Uses CrewAI's sequential process to execute:
    1. Clotho's assessment
    2. Lachesis's evaluation
    3. Atropos's decision

    Example:
        ```python
        crew = DeliberationCrew()
        result = crew.deliberate(petition_content="I request...")
        print(result.disposition)  # ACKNOWLEDGE, REFER, or ESCALATE
        ```
    """

    def __init__(
        self,
        llm: LLM | None = None,
        verbose: bool = True,
        temperature: float = 0.0,
    ) -> None:
        """Initialize the deliberation crew.

        Args:
            llm: Optional LLM instance. If None, uses CrewAI default.
            verbose: Whether to enable verbose output.
            temperature: LLM temperature (0.0 for determinism).
        """
        self.llm = llm
        self.verbose = verbose
        self.temperature = temperature

        # Create the three Fates
        self.clotho, self.lachesis, self.atropos = create_three_fates(
            llm=llm,
            verbose=verbose,
            temperature=temperature,
        )

    def deliberate(
        self,
        petition_content: str,
        petition_id: str = "PET-001",
        petitioner_id: str = "ANON-001",
        petition_type: str = "GENERAL",
    ) -> DeliberationResult:
        """Execute a full Three Fates deliberation.

        Args:
            petition_content: The petition text to deliberate on.
            petition_id: Unique identifier for this petition.
            petitioner_id: Identifier for the petitioner.
            petition_type: Category of petition.

        Returns:
            DeliberationResult with all phase outputs and final disposition.
        """
        import time

        result = DeliberationResult(
            petition_id=petition_id,
            petition_content=petition_content,
        )

        start_time = time.perf_counter()

        try:
            # Create tasks for the deliberation
            tasks = create_deliberation_tasks(
                clotho=self.clotho,
                lachesis=self.lachesis,
                atropos=self.atropos,
                petition_content=petition_content,
                petitioner_id=petitioner_id,
                petition_type=petition_type,
            )

            # Create and execute the crew
            crew = Crew(
                agents=[self.clotho, self.lachesis, self.atropos],
                tasks=tasks,
                process=Process.sequential,
                verbose=self.verbose,
            )

            # Execute deliberation
            crew_output = crew.kickoff()

            # Record raw output
            result.crew_output_raw = str(crew_output)

            # Extract disposition from final output
            result.disposition = extract_disposition(str(crew_output))

            # Parse phase results from crew output
            # Note: CrewAI's output structure may vary by version
            result = self._parse_crew_output(result, crew_output, tasks)

        except Exception as e:
            result.error = str(e)
            result.disposition = "ERROR"

        finally:
            result.total_execution_time_ms = (time.perf_counter() - start_time) * 1000
            result.completed_at = datetime.now(timezone.utc)

        return result

    async def deliberate_async(
        self,
        petition_content: str,
        petition_id: str = "PET-001",
        petitioner_id: str = "ANON-001",
        petition_type: str = "GENERAL",
    ) -> DeliberationResult:
        """Async version of deliberate.

        Args:
            petition_content: The petition text to deliberate on.
            petition_id: Unique identifier for this petition.
            petitioner_id: Identifier for the petitioner.
            petition_type: Category of petition.

        Returns:
            DeliberationResult with all phase outputs and final disposition.
        """
        import time

        result = DeliberationResult(
            petition_id=petition_id,
            petition_content=petition_content,
        )

        start_time = time.perf_counter()

        try:
            # Create tasks for the deliberation
            tasks = create_deliberation_tasks(
                clotho=self.clotho,
                lachesis=self.lachesis,
                atropos=self.atropos,
                petition_content=petition_content,
                petitioner_id=petitioner_id,
                petition_type=petition_type,
            )

            # Create the crew
            crew = Crew(
                agents=[self.clotho, self.lachesis, self.atropos],
                tasks=tasks,
                process=Process.sequential,
                verbose=self.verbose,
            )

            # Execute deliberation asynchronously
            crew_output = await crew.kickoff_async()

            # Record raw output
            result.crew_output_raw = str(crew_output)

            # Extract disposition from final output
            result.disposition = extract_disposition(str(crew_output))

            # Parse phase results
            result = self._parse_crew_output(result, crew_output, tasks)

        except Exception as e:
            result.error = str(e)
            result.disposition = "ERROR"

        finally:
            result.total_execution_time_ms = (time.perf_counter() - start_time) * 1000
            result.completed_at = datetime.now(timezone.utc)

        return result

    def _parse_crew_output(
        self,
        result: DeliberationResult,
        crew_output: Any,
        tasks: list[Task],
    ) -> DeliberationResult:
        """Parse CrewAI output into structured phase results.

        Args:
            result: The DeliberationResult to populate.
            crew_output: Raw output from CrewAI.
            tasks: The tasks that were executed.

        Returns:
            Updated DeliberationResult.
        """
        # CrewAI output handling varies by version
        # This is a best-effort extraction
        try:
            output_str = str(crew_output)

            # For now, store the full output in each phase
            # In production, we'd parse the structured output more carefully
            result.assessment = PhaseResult(
                phase_name="Assessment",
                agent_name=CLOTHO_PERSONA.name,
                output=output_str,  # Would extract just Clotho's part
                execution_time_ms=0.0,  # Would measure per-phase
            )

            result.evaluation = PhaseResult(
                phase_name="Evaluation",
                agent_name=LACHESIS_PERSONA.name,
                output=output_str,  # Would extract just Lachesis's part
                execution_time_ms=0.0,
            )

            result.decision = PhaseResult(
                phase_name="Decision",
                agent_name=ATROPOS_PERSONA.name,
                output=output_str,  # Would extract just Atropos's part
                execution_time_ms=0.0,
            )

        except Exception:
            # If parsing fails, we still have the raw output and disposition
            pass

        return result


# =============================================================================
# Utility Functions
# =============================================================================


def create_deliberation_crew(
    llm: LLM | None = None,
    verbose: bool = True,
    temperature: float = 0.0,
) -> DeliberationCrew:
    """Factory function to create a configured deliberation crew.

    Args:
        llm: Optional LLM instance.
        verbose: Whether to enable verbose output.
        temperature: LLM temperature for reproducibility.

    Returns:
        Configured DeliberationCrew.
    """
    return DeliberationCrew(llm=llm, verbose=verbose, temperature=temperature)
