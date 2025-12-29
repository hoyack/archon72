#!/usr/bin/env python3
"""
Constitutional Lint - Archon 72

Scans codebase for forbidden language patterns that violate
the post-collapse constitution established in Language Surgery.

Usage:
    python scripts/constitutional_lint.py [--fix-suggestions]

Exit codes:
    0 - No violations found
    1 - Violations found (CI should fail)
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Violation:
    file: Path
    line_number: int
    line_content: str
    pattern: str
    suggestion: str


# Forbidden patterns with their replacements
# These are derived from Language Surgery (2025-12-28)
FORBIDDEN_PATTERNS = [
    # Enforcement language
    (r'\benforce\b', 'verify'),
    (r'\benforcement\b', 'verification'),
    (r'\benforces\b', 'verifies'),
    (r'\benforcing\b', 'verifying'),

    # Safety theater
    (r'\bensure\s+safety\b', 'enable visibility'),
    (r'\bensures\s+safety\b', 'enables visibility'),
    (r'\bsafeguard\b', 'expose'),
    (r'\bsafeguards\b', 'exposes'),

    # Authority claims
    (r'\bauthority\b', 'scope'),
    (r'\bauthoritative\b', 'scoped'),
    (r'\bauthorities\b', 'scopes'),

    # Binding as power (careful: "binding" in UI context is OK)
    (r'\bbinding\s+force\b', 'recorded consequence'),
    (r'\bbinding\s+decision\b', 'recorded decision'),
    (r'\blegally\s+binding\b', 'recorded with consequence'),

    # Automatic decisions (automation without witness)
    (r'\bautomatic\s+decision\b', 'witnessed decision'),
    (r'\bautomatically\s+decide\b', 'explicitly decide'),
    (r'\bauto-approve\b', 'explicitly approve'),

    # Prevention claims
    (r'\bprevent\s+harm\b', 'detect harm'),
    (r'\bprevents\s+harm\b', 'detects harm'),
    (r'\bpreventing\s+harm\b', 'detecting harm'),

    # Guarantee claims
    (r'\bguarantee\b', 'verify'),
    (r'\bguarantees\b', 'verifies'),
    (r'\bguaranteed\b', 'verified'),
]

# Directories to scan
SCAN_DIRS = ['src', 'docs', 'migrations', 'input_boundary']

# File extensions to check
SCAN_EXTENSIONS = {'.py', '.md', '.sql', '.yaml', '.yml', '.json'}

# Files/patterns to exclude
EXCLUDE_PATTERNS = [
    r'constitutional_lint\.py$',  # This file
    r'constitutional-implementation-rules\.md$',  # The rules doc (contains examples)
    r'language-surgery',  # Language surgery analysis docs
    r'/bs/',  # Brainstorming files (meta-discussion)
    r'brainstorming',  # Brainstorming directories
    r'__pycache__',
    r'\.git',
    r'node_modules',
    r'\.venv',
]


def should_exclude(path: Path) -> bool:
    """Check if a path should be excluded from scanning."""
    path_str = str(path)
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, path_str):
            return True
    return False


def scan_file(file_path: Path) -> list[Violation]:
    """Scan a single file for constitutional violations."""
    violations = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return violations

    lines = content.split('\n')

    for line_num, line in enumerate(lines, start=1):
        # Skip comments that are explaining the rules (detection context)
        if 'WRONG' in line or 'forbidden' in line.lower() or 'never' in line.lower():
            continue

        for pattern, suggestion in FORBIDDEN_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append(Violation(
                    file=file_path,
                    line_number=line_num,
                    line_content=line.strip(),
                    pattern=pattern,
                    suggestion=suggestion,
                ))

    return violations


def scan_directory(root: Path) -> list[Violation]:
    """Scan a directory recursively for violations."""
    violations = []

    for scan_dir in SCAN_DIRS:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob('*'):
            if not file_path.is_file():
                continue
            if file_path.suffix not in SCAN_EXTENSIONS:
                continue
            if should_exclude(file_path):
                continue

            violations.extend(scan_file(file_path))

    return violations


def format_violation(v: Violation) -> str:
    """Format a violation for output."""
    return (
        f"\n  {v.file}:{v.line_number}\n"
        f"    Pattern: {v.pattern}\n"
        f"    Line: {v.line_content[:80]}{'...' if len(v.line_content) > 80 else ''}\n"
        f"    Suggestion: Use '{v.suggestion}' instead"
    )


def main() -> int:
    """Run constitutional lint and return exit code."""
    print("Constitutional Lint - Archon 72")
    print("=" * 40)

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    print(f"Scanning: {project_root}")
    print(f"Directories: {', '.join(SCAN_DIRS)}")
    print()

    violations = scan_directory(project_root)

    if not violations:
        print("No constitutional violations found.")
        return 0

    print(f"CONSTITUTIONAL VIOLATIONS FOUND: {len(violations)}")
    print("-" * 40)

    # Group by file
    by_file: dict[Path, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)

    for file_path, file_violations in sorted(by_file.items()):
        print(f"\n{file_path} ({len(file_violations)} violations)")
        for v in file_violations:
            print(format_violation(v))

    print()
    print("-" * 40)
    print(f"Total: {len(violations)} violations in {len(by_file)} files")
    print()
    print("These patterns violate the post-collapse constitution.")
    print("See: docs/constitutional-implementation-rules.md")

    return 1


if __name__ == '__main__':
    sys.exit(main())
