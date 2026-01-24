"""Anti-Metrics Guard Implementation.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

This adapter implements the anti-metrics guard that enforces
constitutional constraints at the data layer.

Design Philosophy - Structural Absence:
    Traditional: "Don't track metrics" (policy)
        - Can be ignored
        - Can be "accidentally" implemented
        - Requires ongoing vigilance

    Structural: No metrics infrastructure exists
        - No metric tables in schema
        - No metric endpoints in router
        - No metric fields in models
        - Cannot use what doesn't exist

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer

Implementation Notes:
- Uses regex patterns to detect prohibited table/column names
- Validates schema on startup
- Emits constitutional.anti_metrics.enforced event
- Blocks and records all violation attempts
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import uuid4

from src.application.ports.governance.anti_metrics_port import (
    AntiMetricsGuardPort,
    EventEmitterPort,
    SchemaValidatorPort,
)
from src.domain.governance.antimetrics import (
    PROHIBITED_COLUMN_PATTERNS,
    PROHIBITED_TABLE_PATTERNS,
    AntiMetricsViolation,
    AntiMetricsViolationError,
    ProhibitedPattern,
)
from src.domain.ports.time_authority import TimeAuthorityProtocol


class AntiMetricsGuard(AntiMetricsGuardPort):
    """Anti-Metrics Guard - enforces anti-metrics at data layer.

    This guard implements the structural absence pattern:
    - No metric tables allowed
    - No metric columns allowed
    - No metric endpoints allowed (validated elsewhere)
    - Collection attempts trigger violations

    Usage:
        guard = AntiMetricsGuard(
            schema_validator=schema_validator,
            event_emitter=event_emitter,
            time_authority=time_authority,
        )

        # On startup
        await guard.enforce_on_startup()

        # Before migrations
        await guard.check_table_creation("new_table")
        await guard.check_column_addition("table", "new_column")

    Constitutional Reference:
        NFR-CONST-08: Anti-metrics are enforced at data layer;
        collection endpoints do not exist.
    """

    def __init__(
        self,
        schema_validator: SchemaValidatorPort,
        event_emitter: EventEmitterPort,
        time_authority: TimeAuthorityProtocol,
    ) -> None:
        """Initialize the anti-metrics guard.

        Args:
            schema_validator: Port for validating database schema
            event_emitter: Port for emitting events to ledger
            time_authority: Authority for timestamps (not datetime.now())
        """
        self._schema = schema_validator
        self._event_emitter = event_emitter
        self._time = time_authority

        # Track enforcement state
        self._enforced: bool = False
        self._last_check: datetime | None = None
        self._violations_detected: int = 0
        self._schema_valid: bool = False

    async def enforce_on_startup(self) -> None:
        """Enforce anti-metrics on system startup.

        Validates schema has no metric tables or columns.
        Emits enforcement event on success.
        Raises error if violations found.

        Raises:
            AntiMetricsViolationError: If schema contains prohibited patterns
        """
        now = self._time.utcnow()
        self._last_check = now

        # Validate schema for metric tables
        metric_tables = await self._schema.check_for_metric_tables()
        if metric_tables:
            self._schema_valid = False
            self._violations_detected += len(metric_tables)

            # Record each violation
            for table in metric_tables:
                await self._record_violation(
                    pattern=self._classify_table_pattern(table),
                    attempted_by="schema",
                    description=f"Prohibited metric table exists: {table}",
                )

            raise AntiMetricsViolationError(
                f"Schema contains prohibited metric tables: {metric_tables}"
            )

        # Validate schema for metric columns
        metric_columns = await self._schema.check_for_metric_columns()
        if metric_columns:
            self._schema_valid = False
            self._violations_detected += len(metric_columns)

            # Record each violation
            for table, column in metric_columns:
                await self._record_violation(
                    pattern=self._classify_column_pattern(column),
                    attempted_by="schema",
                    description=f"Prohibited metric column exists: {table}.{column}",
                )

            raise AntiMetricsViolationError(
                f"Schema contains prohibited metric columns: {metric_columns}"
            )

        # Schema is clean - emit enforcement event
        self._schema_valid = True
        self._enforced = True

        await self._event_emitter.emit(
            event_type="constitutional.anti_metrics.enforced",
            actor="system",
            payload={
                "enforced_at": now.isoformat(),
                "schema_valid": True,
                "prohibited_table_patterns_checked": len(PROHIBITED_TABLE_PATTERNS),
                "prohibited_column_patterns_checked": len(PROHIBITED_COLUMN_PATTERNS),
                "violations_found": 0,
            },
        )

    async def check_table_creation(self, table_name: str) -> None:
        """Check if table creation violates anti-metrics.

        Args:
            table_name: Name of table being created

        Raises:
            AntiMetricsViolationError: If table name is prohibited
        """
        for pattern in PROHIBITED_TABLE_PATTERNS:
            if re.match(pattern, table_name):
                violation = await self._record_violation(
                    pattern=self._classify_table_pattern(table_name),
                    attempted_by="migration",
                    description=f"Attempted to create metric table: {table_name}",
                )
                raise AntiMetricsViolationError(
                    f"Cannot create metric table: {table_name}",
                    violation=violation,
                )

    async def check_column_addition(
        self,
        table_name: str,
        column_name: str,
    ) -> None:
        """Check if column addition violates anti-metrics.

        Args:
            table_name: Table the column is being added to
            column_name: Name of column being added

        Raises:
            AntiMetricsViolationError: If column name is prohibited
        """
        for pattern in PROHIBITED_COLUMN_PATTERNS:
            if re.match(pattern, column_name):
                violation = await self._record_violation(
                    pattern=self._classify_column_pattern(column_name),
                    attempted_by="migration",
                    description=f"Attempted to add metric column: {table_name}.{column_name}",
                )
                raise AntiMetricsViolationError(
                    f"Cannot add metric column: {column_name}",
                    violation=violation,
                )

    async def get_prohibited_patterns(self) -> list[ProhibitedPattern]:
        """Get list of all prohibited patterns.

        Returns:
            List of all ProhibitedPattern enum values.
        """
        return list(ProhibitedPattern)

    async def get_enforcement_status(self) -> dict:
        """Get current enforcement status.

        Returns:
            Dict with enforcement state information.
        """
        return {
            "enforced": self._enforced,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "violations_detected": self._violations_detected,
            "schema_valid": self._schema_valid,
        }

    async def _record_violation(
        self,
        pattern: ProhibitedPattern,
        attempted_by: str,
        description: str,
    ) -> AntiMetricsViolation:
        """Record and emit violation event.

        Args:
            pattern: Which prohibited pattern was violated
            attempted_by: Who/what attempted the violation
            description: Human-readable description

        Returns:
            The created violation record.
        """
        now = self._time.utcnow()
        self._violations_detected += 1

        violation = AntiMetricsViolation(
            violation_id=uuid4(),
            attempted_at=now,
            pattern=pattern,
            attempted_by=attempted_by,
            description=description,
        )

        await self._event_emitter.emit(
            event_type="constitutional.violation.anti_metrics",
            actor=attempted_by,
            payload={
                "violation_id": str(violation.violation_id),
                "pattern": pattern.value,
                "description": description,
                "attempted_at": now.isoformat(),
            },
        )

        return violation

    def _classify_table_pattern(self, table_name: str) -> ProhibitedPattern:
        """Classify which pattern a table name violates.

        Args:
            table_name: The prohibited table name

        Returns:
            The most relevant ProhibitedPattern.
        """
        name_lower = table_name.lower()

        if "engagement" in name_lower:
            return ProhibitedPattern.ENGAGEMENT_TRACKING
        if "retention" in name_lower:
            return ProhibitedPattern.RETENTION_METRICS
        if "session" in name_lower:
            return ProhibitedPattern.SESSION_TRACKING
        if "completion" in name_lower:
            return ProhibitedPattern.COMPLETION_RATE
        if "performance" in name_lower or "score" in name_lower:
            return ProhibitedPattern.PARTICIPANT_PERFORMANCE

        # Default classification
        return ProhibitedPattern.PARTICIPANT_PERFORMANCE

    def _classify_column_pattern(self, column_name: str) -> ProhibitedPattern:
        """Classify which pattern a column name violates.

        Args:
            column_name: The prohibited column name

        Returns:
            The most relevant ProhibitedPattern.
        """
        name_lower = column_name.lower()

        if "completion" in name_lower:
            return ProhibitedPattern.COMPLETION_RATE
        if "success" in name_lower or "failure" in name_lower:
            return ProhibitedPattern.COMPLETION_RATE
        if "engagement" in name_lower:
            return ProhibitedPattern.ENGAGEMENT_TRACKING
        if "retention" in name_lower:
            return ProhibitedPattern.RETENTION_METRICS
        if "session" in name_lower or "login" in name_lower:
            return ProhibitedPattern.SESSION_TRACKING
        if "response_time" in name_lower:
            return ProhibitedPattern.RESPONSE_TIME_PER_PARTICIPANT

        # Default classification
        return ProhibitedPattern.PARTICIPANT_PERFORMANCE

    # STRUCTURAL ABSENCE - These methods INTENTIONALLY do not exist:
    #
    # async def store_participant_performance(self, ...): ...
    # async def calculate_completion_rate(self, ...): ...
    # async def track_engagement(self, ...): ...
    # async def record_session(self, ...): ...
    # async def save_metrics(self, ...): ...
    # async def get_performance_history(self, ...): ...
    #
    # If you're reading this looking for these methods,
    # they do not exist ON PURPOSE. This is constitutional.
