"""Unit tests for canonical_json module.

Story: consent-gov-1.3: Hash Chain Implementation

Tests canonical JSON serialization for deterministic hashing per AC6.
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.governance.events.canonical_json import (
    canonical_json,
    canonical_json_bytes,
)


class TestCanonicalJsonDeterminism:
    """Tests for canonical JSON determinism (AC6)."""

    def test_same_dict_same_output(self) -> None:
        """Same dictionary produces identical JSON."""
        data = {"a": 1, "b": 2}
        result1 = canonical_json(data)
        result2 = canonical_json(data)
        assert result1 == result2

    def test_key_order_independent(self) -> None:
        """Different key insertion order produces same JSON."""
        d1 = {"b": 1, "a": 2}
        d2 = {"a": 2, "b": 1}
        assert canonical_json(d1) == canonical_json(d2)

    def test_keys_sorted_alphabetically(self) -> None:
        """Keys are sorted alphabetically in output."""
        data = {"z": 1, "m": 2, "a": 3}
        result = canonical_json(data)
        assert result == '{"a":3,"m":2,"z":1}'

    def test_nested_dicts_sorted(self) -> None:
        """Nested dictionary keys are also sorted."""
        data = {"outer": {"z": 1, "a": 2}}
        result = canonical_json(data)
        assert result == '{"outer":{"a":2,"z":1}}'

    def test_no_whitespace(self) -> None:
        """Output has no extra whitespace."""
        data = {"key": "value", "number": 42}
        result = canonical_json(data)
        assert " " not in result
        assert "\n" not in result
        assert "\t" not in result


class TestCanonicalJsonTypeHandling:
    """Tests for type conversion in canonical JSON."""

    def test_datetime_to_isoformat(self) -> None:
        """Datetime is converted to ISO-8601 string."""
        dt = datetime(2026, 1, 16, 12, 30, 45, tzinfo=timezone.utc)
        data = {"timestamp": dt}
        result = canonical_json(data)
        assert "2026-01-16T12:30:45" in result

    def test_uuid_to_string(self) -> None:
        """UUID is converted to lowercase string."""
        uuid = UUID("12345678-1234-1234-1234-123456789abc")
        data = {"id": uuid}
        result = canonical_json(data)
        assert "12345678-1234-1234-1234-123456789abc" in result

    def test_bytes_to_hex(self) -> None:
        """Bytes are converted to hex string."""
        data = {"data": b"\x00\xff"}
        result = canonical_json(data)
        assert "00ff" in result

    def test_integer_preserved(self) -> None:
        """Integers are preserved as-is."""
        data = {"count": 42}
        result = canonical_json(data)
        assert '"count":42' in result

    def test_float_preserved(self) -> None:
        """Floats are preserved as-is."""
        data = {"value": 3.14}
        result = canonical_json(data)
        assert "3.14" in result

    def test_boolean_preserved(self) -> None:
        """Booleans are preserved as JSON true/false."""
        data = {"flag": True, "disabled": False}
        result = canonical_json(data)
        assert "true" in result
        assert "false" in result

    def test_null_preserved(self) -> None:
        """None is preserved as JSON null."""
        data = {"value": None}
        result = canonical_json(data)
        assert "null" in result

    def test_list_preserved(self) -> None:
        """Lists are preserved with order."""
        data = {"items": [3, 1, 2]}
        result = canonical_json(data)
        assert "[3,1,2]" in result


class TestCanonicalJsonUnicodeNormalization:
    """Tests for Unicode normalization in canonical JSON."""

    def test_unicode_normalized_nfkc(self) -> None:
        """Unicode strings are NFKC normalized."""
        # é as separate characters (e + combining acute)
        decomposed = "cafe\u0301"
        # é as single character
        composed = "café"

        data1 = {"text": decomposed}
        data2 = {"text": composed}

        # Both should produce the same output after NFKC normalization
        assert canonical_json(data1) == canonical_json(data2)

    def test_unicode_not_escaped(self) -> None:
        """Non-ASCII Unicode is not escaped."""
        data = {"text": "日本語"}
        result = canonical_json(data)
        assert "日本語" in result
        assert "\\u" not in result


class TestCanonicalJsonFloatValidation:
    """Tests for float validation in canonical JSON."""

    def test_nan_rejected(self) -> None:
        """NaN float values raise ConstitutionalViolationError."""
        data = {"value": float("nan")}
        with pytest.raises(ConstitutionalViolationError, match="non-finite float"):
            canonical_json(data)

    def test_infinity_rejected(self) -> None:
        """Infinity float values raise ConstitutionalViolationError."""
        data = {"value": float("inf")}
        with pytest.raises(ConstitutionalViolationError, match="non-finite float"):
            canonical_json(data)

    def test_negative_infinity_rejected(self) -> None:
        """-Infinity float values raise ConstitutionalViolationError."""
        data = {"value": float("-inf")}
        with pytest.raises(ConstitutionalViolationError, match="non-finite float"):
            canonical_json(data)

    def test_nested_nan_rejected(self) -> None:
        """NaN in nested structure raises ConstitutionalViolationError."""
        data = {"nested": {"value": float("nan")}}
        with pytest.raises(ConstitutionalViolationError, match="non-finite float"):
            canonical_json(data)

    def test_nan_in_list_rejected(self) -> None:
        """NaN in list raises ConstitutionalViolationError."""
        data = {"items": [1, float("nan"), 3]}
        with pytest.raises(ConstitutionalViolationError, match="non-finite float"):
            canonical_json(data)


class TestCanonicalJsonBytes:
    """Tests for canonical_json_bytes function."""

    def test_returns_bytes(self) -> None:
        """canonical_json_bytes returns bytes."""
        data = {"key": "value"}
        result = canonical_json_bytes(data)
        assert isinstance(result, bytes)

    def test_utf8_encoding(self) -> None:
        """canonical_json_bytes uses UTF-8 encoding."""
        data = {"text": "日本語"}
        result = canonical_json_bytes(data)
        assert result == canonical_json(data).encode("utf-8")

    def test_same_as_manual_encode(self) -> None:
        """canonical_json_bytes matches manual encoding."""
        data = {"a": 1, "b": 2}
        assert canonical_json_bytes(data) == canonical_json(data).encode("utf-8")


class TestCanonicalJsonComplexStructures:
    """Tests for complex nested structures."""

    def test_deeply_nested_structure(self) -> None:
        """Deeply nested structures are handled correctly."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": 42
                    }
                }
            }
        }
        result = canonical_json(data)
        assert result == '{"level1":{"level2":{"level3":{"value":42}}}}'

    def test_mixed_types_in_list(self) -> None:
        """Lists with mixed types are serialized correctly."""
        data = {"mixed": [1, "string", True, None, {"nested": "dict"}]}
        result = canonical_json(data)
        assert '"mixed":[1,"string",true,null,{"nested":"dict"}]' in result

    def test_empty_dict(self) -> None:
        """Empty dict serializes to {}."""
        data: dict[str, object] = {}
        result = canonical_json(data)
        assert result == "{}"

    def test_empty_list_in_dict(self) -> None:
        """Empty list in dict serializes correctly."""
        data = {"items": []}
        result = canonical_json(data)
        assert result == '{"items":[]}'
