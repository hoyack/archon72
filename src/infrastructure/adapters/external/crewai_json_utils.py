"""Shared JSON parsing utilities for CrewAI adapters."""

from __future__ import annotations

import ast
import json
import re


def strip_markdown_fence(text: str) -> str:
    """Remove markdown code fences from text if present."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1])
        else:
            cleaned = "\n".join(lines[1:])
    return cleaned


def remove_trailing_commas(text: str) -> str:
    """Remove trailing commas before closing braces/brackets."""
    return re.sub(r",\s*([\]}])", r"\1", text)


def extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from a string."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def extract_json_payload(text: str) -> str:
    """Extract the outermost JSON object or array from a string."""
    obj_start = text.find("{")
    arr_start = text.find("[")
    if obj_start == -1 and arr_start == -1:
        return text
    if obj_start == -1 or (0 <= arr_start < obj_start):
        end = text.rfind("]") + 1
        if arr_start >= 0 and end > arr_start:
            return text[arr_start:end]
        return text
    return extract_json_object(text)


def sanitize_json_string(text: str) -> str:
    """Escape control characters inside JSON string values."""
    result = []
    in_string = False
    escape_next = False
    i = 0

    while i < len(text):
        char = text[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\" and in_string:
            escape_next = True
            result.append(char)
            i += 1
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string and ord(char) < 32:
            if char == "\n":
                result.append("\\n")
            elif char == "\r":
                result.append("\\r")
            elif char == "\t":
                result.append("\\t")
            else:
                result.append(f"\\u{ord(char):04x}")
        else:
            result.append(char)

        i += 1

    return "".join(result)


def aggressive_clean(text: str) -> str:
    """Aggressively clean JSON when standard parsing fails."""
    cleaned = strip_markdown_fence(text)

    def replace_control(match: re.Match[str]) -> str:
        char = match.group(0)
        if char == "\n":
            return "\\n"
        if char == "\r":
            return "\\r"
        if char == "\t":
            return "\\t"
        return f"\\u{ord(char):04x}"

    cleaned = re.sub(r"[\x00-\x1f]", replace_control, cleaned)
    cleaned = remove_trailing_commas(cleaned)
    cleaned = re.sub(r"{\s*(\w+):", r'{"\1":', cleaned)
    cleaned = re.sub(r",\s*(\w+):", r',"\1":', cleaned)
    cleaned = extract_json_payload(cleaned)
    return cleaned


def _literal_eval_json(candidate: str) -> dict | None:
    """Attempt to parse a Python literal payload into a dict."""
    try:
        parsed = ast.literal_eval(candidate)
    except Exception:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def parse_json_response(text: str, *, aggressive: bool = False) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    cleaned = strip_markdown_fence(text)
    cleaned = remove_trailing_commas(cleaned)
    cleaned = extract_json_payload(cleaned)
    cleaned = sanitize_json_string(cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        if not aggressive:
            raise
        cleaned = aggressive_clean(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            fallback = _literal_eval_json(cleaned)
            if fallback is not None:
                return fallback
            fallback = _literal_eval_json(strip_markdown_fence(text))
            if fallback is not None:
                return fallback
            fallback = _literal_eval_json(extract_json_payload(text))
            if fallback is not None:
                return fallback
            raise
