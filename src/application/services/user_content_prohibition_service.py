"""User content prohibition service (Story 9.4, FR58).

Orchestrates the evaluation of user content for featuring eligibility.
When prohibited terms are detected, the content is FLAGGED (not deleted),
a witnessed event is created, and an error is raised.

CRITICAL DISTINCTION from Publication Scanning (Story 9.2):
- Publications: BLOCK content -> don't publish
- User Content: FLAG content -> allow to exist, prevent featuring

Constitutional Constraints:
- FR58: User content subject to same prohibition for featuring
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All prohibition events must be witnessed

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - All events MUST be witnessed
3. FLAG NOT DELETE - User content is NEVER deleted, only flagged
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.prohibited_language_scanner import (
    ProhibitedLanguageScannerProtocol,
)
from src.application.ports.user_content_repository import (
    UserContentRepositoryProtocol,
)
from src.domain.errors.user_content import (
    UserContentCannotBeFeaturedException,
    UserContentNotFoundError,
)
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.user_content_prohibition import (
    USER_CONTENT_CLEARED_EVENT_TYPE,
    USER_CONTENT_PROHIBITED_EVENT_TYPE,
    USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
    UserContentClearedEventPayload,
    UserContentProhibitionEventPayload,
)
from src.domain.models.user_content import (
    FeatureRequest,
    FeaturedStatus,
    UserContent,
    UserContentProhibitionFlag,
    UserContentStatus,
)

if TYPE_CHECKING:
    from src.application.services.event_writer_service import EventWriterService


class UserContentProhibitionService:
    """Service for user content prohibition in featuring workflow (FR58).

    Orchestrates evaluating user content for featuring eligibility.
    When prohibited language is detected:
    - Content is FLAGGED (not deleted - user's property)
    - Content cannot be featured (FeaturedStatus.PROHIBITED)
    - Witnessed event is created (CT-12)
    - Error is raised (fail loud)

    Constitutional Pattern:
    1. HALT CHECK FIRST at every public operation (CT-11)
    2. Scan content using ProhibitedLanguageScannerProtocol (reuse from 9-1)
    3. Create witnessed event for ALL evaluations (CT-12)
    4. If violations found:
       - Create prohibition flag
       - Update content with FLAGGED status
       - Save content (NOT delete!)
       - Create UserContentProhibitionEvent
       - Raise UserContentCannotBeFeaturedException
    5. If clean:
       - Create UserContentClearedEvent
       - Return content with PENDING_REVIEW status

    Attributes:
        _content_repository: Repository for user content persistence.
        _scanner: Scanner for detecting prohibited terms (from Story 9-1).
        _event_writer: For creating witnessed events.
        _halt_checker: For HALT CHECK FIRST pattern.

    Example:
        service = UserContentProhibitionService(
            content_repository=content_repo,
            scanner=scanner,
            event_writer=event_writer,
            halt_checker=halt_checker,
        )

        # Evaluate for featuring
        request = FeatureRequest(
            content_id="uc_123",
            owner_id="user_456",
            content="User's article here",
            title="My Article",
        )
        try:
            content = await service.evaluate_for_featuring(request)
            # content.featured_status == FeaturedStatus.PENDING_REVIEW
        except UserContentCannotBeFeaturedException as e:
            # Content was flagged (NOT deleted), event was recorded
            # Cannot feature this content
            ...
    """

    def __init__(
        self,
        content_repository: UserContentRepositoryProtocol,
        scanner: ProhibitedLanguageScannerProtocol,
        event_writer: EventWriterService,
        halt_checker: HaltChecker,
    ) -> None:
        """Initialize the user content prohibition service.

        Args:
            content_repository: Repository for user content (new for this story).
            scanner: Scanner for detecting prohibited terms (reuse from 9-1).
            event_writer: For creating witnessed events (CT-12).
            halt_checker: For CT-11 halt check before operations.
        """
        self._content_repository = content_repository
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

    async def evaluate_for_featuring(
        self, request: FeatureRequest
    ) -> UserContent:
        """Evaluate user content for featuring eligibility (FR58).

        Scans user content for prohibited terms. Creates witnessed events
        for both clean and prohibited outcomes (CT-12).

        CRITICAL: Content is FLAGGED, not deleted if prohibited.

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Scan content via scanner port (reuse from Story 9-1)
        3. If clean:
           a. Create UserContentClearedEvent (CT-12)
           b. Return content with PENDING_REVIEW status
        4. If violation:
           a. Create prohibition flag (DO NOT DELETE)
           b. Save flagged content
           c. Create UserContentProhibitionEvent (CT-12)
           d. Raise error (fail loud)

        Args:
            request: The feature request to evaluate.

        Returns:
            UserContent with featured_status = PENDING_REVIEW if clean.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            UserContentCannotBeFeaturedException: If prohibited terms detected (FR58).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        scanned_at = datetime.now(timezone.utc)

        # Scan content via scanner port (reuse from Story 9-1)
        scan_result = await self._scanner.scan_content(request.content)

        if scan_result.violations_found:
            # FLAGGED (not deleted) - create prohibition flag
            return await self._handle_prohibited_content(
                request=request,
                matched_terms=scan_result.matched_terms,
                detection_method=scan_result.detection_method,
                flagged_at=scanned_at,
            )
        else:
            # Clean - create cleared event and return with PENDING_REVIEW
            return await self._handle_clean_content(
                request=request,
                detection_method=scan_result.detection_method,
                scanned_at=scanned_at,
            )

    async def _handle_clean_content(
        self,
        request: FeatureRequest,
        detection_method: str,
        scanned_at: datetime,
    ) -> UserContent:
        """Handle clean user content that can be featured.

        Creates witnessed event (CT-12) and returns content with PENDING_REVIEW.

        Args:
            request: The feature request.
            detection_method: Detection method used.
            scanned_at: When the scan occurred.

        Returns:
            UserContent with featured_status = PENDING_REVIEW.
        """
        # Create event payload for clean scan
        payload = UserContentClearedEventPayload.create(
            content_id=request.content_id,
            owner_id=request.owner_id,
            title=request.title,
            scanned_at=scanned_at,
            detection_method=detection_method,
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=USER_CONTENT_CLEARED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=scanned_at,
        )

        # Create content with PENDING_REVIEW status
        content = request.to_user_content(
            status=UserContentStatus.ACTIVE,
            featured_status=FeaturedStatus.PENDING_REVIEW,
            created_at=scanned_at,
        )

        # Save content to repository
        await self._content_repository.save_content(content)

        return content

    async def _handle_prohibited_content(
        self,
        request: FeatureRequest,
        matched_terms: tuple[str, ...],
        detection_method: str,
        flagged_at: datetime,
    ) -> UserContent:
        """Handle prohibited user content that cannot be featured.

        CRITICAL: Content is FLAGGED, not deleted.

        Creates prohibition flag, saves content, writes witnessed event,
        and raises error.

        Args:
            request: The feature request.
            matched_terms: Prohibited terms detected.
            detection_method: Detection method used.
            flagged_at: When the content was flagged.

        Returns:
            Never returns - always raises.

        Raises:
            UserContentCannotBeFeaturedException: Always raised.
        """
        # Create prohibition flag (content NOT deleted)
        flag = UserContentProhibitionFlag(
            flagged_at=flagged_at,
            matched_terms=matched_terms,
            can_be_featured=False,
            reviewed_by=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
        )

        # Create content with FLAGGED status and PROHIBITED featured_status
        content = request.to_user_content(
            status=UserContentStatus.FLAGGED,
            featured_status=FeaturedStatus.PROHIBITED,
            created_at=flagged_at,
            prohibition_flag=flag,
        )

        # Save flagged content (NOT deleted - user's property)
        await self._content_repository.save_content(content)

        # Create event payload for prohibition
        payload = UserContentProhibitionEventPayload.create(
            content_id=request.content_id,
            owner_id=request.owner_id,
            title=request.title,
            matched_terms=matched_terms,
            flagged_at=flagged_at,
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=USER_CONTENT_PROHIBITED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=flagged_at,
        )

        # Fail loud - raise error with violation details
        raise UserContentCannotBeFeaturedException(
            content_id=request.content_id,
            owner_id=request.owner_id,
            matched_terms=matched_terms,
        )

    async def batch_evaluate_for_featuring(
        self, requests: list[FeatureRequest]
    ) -> list[UserContent]:
        """Evaluate multiple user content items for featuring (FR58).

        Evaluates each content item and collects results. Individual
        prohibitions do not stop the batch; flagged content is
        recorded in results with FLAGGED status.

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Iterate through requests
        3. For each: evaluate and collect result (catching prohibitions)
        4. Return all results

        Args:
            requests: List of feature requests to evaluate.

        Returns:
            List of UserContent for all evaluated items.
            Flagged content has featured_status = PROHIBITED.
            Clean content has featured_status = PENDING_REVIEW.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        results: list[UserContent] = []

        for request in requests:
            try:
                content = await self.evaluate_for_featuring(request)
                results.append(content)
            except UserContentCannotBeFeaturedException:
                # Content was flagged - get it from repository
                content = await self._content_repository.get_content(
                    request.content_id
                )
                if content:
                    results.append(content)

        return results

    async def get_content_prohibition_status(
        self, content_id: str
    ) -> UserContentProhibitionFlag | None:
        """Get the prohibition status for user content (FR58, AC5).

        Args:
            content_id: ID of the content to check.

        Returns:
            UserContentProhibitionFlag if content is prohibited, None otherwise.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            UserContentNotFoundError: If content does not exist.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        content = await self._content_repository.get_content(content_id)
        if content is None:
            raise UserContentNotFoundError(content_id)

        return content.prohibition_flag

    async def clear_prohibition_flag(
        self, content_id: str, reason: str
    ) -> UserContent:
        """Clear the prohibition flag from user content (FR58).

        This is for admin/manual review override. Clears the prohibition
        flag and sets content back to ACTIVE with NOT_FEATURED status.

        Constitutional Pattern:
        1. HALT CHECK FIRST (Golden Rule #1, CT-11)
        2. Get content from repository
        3. Create cleared event (CT-12 - witnessing required)
        4. Clear flag and update content
        5. Save content

        Args:
            content_id: ID of the content to clear.
            reason: Reason for clearing the flag (for audit).

        Returns:
            Updated UserContent with flag cleared.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            UserContentNotFoundError: If content does not exist.
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        # Get existing content
        content = await self._content_repository.get_content(content_id)
        if content is None:
            raise UserContentNotFoundError(content_id)

        cleared_at = datetime.now(timezone.utc)

        # Create cleared event payload
        payload = UserContentClearedEventPayload.create(
            content_id=content.content_id,
            owner_id=content.owner_id,
            title=content.title,
            scanned_at=cleared_at,
            detection_method=f"manual_review: {reason}",
        )

        # Write witnessed event (CT-12 - WITNESS EVERYTHING)
        await self._event_writer.write_event(
            event_type=USER_CONTENT_CLEARED_EVENT_TYPE,
            payload=payload.to_dict(),
            agent_id=USER_CONTENT_SCANNER_SYSTEM_AGENT_ID,
            local_timestamp=cleared_at,
        )

        # Clear flag via repository
        cleared_content = await self._content_repository.clear_prohibition_flag(
            content_id
        )

        if cleared_content is None:
            raise UserContentNotFoundError(content_id)

        return cleared_content

    async def get_prohibited_content_list(self) -> list[UserContent]:
        """Get all content that has been flagged as prohibited (FR58).

        Returns content with FeaturedStatus.PROHIBITED.
        This content cannot be featured but is NOT deleted.

        Returns:
            List of prohibited UserContent.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._content_repository.get_prohibited_content()

    async def get_featured_candidates(self) -> list[UserContent]:
        """Get all content that is a candidate for featuring (FR58).

        Returns content with FeaturedStatus.PENDING_REVIEW,
        which have passed scanning and await curation decision.

        Returns:
            List of UserContent that can be featured.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
        """
        # HALT CHECK FIRST (Golden Rule #1)
        await self._check_halt()

        return await self._content_repository.get_featured_candidates()
