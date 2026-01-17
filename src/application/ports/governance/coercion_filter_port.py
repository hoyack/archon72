"""CoercionFilterPort - Interface for coercion content filtering.

Story: consent-gov-3.2: Coercion Filter Service

This port defines the contract for filtering content through the
Coercion Filter before routing to participants.

Constitutional Guarantees:
- All participant-facing content MUST pass through filter (FR21)
- No bypass path exists (NFR-CONST-05)
- Filter decisions logged to ledger

References:
- FR15: System can filter outbound content for coercive language
- FR19: Earl can preview filter result before submit
- FR21: All participant-facing messages routed through filter
- NFR-CONST-05: No API or administrative path to bypass filter
- NFR-PERF-03: Filter processes in ≤200ms
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.governance.filter import FilterResult
from src.domain.governance.filter.message_type import MessageType

# Re-export MessageType for backward compatibility
__all__ = ["CoercionFilterPort", "MessageType", "FilterResult"]


@runtime_checkable
class CoercionFilterPort(Protocol):
    """Port for Coercion Filter content filtering.

    This interface defines the contract for filtering content
    before it can be routed to participants.

    Constitutional Guarantee:
    - All participant-facing content MUST pass through this port
    - Filter decisions are logged to ledger
    - Type system enforces FilteredContent wrapper
    - No bypass path exists (NFR-CONST-05)

    Filter Outcomes:
    - ACCEPTED: Content passes (possibly with transformations)
    - REJECTED: Content rejected, Earl may revise
    - BLOCKED: Severe violation, logged and blocked

    Performance Constraint (NFR-PERF-03):
    - Filter MUST complete in ≤200ms
    - If timeout, REJECT (not accept) - determinism over speed

    Usage:
        result = await filter_port.filter_content(
            content="Please review this task.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        if result.is_sendable():
            # result.content is FilteredContent - the ONLY type
            # that can reach participants
            await send_to_participant(result.content)
    """

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Filter content for coercive language.

        This is the ONLY path to create FilteredContent.
        The type system ensures no bypass path exists.

        Args:
            content: Raw content to filter
            message_type: Type of message being filtered

        Returns:
            FilterResult with decision and optionally FilteredContent.

        Constitutional Guarantee:
            Only ACCEPTED results include FilteredContent.
            REJECTED and BLOCKED results have content=None.

        Performance:
            MUST complete in ≤200ms per NFR-PERF-03.
            If processing exceeds limit, REJECT (not timeout silently).
        """
        ...

    async def preview_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Preview filter result without logging (FR19).

        Allows Earl to see what would happen before submit.
        Same logic as filter_content, but:
        - Does NOT emit events to ledger
        - Does NOT count toward rate limits
        - Does NOT trigger Knight observation on blocks

        Use this for draft preview before final submission.

        Args:
            content: Raw content to preview
            message_type: Type of message being filtered

        Returns:
            FilterResult showing what would happen if submitted.

        Note:
            Preview results are ephemeral and not recorded.
            Final submission must use filter_content().
        """
        ...
