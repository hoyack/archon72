"""Independence attestation domain model for annual Keeper conflict declaration (FR98, FR133).

This module defines the IndependenceAttestation entity for tracking annual Keeper
independence attestations. Keepers must annually declare any conflicts of interest
and organizational affiliations to expose (not prevent) potential collusion.

Constitutional Constraints:
- FR98: Anomalous signature patterns SHALL be flagged for manual review
- FR133: Keepers SHALL annually attest independence from each other and system
         operators; attestation recorded (exposes, doesn't prevent)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> HALT OVER DEGRADE
- CT-12: Witnessing creates accountability -> Attestations are witnessed events

Note: DeletePreventionMixin ensures `.delete()` raises
ConstitutionalViolationError before any DB interaction (FR76).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.primitives import DeletePreventionMixin

if TYPE_CHECKING:
    pass

# Annual attestation requirement (FR133)
ATTESTATION_DEADLINE_DAYS: int = 365

# Grace period after anniversary before suspension (30 days)
DEADLINE_GRACE_PERIOD_DAYS: int = 30


class DeclarationType(Enum):
    """Types of conflict of interest declarations.

    Used to categorize declared conflicts for analysis and reporting.
    """

    FINANCIAL = "FINANCIAL"  # Financial interest (investments, ownership)
    ORGANIZATIONAL = "ORGANIZATIONAL"  # Board membership, employment
    PERSONAL = "PERSONAL"  # Family, close relationships
    NONE_DECLARED = "NONE_DECLARED"  # Explicitly declaring no conflicts


@dataclass(frozen=True, eq=True)
class ConflictDeclaration:
    """A single conflict of interest declaration.

    Keepers must declare all known conflicts. This creates exposure,
    not enforcement - the system records, it does not judge.

    Attributes:
        declaration_type: Category of the conflict
        description: Detailed description of the conflict
        related_party: The party the conflict relates to
        disclosed_at: When this conflict was first disclosed
    """

    declaration_type: DeclarationType
    description: str
    related_party: str
    disclosed_at: datetime


def get_current_attestation_year() -> int:
    """Return the current attestation year.

    Attestation year aligns with calendar year.

    Returns:
        Current year in UTC.
    """
    return datetime.now(timezone.utc).year


def calculate_deadline(
    first_attestation_date: datetime | None,
    current_year: int | None = None,
) -> datetime:
    """Calculate when next attestation is due.

    Due on anniversary of first attestation + grace period.
    If no previous attestation, due immediately.

    Args:
        first_attestation_date: When the Keeper first attested (or None if never).
        current_year: Override year for testing (defaults to current UTC year).

    Returns:
        Deadline datetime for next attestation.
    """
    if first_attestation_date is None:
        return datetime.now(timezone.utc)  # Due immediately

    if current_year is None:
        current_year = datetime.now(timezone.utc).year

    # Anniversary of first attestation in the target year
    anniversary = first_attestation_date.replace(
        year=current_year,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    # Add grace period
    deadline = anniversary + timedelta(days=DEADLINE_GRACE_PERIOD_DAYS)
    return deadline


@dataclass(frozen=True, eq=True)
class IndependenceAttestation(DeletePreventionMixin):
    """Keeper annual independence attestation - immutable, deletion prohibited.

    Each Keeper must submit an annual attestation declaring any conflicts of
    interest and organizational affiliations. This creates exposure for
    accountability, not enforcement.

    Constitutional Constraints:
    - FR76: Historical attestations must be preserved (no deletion)
    - FR133: Annual attestation requirement

    Attributes:
        id: Unique identifier for this attestation record (UUID)
        keeper_id: ID of Keeper making the attestation
            Format: "KEEPER:{name}" (e.g., "KEEPER:alice")
        attested_at: When this attestation was submitted
        attestation_year: The year this attestation covers
        conflict_declarations: List of declared conflicts of interest
        affiliated_organizations: Organizations the Keeper is affiliated with
        signature: Ed25519 signature over attestation content (64 bytes)
        created_at: Audit timestamp for when record was created

    Note:
        DeletePreventionMixin ensures `.delete()` raises
        ConstitutionalViolationError before any DB interaction.
    """

    # Primary identifier
    id: UUID

    # Keeper identifier (FR133)
    keeper_id: str

    # When attestation was submitted
    attested_at: datetime

    # Year this attestation covers
    attestation_year: int

    # Declared conflicts of interest
    conflict_declarations: list[ConflictDeclaration]

    # Affiliated organizations
    affiliated_organizations: list[str]

    # Ed25519 signature (64 bytes)
    signature: bytes

    # Audit timestamp
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate fields after initialization.

        Raises:
            ConstitutionalViolationError: If any field fails validation.
        """
        self._validate_id()
        self._validate_keeper_id()
        self._validate_signature()

    def _validate_id(self) -> None:
        """Validate id is UUID."""
        if not isinstance(self.id, UUID):
            raise ConstitutionalViolationError(
                f"FR133: IndependenceAttestation validation failed - id must be UUID, "
                f"got {type(self.id).__name__}"
            )

    def _validate_keeper_id(self) -> None:
        """Validate keeper_id is non-empty string."""
        if not isinstance(self.keeper_id, str) or not self.keeper_id.strip():
            raise ConstitutionalViolationError(
                "FR133: IndependenceAttestation validation failed - "
                "keeper_id must be non-empty string"
            )

    def _validate_signature(self) -> None:
        """Validate signature is Ed25519 signature (64 bytes)."""
        if not isinstance(self.signature, bytes):
            raise ConstitutionalViolationError(
                "FR133: IndependenceAttestation validation failed - "
                "signature must be bytes"
            )
        # Ed25519 signatures are exactly 64 bytes
        if len(self.signature) != 64:
            raise ConstitutionalViolationError(
                f"FR133: IndependenceAttestation validation failed - "
                f"signature must be 64 bytes (Ed25519), got {len(self.signature)}"
            )

    def __hash__(self) -> int:
        """Hash based on id (unique identifier).

        Note: Lists and signature are excluded from hash since they're mutable
        types. Hash is based on id alone for set membership.
        """
        return hash(self.id)

    def is_valid_for_year(self, year: int) -> bool:
        """Check if this attestation is valid for a specific year.

        An attestation is valid for a year if its attestation_year matches.

        Args:
            year: The year to check against.

        Returns:
            True if attestation covers the specified year, False otherwise.
        """
        return self.attestation_year == year
