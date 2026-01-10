"""Unit tests for prohibited language domain models (Story 9.1, FR55).

Tests:
- ProhibitedTermsList with default terms
- ProhibitedTermsList with custom terms
- NFKC normalization for Unicode evasion defense
- Case-insensitive matching
- ProhibitedLanguageBlockedEventPayload validation and serialization
"""

from datetime import datetime, timezone

import pytest

from src.domain.events.prohibited_language_blocked import (
    MAX_CONTENT_PREVIEW_LENGTH,
    PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
    PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID,
    ProhibitedLanguageBlockedEventPayload,
)
from src.domain.models.prohibited_language import (
    DEFAULT_PROHIBITED_TERMS,
    ProhibitedTermsList,
    normalize_for_scanning,
)


class TestNormalizeForScanning:
    """Tests for normalize_for_scanning function."""

    def test_lowercase_conversion(self) -> None:
        """Test that text is converted to lowercase."""
        assert normalize_for_scanning("EMERGENCE") == "emergence"
        assert normalize_for_scanning("EmErGeNcE") == "emergence"

    def test_nfkc_normalization(self) -> None:
        """Test NFKC normalization catches homoglyphs."""
        # Fullwidth characters -> regular
        assert normalize_for_scanning("ｅｍｅｒｇｅｎｃｅ") == "emergence"

    def test_empty_string(self) -> None:
        """Test empty string normalization."""
        assert normalize_for_scanning("") == ""

    def test_whitespace_preserved(self) -> None:
        """Test whitespace is preserved after normalization."""
        result = normalize_for_scanning("self aware")
        assert result == "self aware"


class TestProhibitedTermsList:
    """Tests for ProhibitedTermsList domain model."""

    def test_default_terms_include_emergence(self) -> None:
        """Test default terms include 'emergence' (FR55)."""
        terms_list = ProhibitedTermsList.default()
        assert "emergence" in terms_list.terms

    def test_default_terms_include_consciousness(self) -> None:
        """Test default terms include 'consciousness' (FR55)."""
        terms_list = ProhibitedTermsList.default()
        assert "consciousness" in terms_list.terms

    def test_default_terms_include_sentience(self) -> None:
        """Test default terms include 'sentience' (FR55)."""
        terms_list = ProhibitedTermsList.default()
        assert "sentience" in terms_list.terms

    def test_default_terms_include_self_awareness(self) -> None:
        """Test default terms include 'self-awareness' (FR55)."""
        terms_list = ProhibitedTermsList.default()
        assert "self-awareness" in terms_list.terms

    def test_default_terms_count(self) -> None:
        """Test default terms list has expected minimum count."""
        terms_list = ProhibitedTermsList.default()
        # Should have at least the core 4 terms plus variations
        assert len(terms_list) >= 4

    def test_from_custom_terms(self) -> None:
        """Test creating list from custom terms."""
        custom = ("custom1", "custom2")
        terms_list = ProhibitedTermsList.from_custom_terms(custom)
        assert terms_list.terms == custom

    def test_from_custom_terms_empty_raises(self) -> None:
        """Test empty custom terms raises ValueError."""
        with pytest.raises(ValueError, match="FR55"):
            ProhibitedTermsList.from_custom_terms(())

    def test_contains_prohibited_term_exact_match(self) -> None:
        """Test exact term matching."""
        terms_list = ProhibitedTermsList.default()
        has_violation, matched = terms_list.contains_prohibited_term(
            "The system has achieved emergence."
        )
        assert has_violation is True
        assert "emergence" in matched

    def test_contains_prohibited_term_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        terms_list = ProhibitedTermsList.default()
        has_violation, matched = terms_list.contains_prohibited_term(
            "EMERGENCE is happening"
        )
        assert has_violation is True
        assert "emergence" in matched

    def test_contains_prohibited_term_clean_content(self) -> None:
        """Test clean content returns no violations."""
        terms_list = ProhibitedTermsList.default()
        has_violation, matched = terms_list.contains_prohibited_term(
            "This is clean content without any issues."
        )
        assert has_violation is False
        assert len(matched) == 0

    def test_contains_prohibited_term_multiple_matches(self) -> None:
        """Test multiple terms matched."""
        terms_list = ProhibitedTermsList.default()
        has_violation, matched = terms_list.contains_prohibited_term(
            "Emergence and consciousness detected."
        )
        assert has_violation is True
        assert len(matched) >= 2
        assert "emergence" in matched
        assert "consciousness" in matched

    def test_normalized_terms_property(self) -> None:
        """Test normalized_terms are lowercase NFKC."""
        terms_list = ProhibitedTermsList.default()
        for term in terms_list.normalized_terms:
            assert term == term.lower()

    def test_len_returns_term_count(self) -> None:
        """Test __len__ returns correct count."""
        custom = ("a", "b", "c")
        terms_list = ProhibitedTermsList.from_custom_terms(custom)
        assert len(terms_list) == 3

    def test_iter_over_terms(self) -> None:
        """Test iteration over terms."""
        custom = ("term1", "term2")
        terms_list = ProhibitedTermsList.from_custom_terms(custom)
        terms = list(terms_list)
        assert terms == ["term1", "term2"]


class TestProhibitedLanguageBlockedEventPayload:
    """Tests for ProhibitedLanguageBlockedEventPayload."""

    @pytest.fixture
    def valid_payload(self) -> ProhibitedLanguageBlockedEventPayload:
        """Create a valid payload for testing."""
        return ProhibitedLanguageBlockedEventPayload(
            content_id="test-content-123",
            matched_terms=("emergence", "consciousness"),
            detection_method="nfkc_scan",
            blocked_at=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            content_preview="This content mentions emergence and consciousness.",
        )

    def test_event_type_constant(self) -> None:
        """Test event type constant value."""
        assert PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE == "prohibited.language.blocked"

    def test_system_agent_id_constant(self) -> None:
        """Test system agent ID constant value."""
        assert PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID == "system:prohibited_language_blocker"

    def test_payload_creation(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test payload can be created with valid data."""
        assert valid_payload.content_id == "test-content-123"
        assert valid_payload.matched_terms == ("emergence", "consciousness")

    def test_payload_empty_content_id_raises(self) -> None:
        """Test empty content_id raises ValueError."""
        with pytest.raises(ValueError, match="FR55: content_id is required"):
            ProhibitedLanguageBlockedEventPayload(
                content_id="",
                matched_terms=("emergence",),
                detection_method="nfkc_scan",
                blocked_at=datetime.now(timezone.utc),
                content_preview="content",
            )

    def test_payload_empty_matched_terms_raises(self) -> None:
        """Test empty matched_terms raises ValueError."""
        with pytest.raises(ValueError, match="FR55: At least one matched term required"):
            ProhibitedLanguageBlockedEventPayload(
                content_id="test-123",
                matched_terms=(),
                detection_method="nfkc_scan",
                blocked_at=datetime.now(timezone.utc),
                content_preview="content",
            )

    def test_payload_empty_detection_method_raises(self) -> None:
        """Test empty detection_method raises ValueError."""
        with pytest.raises(ValueError, match="FR55: detection_method is required"):
            ProhibitedLanguageBlockedEventPayload(
                content_id="test-123",
                matched_terms=("emergence",),
                detection_method="",
                blocked_at=datetime.now(timezone.utc),
                content_preview="content",
            )

    def test_payload_content_preview_truncated(self) -> None:
        """Test content_preview is truncated to max length."""
        long_content = "x" * 500
        payload = ProhibitedLanguageBlockedEventPayload(
            content_id="test-123",
            matched_terms=("emergence",),
            detection_method="nfkc_scan",
            blocked_at=datetime.now(timezone.utc),
            content_preview=long_content,
        )
        assert len(payload.content_preview) == MAX_CONTENT_PREVIEW_LENGTH

    def test_event_type_property(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test event_type property returns correct type."""
        assert valid_payload.event_type == PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE

    def test_terms_count_property(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test terms_count property returns correct count."""
        assert valid_payload.terms_count == 2

    def test_to_dict_serialization(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test to_dict() produces correct dictionary."""
        result = valid_payload.to_dict()

        assert result["content_id"] == "test-content-123"
        assert result["matched_terms"] == ["emergence", "consciousness"]
        assert result["detection_method"] == "nfkc_scan"
        assert result["blocked_at"] == "2026-01-08T12:00:00+00:00"
        assert "content_preview" in result
        assert result["terms_count"] == 2

    def test_signable_content_determinism(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test signable_content() is deterministic."""
        content1 = valid_payload.signable_content()
        content2 = valid_payload.signable_content()
        assert content1 == content2

    def test_signable_content_bytes(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test signable_content() returns bytes."""
        content = valid_payload.signable_content()
        assert isinstance(content, bytes)

    def test_content_hash_hex_string(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test content_hash() returns hex string."""
        hash_value = valid_payload.content_hash()
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64  # SHA-256 hex

    def test_content_hash_determinism(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test content_hash() is deterministic."""
        hash1 = valid_payload.content_hash()
        hash2 = valid_payload.content_hash()
        assert hash1 == hash2

    def test_payload_is_frozen(self, valid_payload: ProhibitedLanguageBlockedEventPayload) -> None:
        """Test payload is immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            valid_payload.content_id = "new-id"  # type: ignore[misc]


class TestDefaultProhibitedTerms:
    """Tests for DEFAULT_PROHIBITED_TERMS constant."""

    def test_is_tuple(self) -> None:
        """Test DEFAULT_PROHIBITED_TERMS is a tuple."""
        assert isinstance(DEFAULT_PROHIBITED_TERMS, tuple)

    def test_contains_core_terms(self) -> None:
        """Test contains the core FR55 prohibited terms."""
        core_terms = ["emergence", "consciousness", "sentience", "self-awareness"]
        for term in core_terms:
            assert term in DEFAULT_PROHIBITED_TERMS, f"Missing core term: {term}"

    def test_all_lowercase(self) -> None:
        """Test all terms are lowercase."""
        for term in DEFAULT_PROHIBITED_TERMS:
            assert term == term.lower(), f"Term not lowercase: {term}"
