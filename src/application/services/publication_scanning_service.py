"""Publication scanning service (Story 9.2, FR56).

Orchestrates automated keyword scanning on publications in the
pre-publish workflow. When prohibited terms are detected, the
publication is blocked (not modified), a witnessed event is created,
and an error is raised.

Constitutional Constraints:
- FR56: Automated keyword scanning on all publications
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All scan events must be witnessed (both clean and blocked)

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All scan events MUST be witnessed
3. FAIL LOUD - Never silently allow prohibited content through
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
)
from src.application.ports.publication_scanner import (
    PublicationScannerProtocol,
    PublicationScanResult,
)
from src.domain.errors.publication import (
    PublicationBlockedError,
    PublicationScanError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.publication_scan import (
    PUBLICATION_BLOCKED_EVENT_TYPE,
    PUBLICATION_SCANNED_EVENT_TYPE,
    PUBLICATION_SCANNER_SYSTEM_AGENT_ID,
    PublicationScannedEventPayload,
)
from src.domain.models.publication import PublicationScanRequest

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


class PublicationScanningService(PublicationScannerProtocol):
    """Service for publication scanning in pre-publish workflow (FR56).

    Orchestrates scanning publications for prohibited language before
    publication. Both clean and blocked publications create witnessed events.

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Scan content using ProhibitedLanguageScannerProtocol
    3. Create witnessed event for ALL scans (CT-12)
    4. If violations found:
       - Create PublicationBlockedEvent
       - Raise PublicationBlockedError (fail loud)
    5. If clean:
       - Create PublicationScannedEvent
       - Return clean result

    Attributes:
        _scanner: Scanner for detecting prohibited terms (from Story 9-1).
        _event_writer: For creating witnessed events.
        _halt_checker: For HALT CHECK FIRST pattern.
        _scan_history: In-memory scan history (per publication).

    Example:
        service = PublicationScanningService(
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Pre-publish scan
        request = PublicationScanRequest(
            publication_id="pub-123",
            content="Article content here",
            title="My Article",
        )
        try:
            result = await service.scan_for_pre_publish(request)
            # result.is_clean == True, safe to publish
        except PublicationBlockedError as e:
            # Publication was blocked, event was recorded
            # Do not publish
            ...
    """

    def __init__(
        self,
        scanner: ProhibitedLanguageScannerProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the publication scanning service.

        Args:
            scanner: Scanner for detecting prohibited terms (reuse from 9-1).
            event_writer: For creating witnessed events (CT-12).
            halt_checker: For CT-11 halt check before operations.
        """
        self._scanner = scanner
        self._event_writer = event_writer
        self._halt_checker = halt_checker
        # In-memory scan history (publication_id -> list of results)
        self._scan_history: dict[str, list[PublicationScanResult]] = {}

    async def _check_halt(self) -> None:
        """Check halt state and raise if halted (CT-11).

        Raises:
            SystemHaltedError: If system is halted.
        """
        if await self._halt_checker.is_halted():
            raise SystemHaltedError("System halted")

    async def scan_publication(
        self, request: PublicationScanRequest
    ) -> PublicationScanResult:
        """Scan a publication for prohibited language (FR56).

        Implements PublicationScannerProtocol.scan_publication.

        Args:
            request: The publication scan request.

        Returns:
            PublicationScanResult with status and any matched terms.

        Raises:
            PublicationBlockedError: If prohibited content is found.
            PublicationScanError: If the scan fails.
            SystemHaltedError: If system is in halted state.
        """
        return await self.scan_for_pre_publish(request)

    async def scan_for_pre_publish(
        self, request: PublicationScanRequest
    ) -> PublicationScanResult:
        """Scan publication in pre-publish workflow (FR56, AC1, AC2, AC3).

        Scans publication content for prohibited terms. Creates witnessed
        events for both clean and blocked outcomes (CT-12).

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Scan content via scanner port (reuse from Story 9-1)
        3. Create witnessed event (CT-12)
        4. If clean, return clean result
        5. If violation:
           a. Create blocked event payload
           b. Write witnessed event (CT-12)
           c. Raise error (fail loud)

        Args:
            request: The publication scan request.

        Returns:
            PublicationScanResult with is_clean=True if publication is clean.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            PublicationBlockedError: If prohibited terms detected (FR56).
            PublicationScanError: If scan fails (CT-11 fail loud).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        scanned_at = datetime.now(timezone.utc)

        # Scan content via scanner port (reuse from Story 9-1)
        try:
            scan_result = await self._scanner.scan_content(request.content)
        except Exception as e:
            # Per CT-11, fail loud rather than allow potentially violating content
            result = PublicationScanResult.error(
                publication_id=request.publication_id,
                scanned_at=scanned_at,
                error_message=str(e),
            )
            self._record_scan_history(result)
            raise PublicationScanError(
                source_error=e,
                publication_id=request.publication_id,
            ) from e

        # Determine result status
        if scan_result.violations_found:
            # Blocked - create blocked event and raise error
            return await self._handle_blocked_publication(
                request=request,
                matched_terms=scan_result.matched_terms,
                detection_method=scan_result.detection_method,
                scanned_at=scanned_at,
            )
        else:
            # Clean - create clean event and return result
            return await self._handle_clean_publication(
                request=request,
                detection_method=scan_result.detection_method,
                scanned_at=scanned_at,
            )

    async def _handle_clean_publication(
        self,
        request: PublicationScanRequest,
        detection_method: str,
        scanned_at: datetime,
    ) -> PublicationScanResult:
        """Handle a clean publication scan result.

        Creates witnessed event (CT-12) and returns clean result.

        Args:
            request: The publication scan request.
            detection_method: Detection method used.
            scanned_at: When the scan occurred.

        Returns:
            PublicationScanResult indicating clean publication.
        """
        # Create event payload for clean scan
        payload = PublicationScannedEventPayload.clean_scan(
            publication_id=request.publication_id,
            title=request.title,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=PUBLICATION_SCANNED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=PUBLICATION_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=scanned_at,
        )

        # Create and record result
        result = PublicationScanResult.clean(
            publication_id=request.publication_id,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )
        self._record_scan_history(result)

        return result

    async def _handle_blocked_publication(
        self,
        request: PublicationScanRequest,
        matched_terms: tuple[str, ...],
        detection_method: str,
        scanned_at: datetime,
    ) -> PublicationScanResult:
        """Handle a blocked publication scan result.

        Creates witnessed event (CT-12) and raises error.

        Args:
            request: The publication scan request.
            matched_terms: Prohibited terms detected.
            detection_method: Detection method used.
            scanned_at: When the scan occurred.

        Returns:
            Never returns - always raises.

        Raises:
            PublicationBlockedError: Always raised with violation details.
        """
        # Create event payload for blocked scan
        payload = PublicationScannedEventPayload.blocked_scan(
            publication_id=request.publication_id,
            title=request.title,
            matched_terms=matched_terms,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=PUBLICATION_BLOCKED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=PUBLICATION_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=scanned_at,
        )

        # Create and record result
        result = PublicationScanResult.blocked(
            publication_id=request.publication_id,
            matched_terms=matched_terms,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )
        self._record_scan_history(result)

        # Fail loud - raise error with violation details
        raise PublicationBlockedError(
            publication_id=request.publication_id,
            title=request.title,
            matched_terms=matched_terms,
        )

    async def batch_scan_publications(
        self, requests: list[PublicationScanRequest]
    ) -> list[PublicationScanResult]:
        """Scan multiple publications in batch (FR56).

        Scans each publication and collects results. Individual
        failures do not stop the batch; blocked publications are
        recorded in results with BLOCKED status.

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Iterate through requests
        3. For each: scan and collect result (catching blocks)
        4. Return all results

        Args:
            requests: List of publication scan requests.

        Returns:
            List of PublicationScanResult for all publications.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        results: list[PublicationScanResult] = []

        for request in requests:
            try:
                result = await self.scan_for_pre_publish(request)
                results.append(result)
            except PublicationBlockedError:
                # Get the result from history (was recorded before error)
                history = self._scan_history.get(request.publication_id, [])
                if history:
                    results.append(history[-1])
            except PublicationScanError:
                # Get the error result from history
                history = self._scan_history.get(request.publication_id, [])
                if history:
                    results.append(history[-1])

        return results

    async def get_scan_history(
        self, publication_id: str
    ) -> list[PublicationScanResult]:
        """Get scan history for a publication (FR56).

        Implements PublicationScannerProtocol.get_scan_history.

        Args:
            publication_id: ID of the publication.

        Returns:
            List of PublicationScanResult for the publication,
            ordered most recent first.
        """
        history = self._scan_history.get(publication_id, [])
        # Return most recent first
        return list(reversed(history))

    def _record_scan_history(self, result: PublicationScanResult) -> None:
        """Record a scan result in history.

        Args:
            result: The scan result to record.
        """
        if result.publication_id not in self._scan_history:
            self._scan_history[result.publication_id] = []
        self._scan_history[result.publication_id].append(result)

    def clear_history(self) -> None:
        """Clear all scan history (for testing)."""
        self._scan_history.clear()
