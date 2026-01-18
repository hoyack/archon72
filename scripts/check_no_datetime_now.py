#!/usr/bin/env python3
"""Pre-commit hook to prevent direct datetime.now() calls in production code.

HARDENING-1: TimeAuthorityService Mandatory Injection
Source: Gov Epic 8 Retrospective Action Item #1 (2026-01-15)

Team Agreement:
> No `datetime.now()` calls in production code - always inject time authority

This script scans src/ for direct datetime.now() or datetime.utcnow() calls
and fails if any are found (excluding the TimeAuthorityService itself).

Usage:
    python scripts/check_no_datetime_now.py

Exit codes:
    0: No violations found
    1: Violations found - datetime.now() detected in production code
"""

import re
import sys
from pathlib import Path

# Patterns to detect direct datetime calls
# Matches: datetime.now(), datetime.utcnow()
# Also catches: from datetime import datetime; ... datetime.now()
DATETIME_NOW_PATTERN = re.compile(r"datetime\s*\.\s*(now|utcnow)\s*\(", re.MULTILINE)

# Files that are ALLOWED to use datetime.now() directly
# These are the only exceptions to the rule
ALLOWED_FILES = {
    # TimeAuthorityService is THE source of truth for time
    "src/application/services/time_authority_service.py",
}

# Test files are allowed to use datetime.now() for test setup
# (though FakeTimeAuthority is preferred)
TEST_PREFIXES = ("tests/", "test_")


def check_file(file_path: Path) -> list[tuple[int, str]]:
    """Check a single file for datetime.now() violations.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        List of (line_number, line_content) tuples for violations.
    """
    violations: list[tuple[int, str]] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        # Check for violations
        if DATETIME_NOW_PATTERN.search(line):
            violations.append((line_num, line.strip()))

    return violations


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        Exit code: 0 for success, 1 for violations found.
    """
    src_path = Path("src")

    if not src_path.exists():
        print("Warning: src/ directory not found, skipping check")
        return 0

    all_violations: dict[str, list[tuple[int, str]]] = {}

    # Scan all Python files in src/
    for py_file in src_path.rglob("*.py"):
        relative_path = str(py_file)

        # Skip allowed files
        if relative_path in ALLOWED_FILES:
            continue

        # Skip test files (but warn)
        if any(relative_path.startswith(prefix) for prefix in TEST_PREFIXES):
            continue

        violations = check_file(py_file)
        if violations:
            all_violations[relative_path] = violations

    if not all_violations:
        print("✅ No datetime.now() violations found in src/")
        return 0

    # Report violations
    print("❌ HARDENING-1 VIOLATION: Direct datetime.now() calls detected!")
    print()
    print("Team Agreement (Gov Epic 8 Retrospective):")
    print(
        "  > No datetime.now() calls in production code - always inject time authority"
    )
    print()
    print("Violations found:")
    print()

    for file_path, violations in sorted(all_violations.items()):
        print(f"  {file_path}:")
        for line_num, line_content in violations:
            print(f"    Line {line_num}: {line_content}")
        print()

    print("How to fix:")
    print("  1. Inject TimeAuthorityProtocol in your service constructor")
    print("  2. Use self._time.now() instead of datetime.now()")
    print()
    print("Example:")
    print("  from src.application.ports.time_authority import TimeAuthorityProtocol")
    print()
    print("  class MyService:")
    print("      def __init__(self, time_authority: TimeAuthorityProtocol) -> None:")
    print("          self._time = time_authority")
    print()
    print("      def process(self) -> None:")
    print("          now = self._time.now()  # NOT datetime.now()")
    print()

    return 1


if __name__ == "__main__":
    sys.exit(main())
