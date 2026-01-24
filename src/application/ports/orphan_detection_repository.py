"""Port for orphan detection persistence (Story 8.3, FR-8.5)."""

from __future__ import annotations

from typing import Protocol

from src.domain.models.orphan_petition_detection import OrphanPetitionDetectionResult


class OrphanDetectionRepositoryProtocol(Protocol):
    """Protocol for persisting orphan detection results."""

    def save_detection_result(
        self, detection_result: OrphanPetitionDetectionResult
    ) -> None:
        """Persist a detection result."""
        ...
