"""Unit tests for CrewAI Three Fates Deliberation Spike.

Tests the deliberation protocol without requiring real LLM calls.
"""

from __future__ import annotations

import pytest

from src.spikes.crewai_deliberation.agents import (
    ATROPOS_PERSONA,
    CLOTHO_PERSONA,
    LACHESIS_PERSONA,
    Disposition,
    FatePersona,
    MockFateAgent,
    create_mock_three_fates,
)
from src.spikes.crewai_deliberation.tasks import (
    execute_mock_deliberation,
    extract_disposition,
)


class TestFatePersonas:
    """Tests for Fate persona definitions."""

    def test_clotho_persona_defined(self) -> None:
        """Verify Clotho persona has required fields."""
        assert CLOTHO_PERSONA.name == "Clotho"
        assert CLOTHO_PERSONA.role == "Assessor of Circumstance"
        assert len(CLOTHO_PERSONA.expertise) >= 3
        assert "Factual analysis" in CLOTHO_PERSONA.expertise

    def test_lachesis_persona_defined(self) -> None:
        """Verify Lachesis persona has required fields."""
        assert LACHESIS_PERSONA.name == "Lachesis"
        assert LACHESIS_PERSONA.role == "Weigher of Merit"
        assert len(LACHESIS_PERSONA.expertise) >= 3
        assert "Constitutional alignment analysis" in LACHESIS_PERSONA.expertise

    def test_atropos_persona_defined(self) -> None:
        """Verify Atropos persona has required fields."""
        assert ATROPOS_PERSONA.name == "Atropos"
        assert ATROPOS_PERSONA.role == "Decider of Fate"
        assert len(ATROPOS_PERSONA.expertise) >= 3
        assert "Disposition recommendation" in ATROPOS_PERSONA.expertise

    def test_personas_are_distinct(self) -> None:
        """Verify each Fate has unique role and goal."""
        personas = [CLOTHO_PERSONA, LACHESIS_PERSONA, ATROPOS_PERSONA]

        names = [p.name for p in personas]
        roles = [p.role for p in personas]
        goals = [p.goal for p in personas]

        assert len(set(names)) == 3, "Names not unique"
        assert len(set(roles)) == 3, "Roles not unique"
        assert len(set(goals)) == 3, "Goals not unique"


class TestMockFateAgents:
    """Tests for mock Fate agents."""

    def test_create_mock_three_fates(self) -> None:
        """Verify mock agent creation."""
        clotho, lachesis, atropos = create_mock_three_fates()

        assert clotho.persona.name == "Clotho"
        assert lachesis.persona.name == "Lachesis"
        assert atropos.persona.name == "Atropos"

    def test_mock_agent_response(self) -> None:
        """Verify mock agents can set and return responses."""
        clotho, _, _ = create_mock_three_fates()

        clotho.set_response("assessment", "Test assessment output")
        response = clotho.get_response("assessment")

        assert response == "Test assessment output"

    def test_mock_agent_default_response(self) -> None:
        """Verify mock agents have default responses."""
        clotho, _, _ = create_mock_three_fates()

        response = clotho.get_response("unknown_task")

        assert "[Clotho]" in response
        assert "unknown_task" in response


class TestDeliberationProtocol:
    """Tests for the deliberation protocol flow."""

    def test_mock_deliberation_produces_output(self) -> None:
        """Verify mock deliberation produces all phase outputs."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition content"

        result = execute_mock_deliberation(clotho, lachesis, atropos, petition)

        assert result.clotho_assessment != ""
        assert result.lachesis_evaluation != ""
        assert result.atropos_disposition != ""
        assert result.final_disposition in [
            Disposition.ACKNOWLEDGE,
            Disposition.REFER,
            Disposition.ESCALATE,
        ]

    def test_mock_deliberation_timing(self) -> None:
        """Verify mock deliberation records execution time."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition content"

        result = execute_mock_deliberation(clotho, lachesis, atropos, petition)

        assert result.execution_time_ms >= 0
        assert result.execution_time_ms < 1000  # Mock should be fast

    def test_mock_deliberation_agent_names_in_output(self) -> None:
        """Verify each Fate's name appears in their output."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition"

        result = execute_mock_deliberation(clotho, lachesis, atropos, petition)

        assert "Clotho" in result.clotho_assessment
        assert "Lachesis" in result.lachesis_evaluation
        assert "Atropos" in result.atropos_disposition


class TestDispositionExtraction:
    """Tests for disposition extraction from output."""

    def test_extract_acknowledge(self) -> None:
        """Verify ACKNOWLEDGE extraction."""
        output = "DISPOSITION: ACKNOWLEDGE\nRATIONALE: Petition reviewed."
        assert extract_disposition(output) == Disposition.ACKNOWLEDGE

    def test_extract_refer(self) -> None:
        """Verify REFER extraction."""
        output = "DISPOSITION: REFER\nRATIONALE: Needs expert review."
        assert extract_disposition(output) == Disposition.REFER

    def test_extract_escalate(self) -> None:
        """Verify ESCALATE extraction."""
        output = "DISPOSITION: ESCALATE\nRATIONALE: Constitutional issue."
        assert extract_disposition(output) == Disposition.ESCALATE

    def test_extract_from_mixed_case(self) -> None:
        """Verify case-insensitive extraction."""
        output = "disposition: Acknowledge\nrationale: Done."
        assert extract_disposition(output) == Disposition.ACKNOWLEDGE

    def test_extract_from_prose(self) -> None:
        """Verify extraction from unstructured output."""
        output = "After careful review, I recommend we ESCALATE this matter."
        assert extract_disposition(output) == Disposition.ESCALATE

    def test_extract_unknown_for_missing(self) -> None:
        """Verify UNKNOWN returned for invalid output."""
        output = "This output has no valid disposition."
        assert extract_disposition(output) == "UNKNOWN"


class TestDispositionTypes:
    """Tests for disposition type definitions."""

    def test_disposition_values(self) -> None:
        """Verify disposition values are correct strings."""
        assert Disposition.ACKNOWLEDGE == "ACKNOWLEDGE"
        assert Disposition.REFER == "REFER"
        assert Disposition.ESCALATE == "ESCALATE"

    def test_disposition_uniqueness(self) -> None:
        """Verify all dispositions are unique."""
        dispositions = [
            Disposition.ACKNOWLEDGE,
            Disposition.REFER,
            Disposition.ESCALATE,
        ]
        assert len(set(dispositions)) == 3


class TestDeliberationDeterminism:
    """Tests for deliberation determinism."""

    def test_mock_deliberation_deterministic(self) -> None:
        """Verify mock deliberation produces consistent results."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition for determinism"

        results = []
        for _ in range(3):
            result = execute_mock_deliberation(clotho, lachesis, atropos, petition)
            results.append(result.final_disposition)

        # All results should be the same
        assert len(set(results)) == 1, f"Non-deterministic: {results}"

    def test_mock_deliberation_reproducible_assessment(self) -> None:
        """Verify mock assessment is reproducible."""
        clotho, lachesis, atropos = create_mock_three_fates()
        petition = "Test petition"

        result1 = execute_mock_deliberation(clotho, lachesis, atropos, petition)
        result2 = execute_mock_deliberation(clotho, lachesis, atropos, petition)

        # Assessment structure should be consistent
        assert "Core Issue" in result1.clotho_assessment
        assert "Core Issue" in result2.clotho_assessment
