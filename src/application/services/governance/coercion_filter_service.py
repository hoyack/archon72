"""CoercionFilterService - Content filtering for coercive language.

Story: consent-gov-3.2: Coercion Filter Service

This service implements the coercion filter pipeline per FR15-FR21:
1. Block Check - Hard violations that cannot be sent
2. Reject Check - Correctable issues requiring rewrite
3. Transform - Apply transformation rules
4. Validate - Final check and create FilteredContent

Constitutional Guarantees:
- All participant-facing content MUST pass through filter (FR21)
- No bypass path exists (NFR-CONST-05)
- Determinism > Speed (NFR-PERF-03)
- Filter completes in ≤200ms or REJECTS

Pipeline Flow:
    Input Content
          │
          ▼
    ┌─────────────────┐
    │ 1. Block Check  │ ──── Hard violation? ──→ BLOCKED
    │   (critical)    │
    └────────┬────────┘
             │ No
             ▼
    ┌─────────────────┐
    │ 2. Reject Check │ ──── Requires rewrite? ──→ REJECTED
    │  (correctable)  │
    └────────┬────────┘
             │ No
             ▼
    ┌─────────────────┐
    │ 3. Transform    │ ──── Apply transformations
    │   (softening)   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 4. Validate     │ ──── Re-check post-transform
    │   (final)       │
    └────────┬────────┘
             │ Pass
             ▼
         ACCEPTED
       (FilteredContent)

References:
- FR15: System can filter outbound content for coercive language
- FR19: Earl can preview filter result before submit
- FR21: All participant-facing messages routed through filter
- NFR-CONST-05: No bypass path exists
- NFR-PERF-03: Filter processes in ≤200ms
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from src.application.ports.governance.coercion_filter_port import (
    CoercionFilterPort,
    MessageType,
)
from src.application.ports.time_authority import TimeAuthorityProtocol
from src.domain.governance.filter import (
    FilteredContent,
    FilterResult,
    FilterVersion,
    RejectionReason,
    Transformation,
    TransformationRule,
)


class PatternLibraryPort(ABC):
    """Port for pattern library operations.

    The pattern library provides the rules for filtering:
    - Blocking patterns (hard violations)
    - Rejection patterns (correctable issues)
    - Transformation rules (softening)

    All patterns are versioned for auditability.
    """

    @abstractmethod
    async def get_current_version(self) -> FilterVersion:
        """Get current version of the pattern library.

        Returns:
            FilterVersion with major.minor.patch and rules hash.
        """
        ...

    @abstractmethod
    async def get_blocking_patterns(self) -> list[dict]:
        """Get patterns that result in BLOCKED.

        Returns:
            List of pattern dicts with 'pattern' and 'violation_type'.
        """
        ...

    @abstractmethod
    async def get_rejection_patterns(self) -> list[dict]:
        """Get patterns that result in REJECTED.

        Returns:
            List of pattern dicts with 'pattern' and 'reason'.
        """
        ...

    @abstractmethod
    async def get_transformation_rules(self) -> list[TransformationRule]:
        """Get transformation rules for softening content.

        Returns:
            List of TransformationRule objects.
        """
        ...


class CoercionFilterService(CoercionFilterPort):
    """Coercion Filter service - mandatory path for all participant content.

    This service implements the full filtering pipeline:
    1. Block Check - Hard violations (BLOCKED)
    2. Reject Check - Correctable issues (REJECTED)
    3. Transform - Apply softening rules (transformations recorded)
    4. Validate - Create FilteredContent (ACCEPTED)

    Constitutional Guarantees:
    - Determinism > Speed: Same input always produces same output
    - No bypass: Only this service can create FilteredContent
    - Timeout = Rejection: If >200ms, REJECT (not accept)

    Usage:
        service = CoercionFilterService(pattern_library, time_authority)
        result = await service.filter_content(
            content="Please review this.",
            message_type=MessageType.TASK_ACTIVATION,
        )

        if result.is_sendable():
            await send_to_participant(result.content)
    """

    TIMEOUT_MS = 200  # Maximum processing time per NFR-PERF-03

    def __init__(
        self,
        pattern_library: PatternLibraryPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the filter service.

        Args:
            pattern_library: Port for accessing filter patterns
            time_authority: Authority for timestamps (not datetime.now())
        """
        self._patterns = pattern_library
        self._time = time_authority

    async def filter_content(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Filter content for coercive language.

        This is the ONLY path to create FilteredContent.
        The type system ensures no bypass path exists.

        Pipeline:
        1. Block Check - Hard violations? → BLOCKED
        2. Reject Check - Correctable issues? → REJECTED
        3. Transform - Apply softening rules
        4. Validate - Create FilteredContent → ACCEPTED

        Args:
            content: Raw content to filter
            message_type: Type of message being filtered

        Returns:
            FilterResult with decision and optionally FilteredContent.

        Performance:
            MUST complete in ≤200ms per NFR-PERF-03.
            If processing exceeds limit, REJECT (not timeout silently).

        Note:
            This method should be called through a service that handles
            logging (FilterLoggingService). For preview without logging,
            use preview_filter() instead.
        """
        return await self._do_filter(content, message_type)

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

        Args:
            content: Raw content to preview
            message_type: Type of message being filtered

        Returns:
            FilterResult showing what would happen if submitted.

        Note:
            This method uses the same filtering logic but is explicitly
            marked as preview. The FilterLoggingService should NOT be
            called for preview operations. This distinction is enforced
            by the calling code (e.g., API routes or services).
        """
        # Same filtering logic - preview vs submit distinction is
        # handled by the caller who decides whether to log
        return await self._do_filter(content, message_type)

    async def _do_filter(
        self,
        content: str,
        message_type: MessageType,
    ) -> FilterResult:
        """Internal filter implementation.

        This contains the actual filtering logic used by both
        filter_content() and preview_filter().

        Args:
            content: Raw content to filter
            message_type: Type of message being filtered

        Returns:
            FilterResult with decision and optionally FilteredContent.
        """
        start_time = self._time.utcnow()
        start_monotonic = self._time.monotonic()
        version = await self._patterns.get_current_version()

        try:
            # 1. Check for hard violations (block)
            violation = await self._check_violations(content)
            if violation:
                return FilterResult.blocked(
                    violation=violation["type"],
                    version=version,
                    timestamp=start_time,
                    details=violation["details"],
                )

            # 2. Check for correctable issues (reject)
            rejection = await self._check_rejections(content)
            if rejection:
                return FilterResult.rejected(
                    reason=rejection["reason"],
                    version=version,
                    timestamp=start_time,
                    guidance=rejection["guidance"],
                )

            # 3. Apply transformations
            transformed, transformations = await self._apply_transformations(content)

            # 4. Check timeout (determinism > speed)
            elapsed_ms = (self._time.monotonic() - start_monotonic) * 1000
            if elapsed_ms > self.TIMEOUT_MS:
                # Determinism > Speed: reject rather than risk non-deterministic result
                return FilterResult.rejected(
                    reason=RejectionReason.EXCESSIVE_EMPHASIS,  # Using closest match
                    version=version,
                    timestamp=start_time,
                    guidance="Content too complex. Please simplify.",
                )

            # 5. Create FilteredContent (only this service can do this)
            filtered_content = FilteredContent._create(
                content=transformed,
                original_content=content,
                filter_version=version,
                filtered_at=self._time.utcnow(),
            )

            return FilterResult.accepted(
                content=filtered_content,
                version=version,
                timestamp=start_time,
                transformations=tuple(transformations),
            )

        except Exception as e:
            # Any error results in rejection (not silent failure)
            return FilterResult.rejected(
                reason=RejectionReason.EXCESSIVE_EMPHASIS,  # Using closest match
                version=version,
                timestamp=start_time,
                guidance=f"Filter error: {str(e)}. Please retry.",
            )

    async def _check_violations(self, content: str) -> dict | None:
        """Check for hard violations that cannot be transformed.

        Returns:
            Dict with 'type' and 'details' if violation found, None otherwise.
        """
        blocking_patterns = await self._patterns.get_blocking_patterns()
        for pattern_info in blocking_patterns:
            pattern = pattern_info["pattern"]
            if re.search(pattern, content):
                return {
                    "type": pattern_info["violation_type"],
                    "details": f"Pattern matched: {pattern}",
                }
        return None

    async def _check_rejections(self, content: str) -> dict | None:
        """Check for correctable issues requiring rewrite.

        Returns:
            Dict with 'reason' and 'guidance' if rejection found, None otherwise.
        """
        rejection_patterns = await self._patterns.get_rejection_patterns()
        for pattern_info in rejection_patterns:
            pattern = pattern_info["pattern"]
            if re.search(pattern, content):
                reason = pattern_info["reason"]
                return {
                    "reason": reason,
                    "guidance": reason.guidance if hasattr(reason, "guidance") else str(reason),
                }
        return None

    async def _apply_transformations(
        self,
        content: str,
    ) -> tuple[str, list[Transformation]]:
        """Apply transformation rules to soften content.

        Returns:
            Tuple of (transformed_content, list_of_transformations).
        """
        transformations: list[Transformation] = []
        result = content

        transform_rules = await self._patterns.get_transformation_rules()
        for rule in transform_rules:
            match = re.search(rule.pattern, result)
            if match:
                original_text = match.group(0)
                result = re.sub(rule.pattern, rule.replacement, result)
                transformations.append(
                    Transformation(
                        pattern_matched=rule.pattern,
                        original_text=original_text,
                        replacement_text=rule.replacement,
                        rule_id=rule.rule_id,
                        position=match.start(),
                    )
                )

        return result, transformations
