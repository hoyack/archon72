"""Semantic scanning service (Story 9.7, FR110).

Orchestrates semantic analysis of content for emergence claims
that evade keyword-based detection.

Constitutional Constraints:
- FR110: Secondary semantic scanning beyond keyword matching
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All suspected violations must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Suspected violations create events
3. FAIL LOUD - Raise errors for scan failures
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.semantic_scanner import (
    SemanticScannerProtocol,
    SemanticScanResult,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.semantic_violation import (
    SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
    SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
    SemanticViolationSuspectedEventPayload,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


class SemanticScanningService:
    """Secondary semantic scanning service (FR110).

    Performs pattern-based analysis to detect emergence claims
    that evade keyword scanning through paraphrasing or encoding.

    This service provides the secondary scanning layer in the
    emergence detection pipeline:

    1. ProhibitedLanguageBlockingService (primary - deterministic keywords)
    2. SemanticScanningService (secondary - probabilistic patterns) <- THIS

    Constitutional Constraints:
    - FR110: Secondary semantic scanning beyond keyword matching
    - CT-11: HALT CHECK FIRST
    - CT-12: All suspected violations witnessed

    Developer Golden Rules:
    1. HALT CHECK FIRST - Every operation checks halt state
    2. WITNESS EVERYTHING - Suspected violations create events
    3. FAIL LOUD - Raise errors for scan failures

    Note: This service creates events for suspected violations but does NOT
    raise errors or block content. Semantic analysis is probabilistic and
    may require human review. The orchestrator decides whether to create
    a breach based on confidence threshold.

    Example:
        service = SemanticScanningService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        result = await service.check_content_semantically(
            content_id="output-123",
            content="We feel that this is an important decision.",
        )

        if result.violation_suspected and result.is_high_confidence:
            # High-confidence suspicion - may warrant breach creation
            ...
    """

    def __init__(
        self,
        scanner: SemanticScannerProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the semantic scanning service.

        Args:
            scanner: Scanner for semantic analysis (port).
            event_writer: For creating witnessed events (CT-12).
            halt_checker: For CT-11 halt check before operations.
        """
        self._scanner = scanner
        self._event_writer = event_writer
        self._halt_checker = halt_checker

    async def _check_halt(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

    async def check_content_semantically(
        self,
        content_id: str,
        content: str,
    ) -> SemanticScanResult:
        """Analyze content for semantic emergence claims (FR110, AC1-AC6).

        Performs pattern-based analysis and creates witnessed events
        for suspected violations with confidence >= threshold.

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Analyze content via scanner port
        3. Get confidence threshold from scanner
        4. If suspicion with sufficient confidence:
           a. Create SemanticViolationSuspectedEvent (CT-12)
        5. Return result (do NOT raise - this is suspected, not confirmed)

        Note: This creates events for suspected violations but does NOT
        raise errors or block content. Semantic analysis is probabilistic
        and may require human review.

        Args:
            content_id: Unique identifier for this content.
            content: Text content to analyze.

        Returns:
            SemanticScanResult with suspicion status and confidence.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            SemanticScanError: If analysis fails (CT-11 fail loud).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        # Analyze content via scanner port
        from src.domain.errors.semantic_violation import SemanticScanError

        try:
            result = await self._scanner.analyze_content(content)
        except Exception as e:
            # Per CT-11, fail loud rather than allow potentially violating content
            raise SemanticScanError(
                source_error=e,
                content_id=content_id,
            ) from e

        # Get confidence threshold
        threshold = await self._scanner.get_confidence_threshold()

        # Create event if suspected violation with sufficient confidence
        if result.violation_suspected and result.confidence_score >= threshold:
            await self._create_suspected_event(
                content_id=content_id,
                content=content,
                result=result,
            )

        return result

    async def _create_suspected_event(
        self,
        content_id: str,
        content: str,
        result: SemanticScanResult,
    ) -> None:
        """Create witnessed event for suspected violation (CT-12).

        Args:
            content_id: Identifier of the analyzed content.
            content: Original content for preview.
            result: Scan result with suspicion details.
        """
        detected_at = datetime.now(timezone.utc)

        # Create event payload
        payload = SemanticViolationSuspectedEventPayload(
            content_id=content_id,
            suspected_patterns=result.suspected_patterns,
            confidence_score=result.confidence_score,
            analysis_method=result.analysis_method,
            content_preview=content[:200] if content else "",
            detected_at=detected_at,
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=SEMANTIC_VIOLATION_SUSPECTED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=SEMANTIC_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=detected_at,
        )

    async def scan_only(
        self,
        content: str,
    ) -> SemanticScanResult:
        """Scan content without creating events (for dry-run/preview).

        This method analyzes content and returns results without
        creating witnessed events. Use for validation previews
        where you want to check before committing.

        Note: This does NOT create a witnessed event and should
        NOT be used as the final check before output.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Analyze content via scanner port
        3. Return result (no event, no exception for suspicions)

        Args:
            content: Text content to analyze.

        Returns:
            SemanticScanResult with suspicion status and confidence.

        Raises:
            SystemHaltedError: If system is halted.
            SemanticScanError: If analysis fails.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        from src.domain.errors.semantic_violation import SemanticScanError

        try:
            return await self._scanner.analyze_content(content)
        except Exception as e:
            raise SemanticScanError(
                source_error=e,
                content_id=None,
            ) from e

    async def get_confidence_threshold(self) -> float:
        """Get the current confidence threshold (FR110, AC6).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Delegate to scanner port

        Returns:
            Confidence threshold (0.0-1.0).

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._scanner.get_confidence_threshold()

    async def get_suspicious_patterns(self) -> tuple[str, ...]:
        """Get the current suspicious patterns list (FR110).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Delegate to scanner port

        Returns:
            Tuple of patterns used for semantic analysis.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._scanner.get_suspicious_patterns()
