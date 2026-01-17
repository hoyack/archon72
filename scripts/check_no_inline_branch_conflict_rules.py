#!/usr/bin/env python3
"""Pre-commit hook to prevent inline BranchConflictRule definitions.

HARDENING-2: Branch Conflict Rules YAML Consolidation
Source: Hardening Epic Story 2

Team Agreement:
> Branch conflict rules MUST be defined in config/permissions/rank-matrix.yaml
> No inline BranchConflictRule instantiations in Python code

This script scans src/ for inline BranchConflictRule definitions and fails
if any are found (excluding the loader itself and imports).

Usage:
    python scripts/check_no_inline_branch_conflict_rules.py

Exit codes:
    0: No violations found
    1: Violations found - inline BranchConflictRule detected in production code
"""

import re
import sys
from pathlib import Path

# Patterns to detect inline BranchConflictRule definitions
# Matches: BranchConflictRule( - instantiation of the dataclass
INLINE_RULE_PATTERN = re.compile(
    r'BranchConflictRule\s*\(',
    re.MULTILINE
)

# Pattern for constant list definitions (the old pattern we removed)
# Matches: BRANCH_CONFLICT_RULES = [
CONSTANT_LIST_PATTERN = re.compile(
    r'BRANCH_CONFLICT_RULES\s*[:\=]',
    re.MULTILINE
)

# Files that are ALLOWED to instantiate BranchConflictRule
# These are the only exceptions to the rule
ALLOWED_FILES = {
    # The loader creates BranchConflictRule instances from YAML
    'src/infrastructure/adapters/config/branch_conflict_rules_loader.py',
}

# Test files are allowed to instantiate for testing purposes
TEST_PREFIXES = ('tests/', 'test_')


def check_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Check a single file for inline BranchConflictRule violations.

    Args:
        file_path: Path to the Python file to check.

    Returns:
        List of (line_number, line_content, violation_type) tuples.
    """
    violations: list[tuple[int, str, str]] = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return violations

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue

        # Skip import statements
        if stripped.startswith('from ') or stripped.startswith('import '):
            continue

        # Check for inline instantiation
        if INLINE_RULE_PATTERN.search(line):
            violations.append((line_num, line.strip(), 'inline instantiation'))

        # Check for constant list definition
        if CONSTANT_LIST_PATTERN.search(line):
            violations.append((line_num, line.strip(), 'constant list definition'))

    return violations


def main() -> int:
    """Main entry point for the pre-commit hook.

    Returns:
        Exit code: 0 for success, 1 for violations found.
    """
    src_path = Path('src')

    if not src_path.exists():
        print("Warning: src/ directory not found, skipping check")
        return 0

    all_violations: dict[str, list[tuple[int, str, str]]] = {}

    # Scan all Python files in src/
    for py_file in src_path.rglob('*.py'):
        relative_path = str(py_file)

        # Skip allowed files
        if relative_path in ALLOWED_FILES:
            continue

        # Skip test files
        if any(relative_path.startswith(prefix) for prefix in TEST_PREFIXES):
            continue

        violations = check_file(py_file)
        if violations:
            all_violations[relative_path] = violations

    if not all_violations:
        print("No inline BranchConflictRule violations found in src/")
        return 0

    # Report violations
    print("HARDENING-2 VIOLATION: Inline BranchConflictRule definitions detected!")
    print()
    print("Team Agreement (Hardening Epic Story 2):")
    print("  > Branch conflict rules MUST be defined in config/permissions/rank-matrix.yaml")
    print("  > No inline BranchConflictRule instantiations in Python code")
    print()
    print("Violations found:")
    print()

    for file_path, violations in sorted(all_violations.items()):
        print(f"  {file_path}:")
        for line_num, line_content, violation_type in violations:
            print(f"    Line {line_num} ({violation_type}): {line_content}")
        print()

    print("How to fix:")
    print("  1. Define rules in config/permissions/rank-matrix.yaml")
    print("  2. Use BranchConflictRulesLoaderProtocol to load rules at runtime")
    print()
    print("Example YAML (config/permissions/rank-matrix.yaml):")
    print("  branch_conflicts:")
    print("    - id: 'legislative_executive'")
    print("      branches: ['legislative', 'executive']")
    print("      rule: 'Same Archon cannot define WHAT and HOW for same motion'")
    print("      severity: 'critical'")
    print("      prd_ref: 'PRD 2.1'")
    print()
    print("Example usage:")
    print("  from src.infrastructure.adapters.config.branch_conflict_rules_loader import (")
    print("      BranchConflictRulesLoaderProtocol,")
    print("      YamlBranchConflictRulesLoader,")
    print("  )")
    print()
    print("  class MyService:")
    print("      def __init__(self, rules_loader: BranchConflictRulesLoaderProtocol):")
    print("          self._rules = rules_loader.load_rules()")
    print()

    return 1


if __name__ == '__main__':
    sys.exit(main())
