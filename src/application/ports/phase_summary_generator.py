"""Phase summary generator protocol (Story 7.5, FR-7.4, AC-1).

This module defines the protocol for generating phase summaries during
deliberation. Phase summaries provide Observer-tier access to deliberation
content without exposing raw transcript text.

Constitutional Constraints:
- Ruling-2: Tiered transcript access - mediated, not raw
- FR-7.4: System SHALL provide deliberation summary to Observer
- AC-1: Phase summary includes themes, duration, convergence indicator
- NO VERBATIM QUOTES: Summary must be derived, not excerpted

Usage:
    from src.application.ports.phase_summary_generator import (
        PhaseSummaryGeneratorProtocol,
    )

    class MyService:
        def __init__(self, summary_generator: PhaseSummaryGeneratorProtocol) -> None:
            self._summary_generator = summary_generator

        async def complete_phase(
            self, phase: DeliberationPhase, transcript: str
        ) -> dict[str, Any]:
            return await self._summary_generator.generate_phase_summary(
                phase=phase,
                transcript=transcript,
            )
"""

from __future__ import annotations

from typing import Any, Protocol

from src.domain.models.deliberation_session import DeliberationPhase


class PhaseSummaryGeneratorProtocol(Protocol):
    """Protocol for generating phase summaries (Story 7.5, AC-1).

    Implementations generate mediated summaries from raw transcript text.
    Summaries include themes, convergence indicators, and challenge counts
    but NEVER include verbatim transcript quotes.

    Constitutional Constraints:
    - Ruling-2: Mediated access only
    - AC-1: Summary includes phase name, duration, themes, convergence
    - AC-3-6: Phase-specific content requirements
    - NO VERBATIM QUOTES

    The returned dictionary must include:
    - themes: list[str] - 3-5 key topics/keywords extracted
    - convergence_reached: bool | None - position alignment indicator
    - challenge_count: int | None - for CROSS_EXAMINE phase only

    Implementations:
    - PhaseSummaryGenerationService: Production implementation using heuristics
    - PhaseSummaryGeneratorStub: Test stub with configurable responses
    """

    async def generate_phase_summary(
        self,
        phase: DeliberationPhase,
        transcript: str,
    ) -> dict[str, Any]:
        """Generate a mediated summary for a completed phase (AC-1).

        Extracts key themes, convergence indicators, and challenge counts
        from the raw transcript text WITHOUT including verbatim quotes.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text from the phase.

        Returns:
            Dictionary containing:
            - themes: list[str] - 3-5 key topics extracted from transcript
            - convergence_reached: bool | None - whether positions aligned
              (None for ASSESS phase which has no prior positions)
            - challenge_count: int | None - count of challenges raised
              (only populated for CROSS_EXAMINE phase)

        Raises:
            ValueError: If transcript is empty or phase is invalid.

        Note:
            The returned dictionary is intended to be passed as part of
            phase_metadata to PhaseWitnessBatchingService.witness_phase().
        """
        ...

    async def augment_phase_metadata(
        self,
        phase: DeliberationPhase,
        transcript: str,
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Augment phase metadata with generated summary fields (AC-1, AC-2).

        Convenience method that generates a phase summary and merges it
        with existing metadata. Used to prepare metadata for witness_phase()
        calls.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text from the phase.
            existing_metadata: Existing metadata to merge with (optional).

        Returns:
            Dictionary with existing metadata plus summary fields.

        Raises:
            ValueError: If transcript is empty or phase is COMPLETE.
        """
        ...
