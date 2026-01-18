"""Cessation error types for system lifecycle management.

Story: consent-gov-8.1: System Cessation Trigger
Story: consent-gov-8.2: Cessation Record Creation

This module defines errors related to cessation operations:
- CessationError: Base class for cessation-related errors
- CessationAlreadyTriggeredError: Cessation cannot be triggered twice
- MotionBlockedByCessationError: New motions rejected during cessation
- CessationRecordCreationError: Cessation record creation failed
- CessationRecordAlreadyExistsError: Cessation record already exists

Note: There is intentionally NO CessationCancelledError or similar.
Cessation cannot be cancelled - it is irreversible.
"""

from datetime import datetime
from uuid import UUID


class CessationError(Exception):
    """Base class for cessation-related errors.

    All cessation errors inherit from this class.
    """

    pass


class CessationAlreadyTriggeredError(CessationError):
    """Raised when cessation is triggered while already in progress.

    Cessation can only be triggered once. Attempting to trigger
    cessation when it has already been triggered raises this error.

    Attributes:
        original_trigger_id: ID of the first trigger.
        original_triggered_at: When cessation was originally triggered.
        original_operator_id: Who originally triggered cessation.

    Example:
        >>> try:
        ...     await cessation_service.trigger_cessation(...)
        ... except CessationAlreadyTriggeredError as e:
        ...     print(f"Already triggered at {e.original_triggered_at}")
    """

    def __init__(
        self,
        original_trigger_id: UUID,
        original_triggered_at: datetime,
        original_operator_id: UUID | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize CessationAlreadyTriggeredError.

        Args:
            original_trigger_id: ID of the original trigger.
            original_triggered_at: When cessation was originally triggered.
            original_operator_id: Who originally triggered cessation.
            message: Optional custom message.
        """
        self.original_trigger_id = original_trigger_id
        self.original_triggered_at = original_triggered_at
        self.original_operator_id = original_operator_id

        if message is None:
            message = (
                f"Cessation already triggered at {original_triggered_at.isoformat()} "
                f"(trigger_id={original_trigger_id})"
            )
        super().__init__(message)


class MotionBlockedByCessationError(CessationError):
    """Raised when a motion is submitted during cessation.

    When cessation is triggered, new motions are blocked.
    Existing in-progress motions continue to completion,
    but no new motions are accepted.

    Attributes:
        trigger_id: ID of the cessation trigger.
        triggered_at: When cessation was triggered.
        motion_id: ID of the blocked motion (if available).

    Example:
        >>> try:
        ...     await motion_service.submit_motion(motion)
        ... except MotionBlockedByCessationError as e:
        ...     print(f"System ceased at {e.triggered_at}")
    """

    def __init__(
        self,
        trigger_id: UUID,
        triggered_at: datetime,
        motion_id: UUID | None = None,
        message: str | None = None,
    ) -> None:
        """Initialize MotionBlockedByCessationError.

        Args:
            trigger_id: ID of the cessation trigger.
            triggered_at: When cessation was triggered.
            motion_id: ID of the blocked motion.
            message: Optional custom message.
        """
        self.trigger_id = trigger_id
        self.triggered_at = triggered_at
        self.motion_id = motion_id

        if message is None:
            message = (
                f"Motion blocked: system cessation in progress since "
                f"{triggered_at.isoformat()} (trigger_id={trigger_id})"
            )
        super().__init__(message)


class ExecutionBlockedByCessationError(CessationError):
    """Raised when execution is attempted after cessation completes.

    During CESSATION_TRIGGERED, existing operations may continue.
    Once CEASED, no execution is possible.

    Attributes:
        trigger_id: ID of the cessation trigger.

    Example:
        >>> try:
        ...     await executor.execute(task)
        ... except ExecutionBlockedByCessationError as e:
        ...     print(f"System has ceased: {e.trigger_id}")
    """

    def __init__(
        self,
        trigger_id: UUID,
        message: str | None = None,
    ) -> None:
        """Initialize ExecutionBlockedByCessationError.

        Args:
            trigger_id: ID of the cessation trigger.
            message: Optional custom message.
        """
        self.trigger_id = trigger_id

        if message is None:
            message = f"Execution blocked: system has ceased (trigger_id={trigger_id})"
        super().__init__(message)


class CessationRecordCreationError(CessationError):
    """Raised when cessation record creation fails.

    Cessation record creation is ATOMIC (NFR-REL-05).
    If any part fails, the entire operation fails.

    Attributes:
        cause: The underlying exception that caused the failure.
        trigger_id: ID of the cessation trigger (if available).

    Example:
        >>> try:
        ...     await record_service.create_record(trigger)
        ... except CessationRecordCreationError as e:
        ...     print(f"Record creation failed: {e}")
    """

    def __init__(
        self,
        message: str,
        cause: Exception | None = None,
        trigger_id: UUID | None = None,
    ) -> None:
        """Initialize CessationRecordCreationError.

        Args:
            message: Error message.
            cause: The underlying exception.
            trigger_id: ID of the cessation trigger.
        """
        self.cause = cause
        self.trigger_id = trigger_id
        super().__init__(message)


class CessationRecordAlreadyExistsError(CessationError):
    """Raised when attempting to create a second cessation record.

    Only ONE cessation record can exist per system instance.
    Once created, no more records can be added.

    Attributes:
        existing_record_id: ID of the existing cessation record.

    Example:
        >>> try:
        ...     await record_service.create_record(trigger)
        ... except CessationRecordAlreadyExistsError as e:
        ...     print(f"Record already exists: {e.existing_record_id}")
    """

    def __init__(
        self,
        existing_record_id: UUID,
        message: str | None = None,
    ) -> None:
        """Initialize CessationRecordAlreadyExistsError.

        Args:
            existing_record_id: ID of the existing record.
            message: Optional custom message.
        """
        self.existing_record_id = existing_record_id

        if message is None:
            message = (
                f"Cessation record already exists: {existing_record_id}. "
                "Only one cessation record allowed per system instance."
            )
        super().__init__(message)
