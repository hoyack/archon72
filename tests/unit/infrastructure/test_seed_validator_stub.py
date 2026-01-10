"""Unit tests for SeedValidatorStub (Story 6.9, FR124).

Tests the in-memory implementation of seed validation.

Constitutional Constraints:
- FR124: Seed source independence verification
- CT-12: Witnessing creates accountability
"""

from datetime import datetime, timezone

import pytest

from src.application.ports.seed_validator import (
    PredictabilityCheck,
    SeedSourceValidation,
    SeedUsageRecord,
    SeedValidatorProtocol,
)
from src.domain.events.seed_validation import SeedValidationResult
from src.infrastructure.stubs.seed_validator_stub import SeedValidatorStub


class TestSeedValidatorStubImplementsProtocol:
    """Test stub implements protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test stub inherits from protocol."""
        stub = SeedValidatorStub()
        assert isinstance(stub, SeedValidatorProtocol)


class TestValidateSeedSource:
    """Tests for validate_seed_source method."""

    @pytest.mark.asyncio
    async def test_returns_validation_result(self) -> None:
        """Test returns SeedSourceValidation."""
        stub = SeedValidatorStub()
        result = await stub.validate_seed_source("source-123", "witness_selection")

        assert isinstance(result, SeedSourceValidation)
        assert result.source_id == "source-123"

    @pytest.mark.asyncio
    async def test_default_returns_independent(self) -> None:
        """Test default sources are independent."""
        stub = SeedValidatorStub()
        result = await stub.validate_seed_source("any-source", "any-purpose")

        assert result.is_independent is True

    @pytest.mark.asyncio
    async def test_configured_validation_returned(self) -> None:
        """Test configured validation is returned."""
        stub = SeedValidatorStub()
        stub.set_source_independent("source-1", False, "test reason")

        result = await stub.validate_seed_source("source-1", "purpose")

        assert result.is_independent is False
        assert result.validation_reason == "test reason"

    @pytest.mark.asyncio
    async def test_set_source_validation_direct(self) -> None:
        """Test setting validation directly."""
        stub = SeedValidatorStub()
        validation = SeedSourceValidation(
            source_id="source-1",
            is_independent=True,
            validation_reason="custom reason",
            last_verified_at=datetime.now(timezone.utc),
        )
        stub.set_source_validation("source-1", validation)

        result = await stub.validate_seed_source("source-1", "purpose")
        assert result.validation_reason == "custom reason"


class TestCheckPredictability:
    """Tests for check_predictability method."""

    @pytest.mark.asyncio
    async def test_returns_predictability_check(self) -> None:
        """Test returns PredictabilityCheck."""
        stub = SeedValidatorStub()
        result = await stub.check_predictability(b"random_seed", "witness_selection")

        assert isinstance(result, PredictabilityCheck)

    @pytest.mark.asyncio
    async def test_default_not_predictable(self) -> None:
        """Test default seeds are not predictable."""
        stub = SeedValidatorStub()
        result = await stub.check_predictability(b"any_seed", "any_context")

        assert result.is_predictable is False
        assert len(result.predictability_indicators) == 0

    @pytest.mark.asyncio
    async def test_configured_predictability_returned(self) -> None:
        """Test configured predictability is returned."""
        stub = SeedValidatorStub()
        seed = b"predictable_seed"
        stub.set_predictability(
            seed,
            "witness_selection",
            is_predictable=True,
            indicators=("time_correlation", "pattern_match"),
            recommendation="Use external entropy",
        )

        result = await stub.check_predictability(seed, "witness_selection")

        assert result.is_predictable is True
        assert "time_correlation" in result.predictability_indicators
        assert result.recommendation == "Use external entropy"


class TestRecordSeedUsage:
    """Tests for record_seed_usage method."""

    @pytest.mark.asyncio
    async def test_records_usage(self) -> None:
        """Test seed usage is recorded."""
        stub = SeedValidatorStub()
        await stub.record_seed_usage(
            seed_hash="abc123hash",
            purpose="witness_selection",
            source_id="entropy-source-1",
        )

        records = stub.get_usage_records()
        assert len(records) == 1
        assert records[0].seed_hash == "abc123hash"
        assert records[0].purpose == "witness_selection"
        assert records[0].source_id == "entropy-source-1"
        assert records[0].validation_result == SeedValidationResult.VALID

    @pytest.mark.asyncio
    async def test_multiple_usages_recorded(self) -> None:
        """Test multiple usages are recorded."""
        stub = SeedValidatorStub()
        await stub.record_seed_usage("hash1", "purpose1", "source1")
        await stub.record_seed_usage("hash2", "purpose2", "source2")

        records = stub.get_usage_records()
        assert len(records) == 2


class TestGetSeedAuditTrail:
    """Tests for get_seed_audit_trail method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_records(self) -> None:
        """Test returns empty list when no records."""
        stub = SeedValidatorStub()
        records = await stub.get_seed_audit_trail("")
        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_returns_all_records_when_no_filter(self) -> None:
        """Test returns all records without filter."""
        stub = SeedValidatorStub()
        await stub.record_seed_usage("hash1", "purpose1", "source1")
        await stub.record_seed_usage("hash2", "purpose2", "source2")

        records = await stub.get_seed_audit_trail("")
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_filters_by_purpose(self) -> None:
        """Test filters by purpose."""
        stub = SeedValidatorStub()
        await stub.record_seed_usage("hash1", "witness_selection", "source1")
        await stub.record_seed_usage("hash2", "key_generation", "source2")

        records = await stub.get_seed_audit_trail("witness_selection")
        assert len(records) == 1
        assert records[0].purpose == "witness_selection"

    @pytest.mark.asyncio
    async def test_respects_limit(self) -> None:
        """Test respects limit parameter."""
        stub = SeedValidatorStub()
        for i in range(10):
            await stub.record_seed_usage(f"hash{i}", "purpose", "source")

        records = await stub.get_seed_audit_trail("", limit=5)
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_returns_most_recent_first(self) -> None:
        """Test returns most recent records first."""
        stub = SeedValidatorStub()
        # Add records directly with timestamps to control order
        from datetime import timedelta
        now = datetime.now(timezone.utc)

        stub.add_usage_record(SeedUsageRecord(
            seed_hash="hash1",
            purpose="purpose",
            source_id="source",
            used_at=now - timedelta(hours=2),
            validation_result=SeedValidationResult.VALID,
        ))
        stub.add_usage_record(SeedUsageRecord(
            seed_hash="hash2",
            purpose="purpose",
            source_id="source",
            used_at=now,
            validation_result=SeedValidationResult.VALID,
        ))

        records = await stub.get_seed_audit_trail("")
        assert records[0].seed_hash == "hash2"  # Most recent first


class TestTestHelpers:
    """Tests for test helper methods."""

    def test_set_default_independence(self) -> None:
        """Test set_default_independence affects new sources."""
        stub = SeedValidatorStub()
        stub.set_default_independence(False)

        # This is synchronous access, need to use asyncio
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            stub.validate_seed_source("new-source", "purpose")
        )
        assert result.is_independent is False

    def test_clear_removes_all_data(self) -> None:
        """Test clear removes all stored data."""
        stub = SeedValidatorStub()
        stub.set_source_independent("source-1", True)
        stub.set_default_independence(False)
        stub._usage_records.append(SeedUsageRecord(
            seed_hash="hash",
            purpose="purpose",
            source_id="source",
            used_at=datetime.now(timezone.utc),
            validation_result=SeedValidationResult.VALID,
        ))

        stub.clear()

        assert len(stub._source_validations) == 0
        assert len(stub._usage_records) == 0
        assert len(stub._predictability_results) == 0
        assert stub._default_is_independent is True
