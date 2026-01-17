"""Schema version constants and validation for governance events.

Schema versioning enables deterministic replay and external verification
by ensuring events can be parsed according to their recorded schema.

Per governance-architecture.md:
- Schema version format: semver (major.minor.patch)
- All events MUST have a schema_version field
- Schema changes require version bumps
"""

import re

from src.domain.errors.constitutional import ConstitutionalViolationError

# Current schema version for new events
CURRENT_SCHEMA_VERSION: str = "1.0.0"

# Semver validation pattern
_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def validate_schema_version(version: str) -> None:
    """Validate schema version is valid semver format.

    Args:
        version: Schema version string to validate.

    Raises:
        ConstitutionalViolationError: If version is not valid semver.
    """
    if not isinstance(version, str):
        raise ConstitutionalViolationError(
            f"AD-17: Schema version must be string, got {type(version).__name__}"
        )

    if not _SEMVER_PATTERN.match(version):
        raise ConstitutionalViolationError(
            f"AD-17: Schema version must be semver format (X.Y.Z), got '{version}'"
        )
