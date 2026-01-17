"""Event type validator for governance events.

Story: consent-gov-1.4: Write-Time Validation

Validates that event types are registered in the governance vocabulary.
Unknown event types are rejected before being appended to the ledger.

Performance Target: ≤1ms (in-memory frozenset lookup)

References:
    - AD-5: Event type validation
    - governance-architecture.md Event Naming Convention
"""

from __future__ import annotations

from difflib import get_close_matches

from src.domain.governance.errors.validation_errors import UnknownEventTypeError
from src.domain.governance.events.event_envelope import GovernanceEvent
from src.domain.governance.events.event_types import GOVERNANCE_EVENT_TYPES


class EventTypeValidator:
    """Validates that event types are registered in the governance vocabulary.

    Uses an in-memory frozenset for O(1) lookup performance.
    Optionally provides suggestions for typos via fuzzy matching.

    Constitutional Constraint:
        Unknown event types are rejected to maintain schema integrity.
        This prevents accidental or malicious injection of unrecognized events.

    Performance:
        - Event type lookup: ≤1ms (in-memory frozenset)
        - Suggestion generation: adds ~1ms when enabled

    Attributes:
        strict_mode: If True (default), only registered event types are allowed.
                     If False, any well-formed event type is allowed.
        suggest_corrections: If True (default), suggests similar event types on failure.
    """

    def __init__(
        self,
        *,
        strict_mode: bool = True,
        suggest_corrections: bool = True,
        additional_event_types: frozenset[str] | None = None,
    ) -> None:
        """Initialize the event type validator.

        Args:
            strict_mode: If True, only registered event types are allowed.
            suggest_corrections: If True, suggests similar event types on failure.
            additional_event_types: Additional event types to allow beyond
                                    the standard governance event types.
        """
        self._strict_mode = strict_mode
        self._suggest_corrections = suggest_corrections

        # Combine standard and additional event types
        if additional_event_types:
            self._allowed_types = GOVERNANCE_EVENT_TYPES | additional_event_types
        else:
            self._allowed_types = GOVERNANCE_EVENT_TYPES

    @property
    def allowed_types(self) -> frozenset[str]:
        """Get the set of allowed event types."""
        return self._allowed_types

    def _find_suggestion(self, event_type: str) -> str:
        """Find a similar event type as a suggestion.

        Args:
            event_type: The unrecognized event type.

        Returns:
            The most similar registered event type, or empty string if none found.
        """
        if not self._suggest_corrections:
            return ""

        matches = get_close_matches(
            event_type,
            list(self._allowed_types),
            n=1,
            cutoff=0.6,
        )
        return matches[0] if matches else ""

    async def validate(self, event: GovernanceEvent) -> None:
        """Validate that the event type is registered.

        Args:
            event: The GovernanceEvent to validate.

        Raises:
            UnknownEventTypeError: If event type is not registered and strict_mode is True.
        """
        if not self._strict_mode:
            # In non-strict mode, any well-formed event type is allowed
            # (format validation already done in EventMetadata)
            return

        event_type = event.event_type

        if event_type in self._allowed_types:
            return  # Valid event type

        # Event type not recognized - reject with helpful error
        suggestion = self._find_suggestion(event_type)

        raise UnknownEventTypeError(
            event_id=event.event_id,
            event_type=event_type,
            suggestion=suggestion,
        )

    def is_valid_type(self, event_type: str) -> bool:
        """Check if an event type is valid without raising.

        Args:
            event_type: The event type to check.

        Returns:
            True if the event type is allowed, False otherwise.
        """
        if not self._strict_mode:
            return True
        return event_type in self._allowed_types
