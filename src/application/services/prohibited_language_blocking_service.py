"""Prohibited language blocking service (Story 9.1, FR55).

Orchestrates prohibited language detection and blocking.
When prohibited terms are detected, content is blocked (not modified),
a witnessed event is created, and an error is raised.

Constitutional Constraints:
- FR55: System outputs never claim emergence, consciousness, etc.
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All blocking events must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All blocking events MUST be witnessed
3. FAIL LOUD - Never silently allow prohibited content
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
    ScanResult,
)
from src.domain.errors.prohibited_language import (
    ProhibitedLanguageBlockedError,
    ProhibitedLanguageScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.prohibited_language_blocked import (
    PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
    PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID,
    ProhibitedLanguageBlockedEventPayload,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


class ProhibitedLanguageBlockingService:
    """Service for prohibited language blocking (FR55).

    Orchestrates scanning content for prohibited language and blocking
    content that contains emergence claims or similar terms.

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Scan content for prohibited terms
    3. If violations found:
       - Create witnessed ProhibitedLanguageBlockedEvent (CT-12)
       - Raise ProhibitedLanguageBlockedError (fail loud)
    4. Content is BLOCKED, never modified or filtered

    Attributes:
        _scanner: Scanner for detecting prohibited terms.
        _event_writer: For creating witnessed events.
        _halt_checker: For HALT CHECK FIRST pattern.

    Example:
        service = ProhibitedLanguageBlockingService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Check content before output
        try:
            result = await service.check_content_for_prohibited_language(
                content_id="output-123",
                content="This is clean content",
            )
            # result.violations_found == False, safe to proceed
        except ProhibitedLanguageBlockedError as e:
            # Content was blocked, event was recorded
            # Do not output content
            ...
    """

    def __init__(
        self,
        scanner: ProhibitedLanguageScannerProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the prohibited language blocking service.

        Args:
            scanner: Scanner for detecting prohibited terms.
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

    async def check_content_for_prohibited_language(
        self,
        content_id: str,
        content: str,
    ) -> ScanResult:
        """Check content for prohibited language (FR55, AC2, AC3).

        Scans content for prohibited terms. If violations are found:
        - Creates a witnessed ProhibitedLanguageBlockedEvent (CT-12)
        - Raises ProhibitedLanguageBlockedError

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Scan content via scanner port
        3. If clean, return result
        4. If violation:
           a. Create event payload
           b. Write witnessed event (CT-12)
           c. Raise error (fail loud)

        Args:
            content_id: Unique identifier for this content.
            content: Text content to scan.

        Returns:
            ScanResult with violations_found=False if content is clean.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            ProhibitedLanguageBlockedError: If prohibited terms detected (FR55).
            ProhibitedLanguageScanError: If scan fails (CT-11 fail loud).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        # Scan content via scanner port
        try:
            result = await self._scanner.scan_content(content)
        except Exception as e:
            # Per CT-11, fail loud rather than allow potentially violating content
            raise ProhibitedLanguageScanError(
                source_error=e,
                content_id=content_id,
            ) from e

        # If no violations, return clean result
        if not result.violations_found:
            return result

        # Violations found - create witnessed event and raise error
        blocked_at = datetime.now(timezone.utc)

        # Create event payload
        payload = ProhibitedLanguageBlockedEventPayload(
            content_id=content_id,
            matched_terms=result.matched_terms,
            detection_method=result.detection_method,
            blocked_at=blocked_at,
            content_preview=content[:200] if content else "",
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=PROHIBITED_LANGUAGE_BLOCKED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=PROHIBITED_LANGUAGE_SYSTEM_AGENT_ID,
            local_timestamp=blocked_at,
        )

        # Fail loud - raise error with violation details
        raise ProhibitedLanguageBlockedError(
            content_id=content_id,
            matched_terms=result.matched_terms,
        )

    async def get_prohibited_terms(self) -> tuple[str, ...]:
        """Get the current prohibited terms list (FR55, AC1).

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Delegate to scanner port

        Returns:
            Tuple of prohibited terms.

        Raises:
            SystemHaltedError: If system is halted.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._scanner.get_prohibited_terms()

    async def scan_only(
        self,
        content: str,
    ) -> ScanResult:
        """Scan content without blocking (for dry-run/preview).

        This method scans content and returns results without
        creating events or raising errors. Use for validation
        previews where you want to check before committing.

        Note: This does NOT create a witnessed event and should
        NOT be used as the final check before output.

        Constitutional Pattern:
        1. HALT CHECK FIRST (CT-11)
        2. Delegate to scanner port
        3. Return result (no event, no exception)

        Args:
            content: Text content to scan.

        Returns:
            ScanResult with violations_found and matched_terms.

        Raises:
            SystemHaltedError: If system is halted.
            ProhibitedLanguageScanError: If scan fails.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        try:
            return await self._scanner.scan_content(content)
        except Exception as e:
            raise ProhibitedLanguageScanError(
                source_error=e,
                content_id=None,
            ) from e
