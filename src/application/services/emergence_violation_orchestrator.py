"""Emergence Violation Orchestrator (Story 9.6/9.7, FR109/FR110).

Orchestrates violation detection and breach creation flow.
Coordinates between:
- ProhibitedLanguageBlockingService (primary keyword detection)
- SemanticScanningService (secondary pattern-based detection, optional)
- EmergenceViolationBreachService (breach creation)

Constitutional Constraints:
- FR109: Emergence violations create constitutional breaches
- FR110: Secondary semantic scanning beyond keyword matching
- FR55: No emergence claims (the violated requirement)
- CT-11: Silent failure destroys legitimacy -> HALT CHECK FIRST
- CT-12: All events witnessed (delegated to services)

Developer Golden Rules:
1. HALT CHECK FIRST - Check halt state before every operation
2. WITNESS EVERYTHING - Delegated to underlying services
3. FAIL LOUD - Re-raise original error after breach creation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from structlog import get_logger

from dataclasses import dataclass

from src.application.ports.halt_checker import HaltChecker
from src.application.ports.prohibited_language_scanner import ScanResult
from src.application.ports.semantic_scanner import SemanticScanResult
from src.domain.errors.prohibited_language import ProhibitedLanguageBlockedError
from src.domain.errors.writer import SystemHaltedError
from src.domain.events.breach import BreachEventPayload


@dataclass(frozen=True)
class CombinedScanResult:
    """Combined result from keyword and semantic scanning (FR109, FR110).

    Attributes:
        keyword_result: Result from primary keyword scanning.
        semantic_result: Result from secondary semantic scanning (if performed).
        semantic_suspicion: True if semantic analysis flagged content.
        breach_created: True if any scan resulted in breach creation.
    """

    keyword_result: ScanResult
    semantic_result: Optional[SemanticScanResult]
    breach_created: bool

    @property
    def semantic_suspicion(self) -> bool:
        """Check if semantic analysis flagged suspicion."""
        if self.semantic_result is None:
            return False
        return self.semantic_result.violation_suspected

    @property
    def is_clean(self) -> bool:
        """Check if content passed all scans with no issues."""
        if self.keyword_result.violations_found:
            return False
        if self.semantic_suspicion:
            return False
        return True

if TYPE_CHECKING:
    from src.application.services.emergence_violation_breach_service import (
        EmergenceViolationBreachService,
    )
    from src.application.services.prohibited_language_blocking_service import (
        ProhibitedLanguageBlockingService,
    )
    from src.application.services.semantic_scanning_service import (
        SemanticScanningService,
    )

logger = get_logger()


class EmergenceViolationOrchestrator:
    """Orchestrates violation detection and breach creation (FR109, FR110).

    This orchestrator coordinates the layered scanning flow:
    - ProhibitedLanguageBlockingService (primary - deterministic keywords)
    - SemanticScanningService (secondary - probabilistic patterns, optional)
    - EmergenceViolationBreachService (breach creation)

    Scanning Flow (FR55 → FR109 → FR110):
    1. HALT CHECK FIRST (CT-11)
    2. Primary: Keyword scan via blocking service
       - If violation: Create breach, raise error
    3. Secondary: Semantic scan (if configured)
       - If high-confidence suspicion: Create breach
       - Event is always created for suspicions (CT-12)
    4. Return clean result if both pass

    Constitutional Constraints:
    - FR109: Violations become breaches (keyword violations)
    - FR110: Secondary semantic scanning (pattern-based detection)
    - FR55: No emergence claims
    - CT-11: HALT CHECK FIRST
    - CT-12: All events witnessed (delegated)

    Example (keyword-only - backward compatible):
        orchestrator = EmergenceViolationOrchestrator(
            blocking_service=blocking_service,
            breach_service=breach_service,
            halt_checker=halt_checker,
        )

        try:
            result = await orchestrator.check_and_report_violation(
                content_id="output-123",
                content="This is clean content",
            )
            # result.violations_found == False, safe to proceed
        except ProhibitedLanguageBlockedError as e:
            # Content was blocked, breach was created
            ...

    Example (with semantic scanning):
        orchestrator = EmergenceViolationOrchestrator(
            blocking_service=blocking_service,
            breach_service=breach_service,
            halt_checker=halt_checker,
            semantic_scanner=semantic_scanner,  # Optional
        )

        result = await orchestrator.check_with_semantic_analysis(
            content_id="output-123",
            content="We feel strongly about this decision",
        )
        if result.semantic_suspicion:
            # Handle semantic suspicion (may have breach)
            ...
    """

    def __init__(
        self,
        blocking_service: ProhibitedLanguageBlockingService,
        breach_service: EmergenceViolationBreachService,
        halt_checker: HaltChecker,
        semantic_scanner: Optional[SemanticScanningService] = None,
    ) -> None:
        """Initialize the Emergence Violation Orchestrator.

        Args:
            blocking_service: Service for detecting prohibited language.
            breach_service: Service for creating breach events.
            halt_checker: Interface to check system halt state (CT-11).
            semantic_scanner: Optional service for secondary semantic analysis (FR110).
        """
        self._blocking_service = blocking_service
        self._breach_service = breach_service
        self._halt_checker = halt_checker
        self._semantic_scanner = semantic_scanner

    async def check_and_report_violation(
        self,
        content_id: str,
        content: str,
    ) -> ScanResult:
        """Check content and create breach if violation detected (FR109).

        This method provides end-to-end orchestration:
        1. HALT CHECK FIRST (CT-11)
        2. Check content via blocking service
        3. If violation:
           a. Create constitutional breach (FR109)
           b. Re-raise original error (fail loud)
        4. Return clean result if no violation

        Constitutional Constraints:
        - FR109: Violations become constitutional breaches
        - FR55: No emergence claims
        - CT-11: HALT CHECK FIRST
        - CT-12: Events witnessed (delegated to services)

        Args:
            content_id: Unique identifier for content.
            content: Text content to check.

        Returns:
            ScanResult if content is clean (violations_found=False).

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            ProhibitedLanguageBlockedError: If violation detected (after breach created).
            ProhibitedLanguageScanError: If scan fails.
        """
        log = logger.bind(
            operation="check_and_report_violation",
            content_id=content_id,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "orchestrator_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Delegate to blocking service
        # =====================================================================
        try:
            result = await self._blocking_service.check_content_for_prohibited_language(
                content_id=content_id,
                content=content,
            )

            # Clean content - no violation
            log.debug(
                "content_clean",
                message="No prohibited language detected",
            )
            return result

        except ProhibitedLanguageBlockedError as e:
            # =====================================================================
            # Violation detected - create breach (FR109)
            # =====================================================================
            log.warning(
                "fr109_violation_detected",
                matched_terms=e.matched_terms,
                message="FR109: Creating constitutional breach for emergence violation",
            )

            # Create breach for the violation
            await self._create_breach_for_error(
                content_id=content_id,
                error=e,
            )

            # Re-raise original error (fail loud)
            raise

    async def _create_breach_for_error(
        self,
        content_id: str,
        error: ProhibitedLanguageBlockedError,
    ) -> Optional[BreachEventPayload]:
        """Create breach for detected violation.

        This internal method handles breach creation and gracefully
        handles any failures (breach creation failure should not
        suppress the original violation error).

        Args:
            content_id: Identifier of the blocked content.
            error: The ProhibitedLanguageBlockedError with violation details.

        Returns:
            The created BreachEventPayload, or None if creation failed.
        """
        log = logger.bind(
            operation="_create_breach_for_error",
            content_id=content_id,
            matched_terms=error.matched_terms,
        )

        try:
            # Generate a deterministic UUID from content_id for the violation event
            # In production, we would query the event store for the actual event ID
            # For now, we use a generated UUID
            from uuid import uuid5, NAMESPACE_DNS

            violation_event_id = uuid5(
                NAMESPACE_DNS,
                f"prohibited_language_blocked:{content_id}",
            )

            breach = await self._breach_service.create_breach_for_violation(
                violation_event_id=violation_event_id,
                content_id=content_id,
                matched_terms=error.matched_terms,
                detection_method="keyword_scan",
            )

            log.info(
                "breach_created_for_violation",
                breach_id=str(breach.breach_id),
                message="FR109: Constitutional breach created",
            )

            return breach

        except SystemHaltedError:
            # System halted during breach creation - log but don't suppress
            log.error(
                "breach_creation_halted",
                message="System halted during breach creation",
            )
            return None

        except Exception as ex:
            # Breach creation failed - log error but don't suppress
            # The original violation error is still raised
            log.error(
                "breach_creation_failed",
                error=str(ex),
                message="Failed to create breach, original violation still raised",
            )
            return None

    async def check_with_semantic_analysis(
        self,
        content_id: str,
        content: str,
    ) -> CombinedScanResult:
        """Check content with both keyword and semantic scanning (FR110).

        This method provides end-to-end orchestration with semantic analysis:
        1. HALT CHECK FIRST (CT-11)
        2. Primary: Keyword scan via blocking service
           - If violation: Create breach, raise error
        3. Secondary: Semantic scan (if scanner configured)
           - If high-confidence suspicion: Create breach
           - Event is always created for suspicions (CT-12)
        4. Return combined result

        Note: This method does NOT raise on semantic suspicions - it returns
        a CombinedScanResult. Callers should check semantic_suspicion and
        breach_created to determine next steps.

        Constitutional Constraints:
        - FR110: Secondary semantic scanning beyond keyword matching
        - FR109: High-confidence suspicions create breaches
        - CT-11: HALT CHECK FIRST
        - CT-12: Events witnessed (delegated to services)

        Args:
            content_id: Unique identifier for content.
            content: Text content to check.

        Returns:
            CombinedScanResult with keyword and semantic results.

        Raises:
            SystemHaltedError: If system is halted (CT-11).
            ProhibitedLanguageBlockedError: If keyword violation detected.
            ProhibitedLanguageScanError: If keyword scan fails.
            SemanticScanError: If semantic scan fails.
        """
        log = logger.bind(
            operation="check_with_semantic_analysis",
            content_id=content_id,
            has_semantic_scanner=self._semantic_scanner is not None,
        )

        # =====================================================================
        # HALT CHECK FIRST (Developer Golden Rule, CT-11)
        # =====================================================================
        if await self._halt_checker.is_halted():
            reason = await self._halt_checker.get_halt_reason()
            log.critical(
                "orchestrator_rejected_system_halted",
                halt_reason=reason,
            )
            raise SystemHaltedError(f"CT-11: System is halted: {reason}")

        # =====================================================================
        # Primary: Keyword scan (always runs)
        # This raises ProhibitedLanguageBlockedError on violation
        # =====================================================================
        keyword_result = await self._blocking_service.check_content_for_prohibited_language(
            content_id=content_id,
            content=content,
        )

        # If we get here, keyword scan passed
        log.debug(
            "keyword_scan_passed",
            message="No prohibited language detected",
        )

        # =====================================================================
        # Secondary: Semantic scan (if configured)
        # =====================================================================
        semantic_result: Optional[SemanticScanResult] = None
        breach_created = False

        if self._semantic_scanner is not None:
            log.debug(
                "starting_semantic_scan",
                message="FR110: Running secondary semantic analysis",
            )

            semantic_result = await self._semantic_scanner.check_content_semantically(
                content_id=content_id,
                content=content,
            )

            # Check for high-confidence suspicion
            if semantic_result.violation_suspected:
                threshold = await self._semantic_scanner.get_confidence_threshold()

                log.warning(
                    "semantic_violation_suspected",
                    suspected_patterns=semantic_result.suspected_patterns,
                    confidence_score=semantic_result.confidence_score,
                    threshold=threshold,
                    message="FR110: Semantic violation suspected",
                )

                # Create breach for high-confidence suspicions
                if semantic_result.confidence_score >= threshold:
                    breach = await self._create_breach_for_semantic_suspicion(
                        content_id=content_id,
                        semantic_result=semantic_result,
                    )
                    breach_created = breach is not None

        return CombinedScanResult(
            keyword_result=keyword_result,
            semantic_result=semantic_result,
            breach_created=breach_created,
        )

    async def _create_breach_for_semantic_suspicion(
        self,
        content_id: str,
        semantic_result: SemanticScanResult,
    ) -> Optional[BreachEventPayload]:
        """Create breach for high-confidence semantic suspicion (FR110).

        This internal method handles breach creation for semantic violations
        and gracefully handles any failures.

        Args:
            content_id: Identifier of the analyzed content.
            semantic_result: The semantic scan result with suspicion details.

        Returns:
            The created BreachEventPayload, or None if creation failed.
        """
        log = logger.bind(
            operation="_create_breach_for_semantic_suspicion",
            content_id=content_id,
            suspected_patterns=semantic_result.suspected_patterns,
            confidence_score=semantic_result.confidence_score,
        )

        try:
            from uuid import uuid5, NAMESPACE_DNS

            # Generate deterministic UUID for the semantic violation
            violation_event_id = uuid5(
                NAMESPACE_DNS,
                f"semantic_violation_suspected:{content_id}",
            )

            # Use the patterns as "matched terms" for breach creation
            # Convert patterns to user-readable format
            breach = await self._breach_service.create_breach_for_violation(
                violation_event_id=violation_event_id,
                content_id=content_id,
                matched_terms=semantic_result.suspected_patterns,
                detection_method=f"semantic_{semantic_result.analysis_method}",
            )

            log.info(
                "breach_created_for_semantic_suspicion",
                breach_id=str(breach.breach_id),
                message="FR110: Constitutional breach created for semantic suspicion",
            )

            return breach

        except SystemHaltedError:
            log.error(
                "semantic_breach_creation_halted",
                message="System halted during semantic breach creation",
            )
            return None

        except Exception as ex:
            log.error(
                "semantic_breach_creation_failed",
                error=str(ex),
                message="Failed to create breach for semantic suspicion",
            )
            return None
