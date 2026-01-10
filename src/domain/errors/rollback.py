"""Rollback domain errors (Story 3.10, Task 6).

This module defines error types for rollback operations. All errors
inherit from ValueError for consistency with other domain errors.

Constitutional Constraints:
- FR143: Rollback operations must fail loudly with clear errors
- CT-11: Silent failure destroys legitimacy - errors must be explicit

Usage:
    if not checkpoint:
        raise CheckpointNotFoundError(f"Checkpoint {checkpoint_id} not found")

    if not await halt_checker.is_halted():
        raise RollbackNotPermittedError("System must be halted for rollback")
"""

from __future__ import annotations


class CheckpointNotFoundError(ValueError):
    """Requested checkpoint does not exist.

    Raised when attempting to rollback to a checkpoint that
    cannot be found in the repository.

    Example:
        >>> raise CheckpointNotFoundError("Checkpoint abc123 not found")
    """

    pass


class RollbackNotPermittedError(ValueError):
    """Rollback not allowed in current state.

    Raised when rollback is attempted but preconditions are not met,
    such as the system not being in a halted state.

    Constitutional Constraint (CT-13):
    Integrity outranks availability - rollback requires halt state.

    Example:
        >>> raise RollbackNotPermittedError("System must be halted for rollback")
    """

    pass


class InvalidRollbackTargetError(ValueError):
    """Selected checkpoint is not valid for rollback.

    Raised when the selected checkpoint cannot be used as a rollback
    target, e.g., if it's beyond the current HEAD sequence.

    Example:
        >>> raise InvalidRollbackTargetError("Checkpoint sequence beyond current HEAD")
    """

    pass


class RollbackAlreadyInProgressError(ValueError):
    """A rollback operation is already in progress.

    Raised when attempting to start a rollback while another
    rollback operation is already active.

    Example:
        >>> raise RollbackAlreadyInProgressError("Rollback already in progress")
    """

    pass
