"""Unit tests for complexity budget domain models (Story 8.6, SC-3, RT-6).

Tests for ComplexityDimension, ComplexityBudgetStatus, ComplexityBudget,
and ComplexitySnapshot domain models.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.models.complexity_budget import (
    ADR_LIMIT,
    CEREMONY_TYPE_LIMIT,
    CROSS_COMPONENT_DEP_LIMIT,
    WARNING_THRESHOLD_PERCENT,
    ComplexityBudget,
    ComplexityBudgetStatus,
    ComplexityDimension,
    ComplexitySnapshot,
)


class TestComplexityDimension:
    """Tests for ComplexityDimension enum."""

    def test_has_adr_count_dimension(self) -> None:
        """Test ADR_COUNT dimension exists."""
        assert ComplexityDimension.ADR_COUNT.value == "adr_count"

    def test_has_ceremony_types_dimension(self) -> None:
        """Test CEREMONY_TYPES dimension exists."""
        assert ComplexityDimension.CEREMONY_TYPES.value == "ceremony_types"

    def test_has_cross_component_deps_dimension(self) -> None:
        """Test CROSS_COMPONENT_DEPS dimension exists."""
        assert ComplexityDimension.CROSS_COMPONENT_DEPS.value == "cross_component_deps"

    def test_all_dimensions_defined(self) -> None:
        """Test all three dimensions are defined."""
        assert len(ComplexityDimension) == 3


class TestComplexityBudgetStatus:
    """Tests for ComplexityBudgetStatus enum."""

    def test_has_within_budget_status(self) -> None:
        """Test WITHIN_BUDGET status exists."""
        assert ComplexityBudgetStatus.WITHIN_BUDGET.value == "within_budget"

    def test_has_warning_status(self) -> None:
        """Test WARNING status exists."""
        assert ComplexityBudgetStatus.WARNING.value == "warning"

    def test_has_breached_status(self) -> None:
        """Test BREACHED status exists."""
        assert ComplexityBudgetStatus.BREACHED.value == "breached"


class TestComplexityBudgetConstants:
    """Tests for complexity budget constants."""

    def test_adr_limit_is_15(self) -> None:
        """Test ADR limit is 15 per CT-14."""
        assert ADR_LIMIT == 15

    def test_ceremony_type_limit_is_10(self) -> None:
        """Test ceremony type limit is 10 per CT-14."""
        assert CEREMONY_TYPE_LIMIT == 10

    def test_cross_component_dep_limit_is_20(self) -> None:
        """Test cross-component dependency limit is 20 per CT-14."""
        assert CROSS_COMPONENT_DEP_LIMIT == 20

    def test_warning_threshold_is_80_percent(self) -> None:
        """Test warning threshold is 80%."""
        assert WARNING_THRESHOLD_PERCENT == 80.0


class TestComplexityBudget:
    """Tests for ComplexityBudget dataclass."""

    def test_create_budget(self) -> None:
        """Test creating a complexity budget."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=10,
        )
        assert budget.dimension == ComplexityDimension.ADR_COUNT
        assert budget.limit == 15
        assert budget.current_value == 10

    def test_status_within_budget_at_zero(self) -> None:
        """Test status is WITHIN_BUDGET at 0%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=0,
        )
        assert budget.status == ComplexityBudgetStatus.WITHIN_BUDGET

    def test_status_within_budget_below_80_percent(self) -> None:
        """Test status is WITHIN_BUDGET below 80%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=100,
            current_value=79,
        )
        assert budget.status == ComplexityBudgetStatus.WITHIN_BUDGET

    def test_status_warning_at_80_percent(self) -> None:
        """Test status is WARNING at exactly 80%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=100,
            current_value=80,
        )
        assert budget.status == ComplexityBudgetStatus.WARNING

    def test_status_warning_at_99_percent(self) -> None:
        """Test status is WARNING at 99%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=100,
            current_value=99,
        )
        assert budget.status == ComplexityBudgetStatus.WARNING

    def test_status_breached_at_100_percent(self) -> None:
        """Test status is BREACHED at exactly 100%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=15,
        )
        assert budget.status == ComplexityBudgetStatus.BREACHED

    def test_status_breached_over_100_percent(self) -> None:
        """Test status is BREACHED over 100%."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=20,
        )
        assert budget.status == ComplexityBudgetStatus.BREACHED

    def test_utilization_percent(self) -> None:
        """Test utilization percentage calculation."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=20,
            current_value=15,
        )
        assert budget.utilization_percent == 75.0

    def test_remaining_capacity(self) -> None:
        """Test remaining capacity calculation."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=10,
        )
        assert budget.remaining == 5

    def test_remaining_negative_when_breached(self) -> None:
        """Test remaining is negative when breached."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=18,
        )
        assert budget.remaining == -3

    def test_is_breached_true(self) -> None:
        """Test is_breached property when breached."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=15,
        )
        assert budget.is_breached is True

    def test_is_breached_false(self) -> None:
        """Test is_breached property when not breached."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=14,
        )
        assert budget.is_breached is False

    def test_is_warning_true(self) -> None:
        """Test is_warning property when at warning level."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=100,
            current_value=85,
        )
        assert budget.is_warning is True

    def test_is_warning_false_when_breached(self) -> None:
        """Test is_warning is False when breached."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=15,
        )
        assert budget.is_warning is False

    def test_to_summary(self) -> None:
        """Test to_summary generates readable output."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=12,
        )
        summary = budget.to_summary()
        assert "adr_count" in summary
        assert "12/15" in summary
        assert "80.0%" in summary

    def test_budget_is_frozen(self) -> None:
        """Test that ComplexityBudget is immutable."""
        budget = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=10,
        )
        with pytest.raises(AttributeError):
            budget.current_value = 20  # type: ignore[misc]

    def test_negative_limit_raises_error(self) -> None:
        """Test that negative limit raises ValueError."""
        with pytest.raises(ValueError, match="limit must be positive"):
            ComplexityBudget(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=-1,
                current_value=0,
            )

    def test_zero_limit_raises_error(self) -> None:
        """Test that zero limit raises ValueError."""
        with pytest.raises(ValueError, match="limit must be positive"):
            ComplexityBudget(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=0,
                current_value=0,
            )

    def test_negative_current_value_raises_error(self) -> None:
        """Test that negative current_value raises ValueError."""
        with pytest.raises(ValueError, match="current_value cannot be negative"):
            ComplexityBudget(
                dimension=ComplexityDimension.ADR_COUNT,
                limit=15,
                current_value=-1,
            )

    def test_optional_breach_id(self) -> None:
        """Test that breach_id is optional."""
        budget_without = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=10,
        )
        assert budget_without.breach_id is None

        breach_id = uuid4()
        budget_with = ComplexityBudget(
            dimension=ComplexityDimension.ADR_COUNT,
            limit=15,
            current_value=20,
            breach_id=breach_id,
        )
        assert budget_with.breach_id == breach_id


class TestComplexitySnapshot:
    """Tests for ComplexitySnapshot dataclass."""

    def test_create_snapshot(self) -> None:
        """Test creating a complexity snapshot."""
        snapshot_id = uuid4()
        timestamp = datetime.now(timezone.utc)
        snapshot = ComplexitySnapshot(
            snapshot_id=snapshot_id,
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=12,
            timestamp=timestamp,
        )
        assert snapshot.snapshot_id == snapshot_id
        assert snapshot.adr_count == 10
        assert snapshot.ceremony_types == 5
        assert snapshot.cross_component_deps == 12
        assert snapshot.timestamp == timestamp

    def test_create_factory_method(self) -> None:
        """Test create factory method generates ID and timestamp."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=12,
        )
        assert snapshot.snapshot_id is not None
        assert snapshot.timestamp is not None
        assert snapshot.adr_count == 10

    def test_create_with_triggered_by(self) -> None:
        """Test create factory with triggered_by."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=12,
            triggered_by="scheduled check",
        )
        assert snapshot.triggered_by == "scheduled check"

    def test_get_budget_for_adr_count(self) -> None:
        """Test get_budget for ADR_COUNT dimension."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,
            ceremony_types=5,
            cross_component_deps=15,
        )
        budget = snapshot.get_budget(ComplexityDimension.ADR_COUNT)
        assert budget.dimension == ComplexityDimension.ADR_COUNT
        assert budget.current_value == 12
        assert budget.limit == ADR_LIMIT

    def test_get_budget_for_ceremony_types(self) -> None:
        """Test get_budget for CEREMONY_TYPES dimension."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,
            ceremony_types=8,
            cross_component_deps=15,
        )
        budget = snapshot.get_budget(ComplexityDimension.CEREMONY_TYPES)
        assert budget.dimension == ComplexityDimension.CEREMONY_TYPES
        assert budget.current_value == 8
        assert budget.limit == CEREMONY_TYPE_LIMIT

    def test_get_budget_for_cross_component_deps(self) -> None:
        """Test get_budget for CROSS_COMPONENT_DEPS dimension."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,
            ceremony_types=5,
            cross_component_deps=18,
        )
        budget = snapshot.get_budget(ComplexityDimension.CROSS_COMPONENT_DEPS)
        assert budget.dimension == ComplexityDimension.CROSS_COMPONENT_DEPS
        assert budget.current_value == 18
        assert budget.limit == CROSS_COMPONENT_DEP_LIMIT

    def test_get_all_budgets(self) -> None:
        """Test get_all_budgets returns all dimensions."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=15,
        )
        budgets = snapshot.get_all_budgets()
        assert len(budgets) == 3
        dimensions = [b.dimension for b in budgets]
        assert ComplexityDimension.ADR_COUNT in dimensions
        assert ComplexityDimension.CEREMONY_TYPES in dimensions
        assert ComplexityDimension.CROSS_COMPONENT_DEPS in dimensions

    def test_overall_status_within_budget(self) -> None:
        """Test overall_status is WITHIN_BUDGET when all under 80%."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,  # 66% of 15
            ceremony_types=5,  # 50% of 10
            cross_component_deps=10,  # 50% of 20
        )
        assert snapshot.overall_status == ComplexityBudgetStatus.WITHIN_BUDGET

    def test_overall_status_warning(self) -> None:
        """Test overall_status is WARNING when any at 80%+."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,  # 80% of 15
            ceremony_types=5,  # 50% of 10
            cross_component_deps=10,  # 50% of 20
        )
        assert snapshot.overall_status == ComplexityBudgetStatus.WARNING

    def test_overall_status_breached(self) -> None:
        """Test overall_status is BREACHED when any at 100%+."""
        snapshot = ComplexitySnapshot.create(
            adr_count=15,  # 100% of 15
            ceremony_types=5,  # 50% of 10
            cross_component_deps=10,  # 50% of 20
        )
        assert snapshot.overall_status == ComplexityBudgetStatus.BREACHED

    def test_overall_status_breached_takes_precedence(self) -> None:
        """Test BREACHED takes precedence over WARNING."""
        snapshot = ComplexitySnapshot.create(
            adr_count=15,  # 100% - BREACHED
            ceremony_types=9,  # 90% - WARNING
            cross_component_deps=10,  # 50% - WITHIN_BUDGET
        )
        assert snapshot.overall_status == ComplexityBudgetStatus.BREACHED

    def test_breached_dimensions(self) -> None:
        """Test breached_dimensions returns only breached dimensions."""
        snapshot = ComplexitySnapshot.create(
            adr_count=16,  # BREACHED
            ceremony_types=5,  # OK
            cross_component_deps=21,  # BREACHED
        )
        breached = snapshot.breached_dimensions
        assert len(breached) == 2
        assert ComplexityDimension.ADR_COUNT in breached
        assert ComplexityDimension.CROSS_COMPONENT_DEPS in breached

    def test_warning_dimensions(self) -> None:
        """Test warning_dimensions returns only warning dimensions."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,  # 80% - WARNING
            ceremony_types=9,  # 90% - WARNING
            cross_component_deps=10,  # 50% - OK
        )
        warning = snapshot.warning_dimensions
        assert len(warning) == 2
        assert ComplexityDimension.ADR_COUNT in warning
        assert ComplexityDimension.CEREMONY_TYPES in warning

    def test_has_breaches_true(self) -> None:
        """Test has_breaches is True when any dimension breached."""
        snapshot = ComplexitySnapshot.create(
            adr_count=16,
            ceremony_types=5,
            cross_component_deps=10,
        )
        assert snapshot.has_breaches is True

    def test_has_breaches_false(self) -> None:
        """Test has_breaches is False when no breaches."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=10,
        )
        assert snapshot.has_breaches is False

    def test_to_summary(self) -> None:
        """Test to_summary generates readable output."""
        snapshot = ComplexitySnapshot.create(
            adr_count=12,
            ceremony_types=5,
            cross_component_deps=18,
            triggered_by="manual check",
        )
        summary = snapshot.to_summary()
        assert "Complexity Snapshot" in summary
        assert "adr_count" in summary
        assert "ceremony_types" in summary
        assert "cross_component_deps" in summary
        assert "manual check" in summary

    def test_snapshot_is_frozen(self) -> None:
        """Test that ComplexitySnapshot is immutable."""
        snapshot = ComplexitySnapshot.create(
            adr_count=10,
            ceremony_types=5,
            cross_component_deps=10,
        )
        with pytest.raises(AttributeError):
            snapshot.adr_count = 20  # type: ignore[misc]

    def test_negative_adr_count_raises_error(self) -> None:
        """Test negative adr_count raises ValueError."""
        with pytest.raises(ValueError, match="adr_count cannot be negative"):
            ComplexitySnapshot(
                snapshot_id=uuid4(),
                adr_count=-1,
                ceremony_types=5,
                cross_component_deps=10,
                timestamp=datetime.now(timezone.utc),
            )

    def test_negative_ceremony_types_raises_error(self) -> None:
        """Test negative ceremony_types raises ValueError."""
        with pytest.raises(ValueError, match="ceremony_types cannot be negative"):
            ComplexitySnapshot(
                snapshot_id=uuid4(),
                adr_count=10,
                ceremony_types=-1,
                cross_component_deps=10,
                timestamp=datetime.now(timezone.utc),
            )

    def test_negative_cross_component_deps_raises_error(self) -> None:
        """Test negative cross_component_deps raises ValueError."""
        with pytest.raises(ValueError, match="cross_component_deps cannot be negative"):
            ComplexitySnapshot(
                snapshot_id=uuid4(),
                adr_count=10,
                ceremony_types=5,
                cross_component_deps=-1,
                timestamp=datetime.now(timezone.utc),
            )
