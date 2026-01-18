"""Finding record domain model for immutable finding preservation.

Story: consent-gov-6-5: Panel Finding Preservation

Defines the FindingRecord value object that wraps a PanelFinding with
ledger metadata for immutable preservation per FR40 and NFR-CONST-06.

Why a Separate Record?
---------------------
PanelFinding is the judicial determination.
FindingRecord is the immutable ledger entry.

The separation ensures:
- Finding data remains pure domain logic
- Ledger metadata (position, hash) is tracked separately
- Immutability is enforced at the record level
- Historical queries work on ledger positions

References:
    - FR40: System can record all panel findings in append-only ledger
    - NFR-CONST-06: Panel findings cannot be deleted or modified
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.panel.determination import Determination
from src.domain.governance.panel.panel_finding import PanelFinding


@dataclass(frozen=True, eq=True)
class FindingRecord:
    """Immutable record of a panel finding in the ledger.

    Once created, a FindingRecord cannot be modified or deleted.
    This enforces NFR-CONST-06 at the domain level.

    Attributes:
        record_id: Unique identifier for this record
        finding: The PanelFinding being preserved
        recorded_at: When the finding was recorded to the ledger
        ledger_position: Position in the append-only ledger
        integrity_hash: SHA-256 hash for integrity verification

    Example:
        >>> record = FindingRecord(
        ...     record_id=uuid4(),
        ...     finding=panel_finding,
        ...     recorded_at=datetime.now(timezone.utc),
        ...     ledger_position=5678,
        ...     integrity_hash="abc123...",
        ... )
    """

    record_id: UUID
    """Unique identifier for this record."""

    finding: PanelFinding
    """The PanelFinding being preserved."""

    recorded_at: datetime
    """When the finding was recorded to the ledger."""

    ledger_position: int
    """Position in the append-only ledger.

    Provides ordering and enables range queries.
    """

    integrity_hash: str
    """SHA-256 hash of the finding for integrity verification.

    Computed from the canonical JSON representation of the finding.
    """

    def __post_init__(self) -> None:
        """Validate record fields."""
        if self.ledger_position <= 0:
            raise ValueError(
                f"Ledger position must be positive, got {self.ledger_position}"
            )
        if not self.integrity_hash:
            raise ValueError("Integrity hash is required")

    def __hash__(self) -> int:
        """Hash based on record_id (unique identifier)."""
        return hash(self.record_id)

    # Convenience accessors for common queries
    @property
    def finding_id(self) -> UUID:
        """UUID of the finding."""
        return self.finding.finding_id

    @property
    def panel_id(self) -> UUID:
        """UUID of the panel that issued this finding."""
        return self.finding.panel_id

    @property
    def statement_id(self) -> UUID:
        """UUID of the witness statement reviewed."""
        return self.finding.statement_id

    @property
    def determination(self) -> Determination:
        """Panel's determination."""
        return self.finding.determination

    @property
    def has_dissent(self) -> bool:
        """Whether the finding includes dissent."""
        return self.finding.dissent is not None

    @property
    def issued_at(self) -> datetime:
        """When the finding was issued."""
        return self.finding.issued_at
