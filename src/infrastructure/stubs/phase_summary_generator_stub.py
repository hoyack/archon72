"""Phase summary generator stub (Story 7.5, AC-All).

This module provides a test stub implementation of PhaseSummaryGeneratorProtocol
for use in unit and integration tests. The stub returns predictable, configurable
responses without performing actual transcript analysis.

Constitutional Constraints:
- Ruling-2: Stub responses follow mediated access pattern (no verbatim quotes)
- AC-All: Stub supports testing all acceptance criteria

Usage:
    from src.infrastructure.stubs.phase_summary_generator_stub import (
        PhaseSummaryGeneratorStub,
    )

    # Default behavior - returns phase-appropriate defaults
    stub = PhaseSummaryGeneratorStub()
    summary = await stub.generate_phase_summary(
        phase=DeliberationPhase.ASSESS,
        transcript="...",
    )

    # Configured responses for specific test scenarios
    stub = PhaseSummaryGeneratorStub(
        themes=["custom", "themes"],
        convergence_reached=True,
        challenge_count=5,
    )

    # Configured to raise an error
    stub = PhaseSummaryGeneratorStub(raise_error=ValueError("Test error"))
"""

from __future__ import annotations

from typing import Any

from src.domain.models.deliberation_session import DeliberationPhase

# Default themes for test scenarios
DEFAULT_THEMES: list[str] = ["governance", "resource", "transparency", "accountability"]


class PhaseSummaryGeneratorStub:
    """Test stub for PhaseSummaryGeneratorProtocol (Story 7.5).

    Provides configurable responses for testing phase summary generation
    without performing actual transcript analysis. Supports:
    - Default phase-appropriate responses
    - Custom configured responses
    - Error injection for failure testing

    Attributes:
        themes: Custom themes to return (or None for defaults).
        convergence_reached: Custom convergence value (or None for phase-based default).
        challenge_count: Custom challenge count (or None for phase-based default).
        raise_error: Exception to raise (for testing error handling).
        calls: List of (phase, transcript) tuples for each call made.
    """

    def __init__(
        self,
        themes: list[str] | None = None,
        convergence_reached: bool | None = None,
        challenge_count: int | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        """Initialize the stub with optional configured responses.

        Args:
            themes: Custom themes to return. If None, uses DEFAULT_THEMES.
            convergence_reached: Custom convergence value. If None, uses
                phase-based defaults (None for ASSESS, True/False for others).
            challenge_count: Custom challenge count. If None, uses phase-based
                default (only populated for CROSS_EXAMINE).
            raise_error: Exception to raise when generate_phase_summary is called.
                Use this for testing error handling paths.
        """
        self._themes = themes
        self._convergence_reached = convergence_reached
        self._challenge_count = challenge_count
        self._raise_error = raise_error
        self.calls: list[tuple[DeliberationPhase, str]] = []

    async def generate_phase_summary(
        self,
        phase: DeliberationPhase,
        transcript: str,
    ) -> dict[str, Any]:
        """Generate a stub phase summary.

        Records the call for test assertions and returns configured
        or phase-appropriate default responses.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text (recorded but not analyzed).

        Returns:
            Dictionary with themes, convergence_reached, challenge_count.

        Raises:
            Exception: If raise_error was configured.
            ValueError: If transcript is empty (matches real service behavior).
        """
        # Record the call for test assertions
        self.calls.append((phase, transcript))

        # Raise configured error if set
        if self._raise_error is not None:
            raise self._raise_error

        # Validate like real service
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")

        if phase == DeliberationPhase.COMPLETE:
            raise ValueError("Cannot generate summary for COMPLETE phase")

        # Determine themes
        themes = self._themes if self._themes is not None else DEFAULT_THEMES.copy()

        # Build phase-specific response
        if phase == DeliberationPhase.ASSESS:
            # ASSESS has no convergence or challenge count
            return {
                "themes": themes,
                "convergence_reached": None,
                "challenge_count": None,
            }
        elif phase == DeliberationPhase.POSITION:
            # POSITION has convergence but no challenge count
            convergence = (
                self._convergence_reached
                if self._convergence_reached is not None
                else True
            )
            return {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": None,
            }
        elif phase == DeliberationPhase.CROSS_EXAMINE:
            # CROSS_EXAMINE has convergence and challenge count
            convergence = (
                self._convergence_reached
                if self._convergence_reached is not None
                else False
            )
            challenge_count = (
                self._challenge_count if self._challenge_count is not None else 3
            )
            return {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": challenge_count,
            }
        elif phase == DeliberationPhase.VOTE:
            # VOTE has convergence (True if unanimous)
            convergence = (
                self._convergence_reached
                if self._convergence_reached is not None
                else True
            )
            return {
                "themes": themes,
                "convergence_reached": convergence,
                "challenge_count": None,
            }
        else:
            raise ValueError(f"Invalid phase: {phase}")

    def reset(self) -> None:
        """Reset call history for reuse in multiple tests."""
        self.calls.clear()

    @property
    def call_count(self) -> int:
        """Get the number of times generate_phase_summary was called."""
        return len(self.calls)

    def was_called_with_phase(self, phase: DeliberationPhase) -> bool:
        """Check if generate_phase_summary was called with the given phase."""
        return any(call_phase == phase for call_phase, _ in self.calls)

    def get_transcript_for_phase(self, phase: DeliberationPhase) -> str | None:
        """Get the transcript that was passed for a specific phase call."""
        for call_phase, transcript in self.calls:
            if call_phase == phase:
                return transcript
        return None

    async def augment_phase_metadata(
        self,
        phase: DeliberationPhase,
        transcript: str,
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Augment phase metadata with generated summary fields (AC-1, AC-2).

        Stub implementation that generates summary and merges with existing.

        Args:
            phase: The deliberation phase that completed.
            transcript: Raw transcript text from the phase.
            existing_metadata: Existing metadata to merge with (optional).

        Returns:
            Dictionary with existing metadata plus summary fields.

        Raises:
            ValueError: If transcript is empty or phase is COMPLETE.
        """
        # Generate summary (which also records the call)
        summary = await self.generate_phase_summary(phase, transcript)

        # Merge with existing metadata
        result: dict[str, Any] = dict(existing_metadata) if existing_metadata else {}
        result.update(summary)

        return result
