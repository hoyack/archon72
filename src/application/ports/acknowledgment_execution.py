"""Acknowledgment execution protocol (Story 3.2, FR-3.1).

This module defines the protocol for executing petition acknowledgments.
Follows hexagonal architecture with port/adapter pattern.

Constitutional Constraints:
- FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
- CT-12: Every action that affects an Archon must be witnessed
- CT-14: Every claim terminates in visible, witnessed fate
- NFR-3.2: Fate assignment atomicity (100% single-fate)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from src.domain.models.acknowledgment import Acknowledgment
    from src.domain.models.acknowledgment_reason import AcknowledgmentReasonCode


class AcknowledgmentExecutionProtocol(Protocol):
    """Protocol for executing petition acknowledgments (FR-3.1).

    This protocol defines the contract for executing acknowledgments
    when deliberation reaches ACKNOWLEDGE consensus. Implementations
    must handle:

    1. Validation of petition state (must be DELIBERATING)
    2. Validation of reason code requirements (rationale, reference)
    3. Atomic state transition (DELIBERATING → ACKNOWLEDGED)
    4. Creation of Acknowledgment record
    5. Event emission and witnessing (CT-12)

    Constitutional Constraints:
    - FR-3.1: Marquis SHALL be able to ACKNOWLEDGE petition with reason code
    - FR-3.3: System SHALL require rationale for REFUSED/NO_ACTION_WARRANTED
    - FR-3.4: System SHALL require reference_petition_id for DUPLICATE
    - CT-12: Every action that affects an Archon must be witnessed
    - NFR-3.2: Fate assignment atomicity (100% single-fate)
    """

    @abstractmethod
    async def execute(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        acknowledging_archon_ids: Sequence[int],
        rationale: str | None = None,
        reference_petition_id: UUID | None = None,
    ) -> Acknowledgment:
        """Execute acknowledgment for a petition.

        This is the main entry point for acknowledging a petition.
        The method must be atomic - either the acknowledgment completes
        fully (state transition + record + event) or not at all.

        Args:
            petition_id: The petition to acknowledge
            reason_code: Reason for acknowledgment from AcknowledgmentReasonCode enum
            acknowledging_archon_ids: IDs of archons who voted ACKNOWLEDGE (min 2)
            rationale: Required for REFUSED/NO_ACTION_WARRANTED per FR-3.3
            reference_petition_id: Required for DUPLICATE per FR-3.4

        Returns:
            The created Acknowledgment record

        Raises:
            PetitionNotFoundError: Petition doesn't exist
            PetitionNotInDeliberatingStateError: Petition not in DELIBERATING state
            AcknowledgmentAlreadyExistsError: Petition already acknowledged
            InvalidArchonCountError: Less than 2 archons provided
            RationaleRequiredError: Rationale missing for REFUSED/NO_ACTION_WARRANTED
            ReferenceRequiredError: Reference missing for DUPLICATE
            InvalidReferencePetitionError: Reference petition doesn't exist
            WitnessHashGenerationError: Failed to generate witness hash
        """
        ...

    @abstractmethod
    async def execute_system_acknowledge(
        self,
        petition_id: UUID,
        reason_code: AcknowledgmentReasonCode,
        rationale: str,
    ) -> Acknowledgment:
        """Execute system-triggered acknowledgment (Story 4.6, FR-4.5).

        System-triggered acknowledgments bypass certain validations:
        - No archon count validation (no deliberating archons)
        - No dwell time enforcement (system action)
        - Accepts REFERRED state (referral workflow completion)

        Used for:
        - EXPIRED: Referral timeout auto-acknowledge (Story 4.6)
        - KNIGHT_REFERRAL: Knight recommendation routing (Story 4.4)

        Args:
            petition_id: The petition to acknowledge.
            reason_code: Must be EXPIRED or KNIGHT_REFERRAL.
            rationale: System-generated rationale.

        Returns:
            The created Acknowledgment record.

        Raises:
            ValueError: If reason_code is not a system reason code.
            PetitionNotFoundError: Petition doesn't exist.
            AcknowledgmentAlreadyExistsError: Petition already acknowledged.
        """
        ...

    @abstractmethod
    async def get_acknowledgment(
        self,
        acknowledgment_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by ID.

        Args:
            acknowledgment_id: The acknowledgment UUID

        Returns:
            The Acknowledgment if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_acknowledgment_by_petition(
        self,
        petition_id: UUID,
    ) -> Acknowledgment | None:
        """Retrieve an acknowledgment by petition ID.

        Args:
            petition_id: The petition UUID

        Returns:
            The Acknowledgment if the petition was acknowledged, None otherwise
        """
        ...


class AcknowledgmentRepositoryProtocol(Protocol):
    """Repository protocol for acknowledgment persistence.

    Separates persistence concerns from execution logic.
    """

    @abstractmethod
    async def save(self, acknowledgment: Acknowledgment) -> None:
        """Persist an acknowledgment record.

        Args:
            acknowledgment: The acknowledgment to save

        Raises:
            AcknowledgmentAlreadyExistsError: Acknowledgment for petition exists
        """
        ...

    @abstractmethod
    async def get_by_id(self, acknowledgment_id: UUID) -> Acknowledgment | None:
        """Retrieve acknowledgment by ID.

        Args:
            acknowledgment_id: The acknowledgment UUID

        Returns:
            The Acknowledgment if found, None otherwise
        """
        ...

    @abstractmethod
    async def get_by_petition_id(self, petition_id: UUID) -> Acknowledgment | None:
        """Retrieve acknowledgment by petition ID.

        Args:
            petition_id: The petition UUID

        Returns:
            The Acknowledgment if petition was acknowledged, None otherwise
        """
        ...

    @abstractmethod
    async def exists_for_petition(self, petition_id: UUID) -> bool:
        """Check if acknowledgment exists for a petition.

        Args:
            petition_id: The petition UUID

        Returns:
            True if an acknowledgment exists, False otherwise
        """
        ...
