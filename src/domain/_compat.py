"""Compatibility shims for Python enum features across supported versions."""

from enum import Enum

try:  # Python 3.11+
    from enum import StrEnum  # type: ignore
except ImportError:  # Python 3.10 fallback

    class StrEnum(str, Enum):
        """Backport of enum.StrEnum for Python 3.10."""

        def __str__(self) -> str:  # pragma: no cover - mirrors stdlib behavior
            return str(self.value)


__all__ = ["StrEnum"]
