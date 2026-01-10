"""Unit tests for seed validation domain events (Story 6.9, FR124).

Tests for SeedValidationEventPayload and SeedRejectedEventPayload.

Constitutional Constraints:
- FR124: Seed independence verification for randomness gaming defense
- CT-12: Witnessing creates accountability -> signable_content()
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.seed_validation import (
    SEED_REJECTED_EVENT_TYPE,
    SEED_VALIDATION_EVENT_TYPE,
    SeedRejectedEventPayload,
    SeedValidationEventPayload,
    SeedValidationResult,
)


class TestSeedValidationResult:
    """Tests for SeedValidationResult enum."""

    def test_enum_values_exist(self) -> None:
        """Test that all expected enum values are present."""
        assert SeedValidationResult.VALID.value == "valid"
        assert SeedValidationResult.PREDICTABLE_REJECTED.value == "predictable_rejected"
        assert SeedValidationResult.SOURCE_DEPENDENT.value == "source_dependent"
        assert SeedValidationResult.ENTROPY_UNAVAILABLE.value == "entropy_unavailable"

    def test_enum_is_string_based(self) -> None:
        """Test enum values are strings for JSON serialization."""
        for result in SeedValidationResult:
            assert isinstance(result.value, str)


class TestSeedValidationEventPayload:
    """Tests for SeedValidationEventPayload."""

    def test_creation_with_valid_data(self) -> None:
        """Test payload creation with all required fields."""
        now = datetime.now(timezone.utc)
        payload = SeedValidationEventPayload(
            validation_id="val-123",
            seed_purpose="witness_selection",
            entropy_source_id="drand.cloudflare.com",
            independence_verified=True,
            validation_result=SeedValidationResult.VALID,
            validated_at=now,
        )

        assert payload.validation_id == "val-123"
        assert payload.seed_purpose == "witness_selection"
        assert payload.entropy_source_id == "drand.cloudflare.com"
        assert payload.independence_verified is True
        assert payload.validation_result == SeedValidationResult.VALID
        assert payload.validated_at == now

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert SEED_VALIDATION_EVENT_TYPE == "seed.validation"

    def test_frozen_dataclass_immutable(self) -> None:
        """Test payload is immutable (frozen dataclass)."""
        now = datetime.now(timezone.utc)
        payload = SeedValidationEventPayload(
            validation_id="val-123",
            seed_purpose="test",
            entropy_source_id="test-source",
            independence_verified=True,
            validation_result=SeedValidationResult.VALID,
            validated_at=now,
        )

        with pytest.raises(AttributeError):
            payload.validation_id = "new-id"  # type: ignore[misc]

    def test_to_dict_returns_serializable_structure(self) -> None:
        """Test to_dict returns JSON-serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = SeedValidationEventPayload(
            validation_id="val-456",
            seed_purpose="deliberation_random",
            entropy_source_id="random.org",
            independence_verified=False,
            validation_result=SeedValidationResult.SOURCE_DEPENDENT,
            validated_at=now,
        )

        result = payload.to_dict()

        assert result["validation_id"] == "val-456"
        assert result["seed_purpose"] == "deliberation_random"
        assert result["entropy_source_id"] == "random.org"
        assert result["independence_verified"] is False
        assert result["validation_result"] == "source_dependent"
        assert result["validated_at"] == now.isoformat()

    def test_signable_content_deterministic_ct12(self) -> None:
        """Test signable_content is deterministic for witnessing (CT-12)."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = SeedValidationEventPayload(
            validation_id="val-789",
            seed_purpose="test_purpose",
            entropy_source_id="test_source",
            independence_verified=True,
            validation_result=SeedValidationResult.VALID,
            validated_at=now,
        )

        content1 = payload.signable_content()
        content2 = payload.signable_content()

        # Same payload produces identical signable content
        assert content1 == content2
        assert isinstance(content1, bytes)

    def test_validation_rejects_empty_validation_id(self) -> None:
        """Test validation rejects empty validation_id."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="validation_id must be non-empty"):
            SeedValidationEventPayload(
                validation_id="",
                seed_purpose="test",
                entropy_source_id="test",
                independence_verified=True,
                validation_result=SeedValidationResult.VALID,
                validated_at=now,
            )

    def test_validation_rejects_empty_seed_purpose(self) -> None:
        """Test validation rejects empty seed_purpose."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="seed_purpose must be non-empty"):
            SeedValidationEventPayload(
                validation_id="val-123",
                seed_purpose="",
                entropy_source_id="test",
                independence_verified=True,
                validation_result=SeedValidationResult.VALID,
                validated_at=now,
            )


class TestSeedRejectedEventPayload:
    """Tests for SeedRejectedEventPayload."""

    def test_creation_with_valid_data(self) -> None:
        """Test payload creation with all required fields."""
        now = datetime.now(timezone.utc)
        payload = SeedRejectedEventPayload(
            rejection_id="rej-123",
            seed_purpose="witness_selection",
            rejection_reason="Predictable pattern detected in seed bytes",
            attempted_source="dev-stub",
            rejected_at=now,
        )

        assert payload.rejection_id == "rej-123"
        assert payload.seed_purpose == "witness_selection"
        assert payload.rejection_reason == "Predictable pattern detected in seed bytes"
        assert payload.attempted_source == "dev-stub"
        assert payload.rejected_at == now

    def test_event_type_constant(self) -> None:
        """Test event type constant is defined."""
        assert SEED_REJECTED_EVENT_TYPE == "seed.rejected"

    def test_to_dict_returns_serializable_structure(self) -> None:
        """Test to_dict returns JSON-serializable dictionary."""
        now = datetime.now(timezone.utc)
        payload = SeedRejectedEventPayload(
            rejection_id="rej-456",
            seed_purpose="lottery",
            rejection_reason="Source not independent",
            attempted_source="internal-prng",
            rejected_at=now,
        )

        result = payload.to_dict()

        assert result["rejection_id"] == "rej-456"
        assert result["seed_purpose"] == "lottery"
        assert result["rejection_reason"] == "Source not independent"
        assert result["attempted_source"] == "internal-prng"
        assert result["rejected_at"] == now.isoformat()

    def test_signable_content_deterministic(self) -> None:
        """Test signable_content is deterministic."""
        now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        payload = SeedRejectedEventPayload(
            rejection_id="rej-789",
            seed_purpose="test",
            rejection_reason="test reason",
            attempted_source="test_source",
            rejected_at=now,
        )

        assert payload.signable_content() == payload.signable_content()

    def test_validation_rejects_empty_rejection_id(self) -> None:
        """Test validation rejects empty rejection_id."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="rejection_id must be non-empty"):
            SeedRejectedEventPayload(
                rejection_id="",
                seed_purpose="test",
                rejection_reason="test",
                attempted_source="test",
                rejected_at=now,
            )

    def test_fr124_message_in_validation(self) -> None:
        """Test FR124 referenced in validation context."""
        now = datetime.now(timezone.utc)
        # Valid payload should mention FR124 in docstring context
        payload = SeedRejectedEventPayload(
            rejection_id="rej-test",
            seed_purpose="witness_selection",
            rejection_reason="FR124 violation - predictable seed",
            attempted_source="bad-source",
            rejected_at=now,
        )
        # Rejection reason should be able to reference FR124
        assert "FR124" in payload.rejection_reason
