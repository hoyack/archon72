#!/usr/bin/env python3
"""Check hexagonal architecture import boundaries.

This script enforces the hexagonal architecture layering rules:
- domain/: Pure business logic, NO imports from other src layers
- application/: Use cases, may import from domain/ only
- infrastructure/: Adapters, may import from domain/ and application/
- api/: External interface, may import from application/ (and transitively domain/)

Usage:
    python scripts/check_imports.py [src_directory]

Exit codes:
    0: No violations found
    1: Violations found
"""
import ast
import sys
from pathlib import Path

# Layer hierarchy: lower number = more inner layer (more protected)
# Inner layers cannot import from outer layers
LAYER_HIERARCHY: dict[str, int] = {
    "domain": 0,  # Core, innermost - imports NOTHING from src
    "application": 1,  # Use cases - imports from domain only
    "infrastructure": 2,  # Adapters - imports from domain, application
    "api": 3,  # External interface - imports from application
}

# Explicit import rules: what each layer CAN import from
# If a layer is not in this dict, it follows the hierarchy rule
ALLOWED_IMPORTS: dict[str, set[str]] = {
    "domain": set(),  # Domain imports NOTHING from src layers
    "application": {"domain"},  # Application can import domain
    "infrastructure": {"domain", "application"},  # Infrastructure can import both
    "api": {"application", "domain"},  # API imports via application (domain transitively)
}


def get_import_module(node: ast.Import | ast.ImportFrom) -> str | None:
    """Extract the module name from an import statement."""
    if isinstance(node, ast.ImportFrom):
        return node.module
    if isinstance(node, ast.Import) and node.names:
        # For 'import x.y.z', get the first name
        return node.names[0].name
    return None


def _get_file_layer(py_file: Path, src_dir: Path) -> str | None:
    """Determine the architectural layer of a file.

    Args:
        py_file: Path to the Python file
        src_dir: Path to the src directory

    Returns:
        The layer name (domain, application, infrastructure, api) or None
    """
    try:
        relative = py_file.relative_to(src_dir)
    except ValueError:
        return None

    parts = relative.parts
    if not parts:
        return None

    file_layer = parts[0]
    return file_layer if file_layer in LAYER_HIERARCHY else None


def _parse_file(py_file: Path) -> ast.Module | None:
    """Parse a Python file into an AST.

    Args:
        py_file: Path to the Python file

    Returns:
        The parsed AST module or None if parsing failed
    """
    try:
        source = py_file.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(py_file))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {py_file}: {e}", file=sys.stderr)
        return None


def _check_import_violation(
    module: str, file_layer: str, allowed_layers: set[str]
) -> str | None:
    """Check if an import violates layer boundaries.

    Args:
        module: The import module string (e.g., "src.domain.models")
        file_layer: The layer the importing file belongs to
        allowed_layers: Set of layers this file is allowed to import from

    Returns:
        Error message if violation detected, None otherwise
    """
    if not module.startswith("src."):
        return None

    module_parts = module.split(".")
    if len(module_parts) < 2:
        return None

    target_layer = module_parts[1]
    if target_layer not in LAYER_HIERARCHY:
        return None

    # Same-layer imports are always allowed
    if target_layer == file_layer:
        return None

    # Check if this cross-layer import is allowed
    if target_layer not in allowed_layers:
        return f"{file_layer} layer cannot import from {target_layer}"

    return None


def check_file_imports(
    py_file: Path, src_dir: Path
) -> list[tuple[str, int, str]]:
    """Check a single file for import boundary violations.

    Args:
        py_file: Path to the Python file to check
        src_dir: Path to the src directory

    Returns:
        List of (file_path, line_number, violation_message) tuples
    """
    file_layer = _get_file_layer(py_file, src_dir)
    if file_layer is None:
        return []

    tree = _parse_file(py_file)
    if tree is None:
        return []

    violations: list[tuple[str, int, str]] = []
    allowed_layers = ALLOWED_IMPORTS.get(file_layer, set())

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = get_import_module(node)
            if module:
                error_msg = _check_import_violation(module, file_layer, allowed_layers)
                if error_msg:
                    violations.append((str(py_file), node.lineno, error_msg))

    return violations


def check_import_boundaries(src_dir: Path) -> list[tuple[str, int, str]]:
    """Check all Python files in src directory for import boundary violations.

    Args:
        src_dir: Path to the src directory

    Returns:
        List of (file_path, line_number, violation_message) tuples
    """
    violations: list[tuple[str, int, str]] = []

    if not src_dir.exists():
        print(f"Error: Source directory '{src_dir}' does not exist", file=sys.stderr)
        return violations

    for py_file in src_dir.rglob("*.py"):
        file_violations = check_file_imports(py_file, src_dir)
        violations.extend(file_violations)

    return violations


def format_violations(violations: list[tuple[str, int, str]]) -> str:
    """Format violations for human-readable output."""
    if not violations:
        return ""

    lines = ["Import boundary violations found:", ""]
    for file_path, line_no, message in sorted(violations):
        lines.append(f"  {file_path}:{line_no}: {message}")
    lines.append("")
    lines.append(f"Total: {len(violations)} violation(s)")
    return "\n".join(lines)


def main() -> int:
    """Main entry point.

    Returns:
        0 if no violations, 1 if violations found
    """
    # Determine src directory
    if len(sys.argv) > 1:
        src_dir = Path(sys.argv[1])
    else:
        # Default to src/ relative to script location or current directory
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        src_dir = project_root / "src"

    violations = check_import_boundaries(src_dir)

    if violations:
        print(format_violations(violations))
        return 1
    else:
        print("No import boundary violations found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
