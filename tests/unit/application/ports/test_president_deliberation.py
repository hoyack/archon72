"""Tests for President deliberation port interface."""

import pytest

from src.application.ports.president_deliberation import (
    DeliberationContext,
    DeliberationResult,
)


def test_deliberation_context_creation():
    """Verify DeliberationContext can be created with required fields."""
    context = DeliberationContext(
        cycle_id="exec_test123",
        motion_id="motion_abc",
        motion_title="Test Motion",
        motion_text="This is a test motion text.",
        constraints=["security", "transparency"],
        affected_portfolios=["portfolio_a", "portfolio_b"],
        plan_owner_portfolio_id="portfolio_a",
        response_deadline="2026-01-28T16:00:00Z",
    )

    assert context.cycle_id == "exec_test123"
    assert context.motion_id == "motion_abc"
    assert len(context.constraints) == 2
    assert len(context.affected_portfolios) == 2


def test_deliberation_result_with_contribution():
    """Verify DeliberationResult can represent a contribution."""
    result = DeliberationResult(
        portfolio_id="portfolio_tech",
        president_name="Marbas",
        contributed=True,
        contribution=None,  # Would be PortfolioContribution in real use
        deliberation_notes="Contributing cryptographic verification tasks",
        duration_ms=1500,
    )

    assert result.contributed is True
    assert result.portfolio_id == "portfolio_tech"
    assert result.president_name == "Marbas"
    assert result.attestation is None


def test_deliberation_result_with_attestation():
    """Verify DeliberationResult can represent a no-action attestation."""
    result = DeliberationResult(
        portfolio_id="portfolio_resource",
        president_name="Valac",
        contributed=False,
        attestation=None,  # Would be NoActionAttestation in real use
        deliberation_notes="Motion does not require resource discovery",
        duration_ms=800,
    )

    assert result.contributed is False
    assert result.contribution is None
    assert result.duration_ms == 800


def test_deliberation_context_with_empty_constraints():
    """Verify DeliberationContext works with empty constraints list."""
    context = DeliberationContext(
        cycle_id="exec_empty",
        motion_id="motion_xyz",
        motion_title="Simple Motion",
        motion_text="A motion with no constraints.",
        constraints=[],
        affected_portfolios=["portfolio_a"],
        plan_owner_portfolio_id="portfolio_a",
        response_deadline="2026-01-28T16:00:00Z",
    )

    assert context.constraints == []
    assert len(context.affected_portfolios) == 1
