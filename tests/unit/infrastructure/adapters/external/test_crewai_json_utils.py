"""Unit tests for shared CrewAI JSON parsing utilities."""

from __future__ import annotations

from src.infrastructure.adapters.external.crewai_json_utils import (
    aggressive_clean,
    parse_json_response,
    sanitize_json_string,
)


def test_parse_json_response_strips_markdown_and_trailing_commas() -> None:
    """Parse JSON wrapped in markdown with trailing commas."""
    raw = """```json
{
  "status": "ok",
  "items": [1, 2, 3,],
}
```"""

    parsed = parse_json_response(raw)
    assert parsed["status"] == "ok"
    assert parsed["items"] == [1, 2, 3]


def test_sanitize_json_string_escapes_control_chars() -> None:
    """Escape raw control characters inside JSON strings."""
    raw = '{"text": "line1\nline2\tend"}'
    cleaned = sanitize_json_string(raw)
    assert "\\n" in cleaned
    assert "\\t" in cleaned


def test_parse_json_response_aggressive_fallback() -> None:
    """Aggressive cleaning should salvage malformed JSON."""
    raw = """```json
{status: "ok", "value": 3,}
```"""

    parsed = parse_json_response(raw, aggressive=True)
    assert parsed["status"] == "ok"
    assert parsed["value"] == 3


def test_aggressive_clean_removes_trailing_commas() -> None:
    """Aggressive clean should normalize trailing commas."""
    raw = '{"items": [1, 2, 3,],}'
    cleaned = aggressive_clean(raw)
    assert ",]" not in cleaned
