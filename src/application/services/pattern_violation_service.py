"""Pattern Violation Detection Service (Story 8.8, AC6).

This service detects pattern violations from the FMEA risk matrix,
including raw string event types, plain string hashes, and missing
HaltGuard checks.

Constitutional Constraints:
- PV-001: Raw string event type (EventType enum required)
- PV-002: Plain string hash (ContentRef validation required)
- PV-003: Missing HaltGuard (base class requirement)

Developer Golden Rules:
1. VALIDATE TYPES - All event types must use EventType enum
2. VALIDATE REFS - All content hashes must use ContentRef
3. HALT CHECK FIRST - All services must have HaltGuard
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Type

from src.application.services.base import LoggingMixin
from src.domain.errors.failure_prevention import FailureModeViolationError
from src.domain.models.failure_mode import FailureModeId
from src.domain.models.pattern_violation import (
    PatternViolation,
    PatternViolationType,
    ViolationScan,
    ViolationSeverity,
)


class PatternViolationService(LoggingMixin):
    """Detects pattern violations from FMEA risk matrix (AC6).

    This service provides:
    1. EventType enum validation (PV-001)
    2. ContentRef validation (PV-002)
    3. HaltGuard injection validation (PV-003)
    4. Violation scanning and reporting

    Constitutional Constraints:
    - PV-001: Raw string event type creates orphan events
    - PV-002: Plain string hash creates invalid refs
    - PV-003: Missing HaltGuard allows operations during halt
    """

    def __init__(self) -> None:
        """Initialize the Pattern Violation Service."""
        self._init_logger(component="constitutional")
        self._violations: list[PatternViolation] = []
        self._scan_results: list[ViolationScan] = []

    def validate_event_type(
        self,
        event_type: Any,
        location: Optional[str] = None,
    ) -> bool:
        """Validate that an event type uses EventType enum (PV-001).

        Constitutional Constraint (PV-001):
        Raw string event types can create orphan events that are
        not properly tracked or processed.

        Args:
            event_type: The event type to validate.
            location: Optional file:line for violation reporting.

        Returns:
            True if event_type is valid (an Enum), False otherwise.
        """
        log = self._log_operation(
            "validate_event_type",
            event_type_value=str(event_type),
            event_type_type=type(event_type).__name__,
        )

        # Check if it's an Enum instance
        is_valid = isinstance(event_type, Enum)

        if not is_valid:
            violation = PatternViolation.create(
                violation_type=PatternViolationType.RAW_STRING_EVENT_TYPE,
                location=location or "unknown",
                description=(
                    f"Raw string event type '{event_type}' detected. "
                    f"Use EventType enum instead."
                ),
            )
            self._violations.append(violation)

            log.warning(
                "pattern_violation_detected",
                violation_id=str(violation.violation_id),
                violation_type=PatternViolationType.RAW_STRING_EVENT_TYPE.value,
            )
        else:
            log.debug("event_type_valid")

        return is_valid

    def validate_content_ref(
        self,
        hash_value: Any,
        location: Optional[str] = None,
    ) -> bool:
        """Validate that a hash uses ContentRef type (PV-002).

        Constitutional Constraint (PV-002):
        Plain string hashes can create invalid refs that fail
        verification or point to wrong content.

        Args:
            hash_value: The hash/ref value to validate.
            location: Optional file:line for violation reporting.

        Returns:
            True if hash_value is valid ContentRef, False otherwise.
        """
        log = self._log_operation(
            "validate_content_ref",
            hash_type=type(hash_value).__name__,
        )

        # Check if it's a ContentRef (NewType wrapper around str with validation)
        # ContentRef should start with "cref-" prefix or similar marker
        is_valid = False

        if hasattr(hash_value, '__class__'):
            type_name = hash_value.__class__.__name__

            # Check for ContentRef type or properly prefixed string
            if type_name == 'ContentRef':
                is_valid = True
            elif isinstance(hash_value, str):
                # ContentRef strings should have the proper prefix
                is_valid = hash_value.startswith('cref-')

        if not is_valid:
            violation = PatternViolation.create(
                violation_type=PatternViolationType.PLAIN_STRING_HASH,
                location=location or "unknown",
                description=(
                    f"Plain string hash detected (type: {type(hash_value).__name__}). "
                    f"Use ContentRef with create_content_ref() instead."
                ),
            )
            self._violations.append(violation)

            log.warning(
                "pattern_violation_detected",
                violation_id=str(violation.violation_id),
                violation_type=PatternViolationType.PLAIN_STRING_HASH.value,
            )
        else:
            log.debug("content_ref_valid")

        return is_valid

    def validate_halt_guard_injection(
        self,
        service: Any,
        location: Optional[str] = None,
    ) -> bool:
        """Validate that a service has HaltGuard/HaltChecker injection (PV-003).

        Constitutional Constraint (PV-003):
        Services without HaltGuard can perform operations during halt,
        which violates constitutional integrity.

        Args:
            service: The service instance to validate.
            location: Optional file:line for violation reporting.

        Returns:
            True if service has halt checking capability, False otherwise.
        """
        log = self._log_operation(
            "validate_halt_guard_injection",
            service_type=type(service).__name__,
        )

        # Check for halt checker attributes
        has_halt_guard = any([
            hasattr(service, '_halt_checker'),
            hasattr(service, '_halt_transport'),
            hasattr(service, 'halt_checker'),
            hasattr(service, 'halt_transport'),
            hasattr(service, 'is_halted'),
            hasattr(service, '_is_halted'),
        ])

        if not has_halt_guard:
            violation = PatternViolation.create(
                violation_type=PatternViolationType.MISSING_HALT_GUARD,
                location=location or f"Service: {type(service).__name__}",
                description=(
                    f"Service '{type(service).__name__}' has no HaltChecker injection. "
                    f"All constitutional services must check halt state."
                ),
            )
            self._violations.append(violation)

            log.warning(
                "pattern_violation_detected",
                violation_id=str(violation.violation_id),
                violation_type=PatternViolationType.MISSING_HALT_GUARD.value,
            )
        else:
            log.debug("halt_guard_valid")

        return has_halt_guard

    def detect_violations(self) -> list[PatternViolation]:
        """Get all detected violations.

        Returns:
            List of all PatternViolation objects.
        """
        return list(self._violations)

    def get_unresolved_violations(self) -> list[PatternViolation]:
        """Get all unresolved violations.

        Returns:
            List of violations that haven't been resolved.
        """
        return [v for v in self._violations if not v.is_resolved]

    def get_blocking_violations(self) -> list[PatternViolation]:
        """Get violations that block deployment.

        Returns:
            List of critical/high severity unresolved violations.
        """
        return [v for v in self._violations if v.blocks_deployment]

    def resolve_violation(
        self,
        violation_id: str,
        resolved_by: str,
    ) -> bool:
        """Mark a violation as resolved.

        Args:
            violation_id: The violation ID to resolve.
            resolved_by: Who resolved the violation.

        Returns:
            True if violation was found and resolved, False otherwise.
        """
        log = self._log_operation(
            "resolve_violation",
            violation_id=violation_id,
            resolved_by=resolved_by,
        )

        from uuid import UUID

        target_id = UUID(violation_id)

        for i, violation in enumerate(self._violations):
            if violation.violation_id == target_id:
                self._violations[i] = violation.resolve(resolved_by)
                log.info("violation_resolved")
                return True

        log.warning("violation_not_found")
        return False

    def raise_if_violations_block(self) -> None:
        """Raise error if any violations block deployment.

        Raises:
            FailureModeViolationError: If blocking violations exist.
        """
        blocking = self.get_blocking_violations()

        if blocking:
            # Get the most severe violation
            critical = [v for v in blocking if v.is_critical]
            most_severe = critical[0] if critical else blocking[0]

            raise FailureModeViolationError(
                mode_id=FailureModeId(most_severe.violation_type.value),
                violation_description=(
                    f"{len(blocking)} blocking violation(s) detected. "
                    f"Most severe: {most_severe.description}"
                ),
                location=most_severe.location,
                remediation=most_severe.remediation,
            )

    def create_scan_report(
        self,
        files_scanned: int,
        scan_duration_ms: int,
    ) -> ViolationScan:
        """Create a scan report from current violations.

        Args:
            files_scanned: Number of files that were scanned.
            scan_duration_ms: Scan duration in milliseconds.

        Returns:
            ViolationScan report.
        """
        log = self._log_operation(
            "create_scan_report",
            files_scanned=files_scanned,
            scan_duration_ms=scan_duration_ms,
        )

        unresolved = self.get_unresolved_violations()
        scan = ViolationScan.create(
            violations=unresolved,
            files_scanned=files_scanned,
            scan_duration_ms=scan_duration_ms,
        )

        self._scan_results.append(scan)

        # Keep only last 100 scans
        if len(self._scan_results) > 100:
            self._scan_results = self._scan_results[-100:]

        log.info(
            "scan_report_created",
            violation_count=len(unresolved),
            critical_count=scan.critical_count,
            blocking_count=scan.blocking_count,
            blocks_deployment=scan.blocks_deployment,
        )

        return scan

    def get_violation_stats(self) -> dict[str, Any]:
        """Get violation statistics.

        Returns:
            Dictionary with violation statistics.
        """
        unresolved = self.get_unresolved_violations()
        blocking = self.get_blocking_violations()

        by_type: dict[str, int] = {}
        for v in unresolved:
            key = v.violation_type.value
            by_type[key] = by_type.get(key, 0) + 1

        by_severity: dict[str, int] = {}
        for v in unresolved:
            key = v.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1

        return {
            "total_violations": len(self._violations),
            "unresolved_count": len(unresolved),
            "resolved_count": len(self._violations) - len(unresolved),
            "blocking_count": len(blocking),
            "blocks_deployment": len(blocking) > 0,
            "by_type": by_type,
            "by_severity": by_severity,
            "recent_scans": len(self._scan_results),
        }

    def get_violation_summary(self) -> str:
        """Get human-readable violation summary.

        Returns:
            Summary string.
        """
        stats = self.get_violation_stats()

        if stats["unresolved_count"] == 0:
            return "✅ No pattern violations detected"

        status = "🚨 BLOCKING" if stats["blocks_deployment"] else "⚠️ VIOLATIONS"

        lines = [
            f"{status}: {stats['unresolved_count']} unresolved pattern violation(s)",
            "",
            "By type:",
        ]

        for vtype, count in stats["by_type"].items():
            lines.append(f"  - {vtype}: {count}")

        lines.append("")
        lines.append("By severity:")

        for severity, count in stats["by_severity"].items():
            lines.append(f"  - {severity}: {count}")

        return "\n".join(lines)
