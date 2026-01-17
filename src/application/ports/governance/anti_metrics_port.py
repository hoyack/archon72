"""Anti-Metrics Port - Interface for anti-metrics enforcement.

Story: consent-gov-10.1: Anti-Metrics Data Layer Enforcement

This port defines the contract for anti-metrics enforcement at the data layer.
Implementations MUST:
1. Block prohibited table creation
2. Block prohibited column addition
3. Validate schema on startup
4. Emit enforcement events

Constitutional Guarantees:
- FR61: No participant-level performance metrics
- FR62: No completion rates per participant
- FR63: No engagement or retention tracking
- NFR-CONST-08: Anti-metrics enforced at data layer

Structural Absence Pattern:
    This interface EXPLICITLY has NO methods for:
    - Storing participant performance
    - Calculating completion rates
    - Tracking engagement metrics

    These methods do NOT exist because the functionality
    MUST NOT exist. This is structural absence enforced
    by the type system.
"""

from abc import ABC, abstractmethod

from src.domain.governance.antimetrics import ProhibitedPattern


class SchemaValidatorPort(ABC):
    """Port for schema validation operations.

    This port is used by the anti-metrics guard to validate
    that the database schema does not contain prohibited
    metric tables or columns.
    """

    @abstractmethod
    async def check_for_metric_tables(self) -> list[str]:
        """Check schema for prohibited metric tables.

        Returns:
            List of table names that match prohibited patterns.
            Empty list if schema is clean.
        """
        ...

    @abstractmethod
    async def check_for_metric_columns(self) -> list[tuple[str, str]]:
        """Check schema for prohibited metric columns.

        Returns:
            List of (table_name, column_name) tuples that match
            prohibited patterns. Empty list if schema is clean.
        """
        ...


class EventEmitterPort(ABC):
    """Port for event emission operations.

    This is a simplified event emitter port for anti-metrics
    enforcement events. Uses the governance ledger for storage.
    """

    @abstractmethod
    async def emit(
        self,
        event_type: str,
        actor: str,
        payload: dict,
    ) -> None:
        """Emit an event to the governance ledger.

        Args:
            event_type: Type of event being emitted
            actor: Who/what is emitting the event
            payload: Event data
        """
        ...


class AntiMetricsGuardPort(ABC):
    """Port for anti-metrics guard operations.

    This port defines the contract for anti-metrics enforcement.
    Implementations MUST block all metric collection attempts
    and emit violations to the ledger.

    STRUCTURAL ABSENCE:
        Notice this interface has NO methods for:
        - store_participant_performance()
        - calculate_completion_rate()
        - track_engagement()
        - record_session()

        These methods do NOT exist because the functionality
        MUST NOT exist. What doesn't exist can't be used.
    """

    @abstractmethod
    async def enforce_on_startup(self) -> None:
        """Enforce anti-metrics on system startup.

        This method MUST be called during system initialization.
        It validates the schema and emits an enforcement event.

        Raises:
            AntiMetricsViolationError: If schema contains prohibited patterns
        """
        ...

    @abstractmethod
    async def check_table_creation(self, table_name: str) -> None:
        """Check if table creation violates anti-metrics.

        Args:
            table_name: Name of table being created

        Raises:
            AntiMetricsViolationError: If table name is prohibited
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def get_prohibited_patterns(self) -> list[ProhibitedPattern]:
        """Get list of all prohibited patterns.

        Returns:
            List of ProhibitedPattern enum values that are enforced.
        """
        ...

    @abstractmethod
    async def get_enforcement_status(self) -> dict:
        """Get current enforcement status.

        Returns:
            Dict with:
                - enforced: bool - Whether anti-metrics is active
                - last_check: datetime - Last schema validation time
                - violations_detected: int - Count of violations detected
                - schema_valid: bool - Whether schema passes validation
        """
        ...

    # STRUCTURAL ABSENCE - These methods do NOT exist:
    #
    # async def store_participant_performance(self, ...): ...
    # async def calculate_completion_rate(self, ...): ...
    # async def track_engagement(self, ...): ...
    # async def record_session(self, ...): ...
    # async def save_metrics(self, ...): ...
    # async def get_performance_history(self, ...): ...
    # async def compute_retention(self, ...): ...
    #
    # If you're reading this looking for these methods,
    # they do not exist ON PURPOSE. This is constitutional.
