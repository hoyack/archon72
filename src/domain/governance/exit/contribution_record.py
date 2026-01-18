"""Contribution record domain model for consent-based governance.

Story: consent-gov-7.3: Contribution Preservation

Defines the ContributionRecord frozen dataclass for tracking
Cluster contributions. Attribution is PII-free (UUIDs only).

Constitutional Truths Honored:
- FR45: Contribution history preserved on exit
- NFR-INT-02: Public data only, no PII
- Ledger immutability: No deletion or modification

Key Design Principles:
1. Immutable value object (frozen dataclass)
2. Attribution uses UUIDs only, no personal information
3. Cannot be deleted or modified (append-only ledger)
4. Hash-verified for integrity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.governance.exit.contribution_type import ContributionType


@dataclass(frozen=True)
class ContributionRecord:
    """Record of a Cluster contribution.

    Per FR45: System can preserve Cluster's contribution history on exit.
    Per NFR-INT-02: Public data only, no PII.

    This is an immutable record capturing:
    - Who contributed (cluster_id - UUID only)
    - What task (task_id - UUID only)
    - What type of contribution
    - When it happened
    - When it was preserved (on exit)
    - Result hash for verification

    STRUCTURAL ABSENCE (PII protection):
        The following fields DO NOT EXIST and CANNOT be added:
        - cluster_name: str  # No personal names
        - cluster_email: str  # No email addresses
        - cluster_phone: str  # No phone numbers
        - cluster_contact: str  # No contact info

        These fields are intentionally absent. Adding them would
        violate NFR-INT-02 (public data only, no PII).

    Attributes:
        record_id: Unique identifier for this contribution record.
        cluster_id: ID of the Cluster who contributed (UUID - pseudonymous).
        task_id: ID of the task this contribution relates to.
        contribution_type: Type of contribution made.
        contributed_at: When the contribution was made.
        preserved_at: When the contribution was preserved (set on exit, None otherwise).
        result_hash: Hash of the contribution result for verification.
    """

    record_id: UUID
    cluster_id: UUID  # Pseudonymous attribution - no PII
    task_id: UUID
    contribution_type: ContributionType
    contributed_at: datetime
    preserved_at: datetime | None  # Set on exit
    result_hash: str  # For verification

    # ========================================================================
    # STRUCTURAL ABSENCE - The following fields DO NOT EXIST
    # ========================================================================
    #
    # These fields are INTENTIONALLY absent (NFR-INT-02 enforcement):
    #
    # cluster_name: str
    #     Would store personal name - VIOLATES NFR-INT-02
    #
    # cluster_email: str
    #     Would store email address - VIOLATES NFR-INT-02
    #
    # cluster_phone: str
    #     Would store phone number - VIOLATES NFR-INT-02
    #
    # cluster_contact: str
    #     Would store contact info - VIOLATES NFR-INT-02
    #
    # If you see these fields being added in the future, this is a
    # CONSTITUTIONAL VIOLATION. Knight should observe and record.
    # ========================================================================

    def __post_init__(self) -> None:
        """Validate contribution record fields."""
        self._validate_record_id()
        self._validate_cluster_id()
        self._validate_task_id()
        self._validate_contribution_type()
        self._validate_contributed_at()
        self._validate_preserved_at()
        self._validate_result_hash()

    def _validate_record_id(self) -> None:
        """Validate record_id is UUID."""
        if not isinstance(self.record_id, UUID):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"record_id must be UUID, got {type(self.record_id).__name__}"
            )

    def _validate_cluster_id(self) -> None:
        """Validate cluster_id is UUID."""
        if not isinstance(self.cluster_id, UUID):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"cluster_id must be UUID, got {type(self.cluster_id).__name__}"
            )

    def _validate_task_id(self) -> None:
        """Validate task_id is UUID."""
        if not isinstance(self.task_id, UUID):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"task_id must be UUID, got {type(self.task_id).__name__}"
            )

    def _validate_contribution_type(self) -> None:
        """Validate contribution_type is ContributionType."""
        if not isinstance(self.contribution_type, ContributionType):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"contribution_type must be ContributionType, got {type(self.contribution_type).__name__}"
            )

    def _validate_contributed_at(self) -> None:
        """Validate contributed_at is datetime."""
        if not isinstance(self.contributed_at, datetime):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"contributed_at must be datetime, got {type(self.contributed_at).__name__}"
            )

    def _validate_preserved_at(self) -> None:
        """Validate preserved_at is datetime or None."""
        if self.preserved_at is not None and not isinstance(
            self.preserved_at, datetime
        ):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"preserved_at must be datetime or None, got {type(self.preserved_at).__name__}"
            )

    def _validate_result_hash(self) -> None:
        """Validate result_hash is non-empty string."""
        if not isinstance(self.result_hash, str):
            raise ValueError(
                f"ContributionRecord validation failed - "
                f"result_hash must be str, got {type(self.result_hash).__name__}"
            )
        if not self.result_hash.strip():
            raise ValueError(
                "ContributionRecord validation failed - "
                "result_hash must not be empty or whitespace"
            )

    @property
    def is_preserved(self) -> bool:
        """Check if contribution has been preserved (on exit)."""
        return self.preserved_at is not None
