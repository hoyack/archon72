"""Constitutional primitive: Prevent deletion of domain entities (FR80).

This module provides a mixin class that prevents deletion of constitutional
entities. Any attempt to delete an entity using this mixin will raise a
ConstitutionalViolationError.

Constitutional Constraint (FR80):
    Events and constitutional entities cannot be deleted.
    Any attempt to delete raises ConstitutionalViolationError.

Constitutional Truths Honored:
    - CT-11: Silent failure destroys legitimacy → HALT OVER DEGRADE
    - CT-13: Integrity outranks availability

Usage:
    class MyEntity(BaseModel, DeletePreventionMixin):
        ...

    entity = MyEntity()
    entity.delete()  # Raises ConstitutionalViolationError
"""

from src.domain.errors.constitutional import ConstitutionalViolationError


class DeletePreventionMixin:
    """Mixin that prevents deletion of domain entities.

    Constitutional Constraint (FR80):
    Events and constitutional entities cannot be deleted.
    Any attempt to delete raises ConstitutionalViolationError.

    This mixin should be inherited by any domain entity that must
    be immutable and cannot be deleted. It provides a `delete()` method
    that always raises an error, making the forbidden operation visible
    rather than silent.

    Example:
        >>> class Event(DeletePreventionMixin):
        ...     pass
        >>> event = Event()
        >>> event.delete()  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ConstitutionalViolationError: FR80: Deletion prohibited...
    """

    def delete(self) -> None:
        """Raise ConstitutionalViolationError - deletion is prohibited.

        This method always raises an error. It exists to explicitly
        prevent deletion operations and make any such attempts visible.

        Raises:
            ConstitutionalViolationError: Always raised with FR80 reference.
        """
        raise ConstitutionalViolationError(
            "FR80: Deletion prohibited - constitutional entities are immutable"
        )
