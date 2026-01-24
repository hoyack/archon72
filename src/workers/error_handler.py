"""Category-specific error handling for validation workers.

Story 3.4: Implement Error Handler
ADR-005: Error handling strategy (RETRY, DEAD_LETTER, PROPAGATE, SKIP)

This module provides error classification and handling decisions for
the async validation pipeline. Errors are categorized to determine
the appropriate action:

- RETRY: Transient errors that may succeed on retry (timeout, rate limit)
- DEAD_LETTER: Permanent errors after max retries exhausted
- PROPAGATE: Constitutional errors that MUST halt the system (witness write)
- SKIP: Idempotent duplicates that are safe to ignore
"""

import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors encountered during validation."""

    # Transient - may succeed on retry
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    BROKER_UNAVAILABLE = "broker_unavailable"

    # Permanent - validation cannot succeed
    INVALID_MESSAGE = "invalid_message"
    SCHEMA_ERROR = "schema_error"
    VALIDATOR_REJECTED = "validator_rejected"

    # Constitutional - system MUST halt (P5)
    WITNESS_FAILURE = "witness_failure"
    INTEGRITY_VIOLATION = "integrity_violation"

    # Idempotent - safe to skip
    DUPLICATE = "duplicate"

    # Unknown - requires investigation
    UNKNOWN = "unknown"


class ErrorAction(Enum):
    """Action to take when an error occurs."""

    RETRY = "retry"  # Retry with backoff (if under max attempts)
    DEAD_LETTER = "dead_letter"  # Send to DLQ (max retries exhausted)
    PROPAGATE = "propagate"  # Re-raise (constitutional - halt system)
    SKIP = "skip"  # Ignore (idempotent duplicate)


@dataclass(frozen=True)
class ErrorDecision:
    """Decision about how to handle an error.

    Attributes:
        action: The action to take
        category: The error category
        should_log: Whether to log the error
        log_level: Logging level if should_log is True
        retry_delay_seconds: Delay before retry (if action is RETRY)
        context: Additional context for logging/debugging
    """

    action: ErrorAction
    category: ErrorCategory
    should_log: bool = True
    log_level: str = "warning"
    retry_delay_seconds: float = 1.0
    context: dict[str, Any] | None = None

    @property
    def is_terminal(self) -> bool:
        """Check if this decision ends processing for this message."""
        return self.action in {
            ErrorAction.DEAD_LETTER,
            ErrorAction.PROPAGATE,
            ErrorAction.SKIP,
        }


# Error type to category mapping
ERROR_CATEGORIES: dict[type[Exception], ErrorCategory] = {}


def register_error_category(
    error_type: type[Exception],
    category: ErrorCategory,
) -> None:
    """Register an error type with its category.

    Args:
        error_type: The exception type
        category: The category to assign
    """
    ERROR_CATEGORIES[error_type] = category


def categorize_error(error: Exception) -> ErrorCategory:
    """Determine the category of an error.

    Args:
        error: The exception to categorize

    Returns:
        ErrorCategory for the error
    """
    # Check registered error types
    for error_type, category in ERROR_CATEGORIES.items():
        if isinstance(error, error_type):
            return category

    # Check by error name/message patterns
    error_name = type(error).__name__.lower()
    error_msg = str(error).lower()

    # Timeout patterns
    if "timeout" in error_name or "timeout" in error_msg:
        return ErrorCategory.TIMEOUT

    # Rate limit patterns
    if (
        "ratelimit" in error_name
        or "rate limit" in error_msg
        or "429" in error_msg
        or "too many concurrent requests" in error_msg
        or "temporarily unavailable" in error_msg
        or "503" in error_msg
    ):
        return ErrorCategory.RATE_LIMIT

    # Network patterns
    if any(p in error_name for p in ["connection", "network", "socket"]):
        return ErrorCategory.NETWORK

    # Kafka broker patterns
    if "broker" in error_msg or "kafka" in error_name.lower():
        return ErrorCategory.BROKER_UNAVAILABLE

    # Schema patterns
    if "schema" in error_name or "serialization" in error_name:
        return ErrorCategory.SCHEMA_ERROR

    # Witness patterns (P5 - constitutional)
    if "witness" in error_name or "witness" in error_msg:
        return ErrorCategory.WITNESS_FAILURE

    # Integrity patterns (constitutional)
    if "integrity" in error_name or "hash" in error_name:
        return ErrorCategory.INTEGRITY_VIOLATION

    # Duplicate patterns
    if "duplicate" in error_name or "already exists" in error_msg:
        return ErrorCategory.DUPLICATE

    # Invalid message patterns
    if "invalid" in error_name or "validation" in error_name:
        return ErrorCategory.INVALID_MESSAGE

    return ErrorCategory.UNKNOWN


class ErrorHandler:
    """Error handler that decides actions based on error category.

    This handler implements ADR-005 error handling strategy:
    - Transient errors → RETRY (with backoff, up to max attempts)
    - Permanent errors → DEAD_LETTER
    - Constitutional errors → PROPAGATE (system halts)
    - Duplicates → SKIP (idempotent)

    Usage:
        handler = ErrorHandler(max_attempts=3)

        try:
            await process_message(msg)
        except Exception as e:
            decision = handler.handle(e, attempt=current_attempt)

            if decision.action == ErrorAction.RETRY:
                await asyncio.sleep(decision.retry_delay_seconds)
                continue
            elif decision.action == ErrorAction.DEAD_LETTER:
                await send_to_dlq(msg, e)
                break
            elif decision.action == ErrorAction.PROPAGATE:
                raise  # Constitutional - must halt
            elif decision.action == ErrorAction.SKIP:
                break  # Safe to ignore
    """

    # Retry configuration per category
    RETRY_DELAYS: dict[ErrorCategory, float] = {
        ErrorCategory.TIMEOUT: 2.0,
        ErrorCategory.RATE_LIMIT: 5.0,
        ErrorCategory.NETWORK: 1.0,
        ErrorCategory.BROKER_UNAVAILABLE: 3.0,
    }

    # Categories that are retryable
    RETRYABLE_CATEGORIES: set[ErrorCategory] = {
        ErrorCategory.TIMEOUT,
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.NETWORK,
        ErrorCategory.BROKER_UNAVAILABLE,
    }

    # Categories that go to DLQ immediately (no retry)
    IMMEDIATE_DLQ_CATEGORIES: set[ErrorCategory] = {
        ErrorCategory.INVALID_MESSAGE,
        ErrorCategory.SCHEMA_ERROR,
        ErrorCategory.VALIDATOR_REJECTED,
    }

    # Categories that MUST propagate (constitutional - P5)
    PROPAGATE_CATEGORIES: set[ErrorCategory] = {
        ErrorCategory.WITNESS_FAILURE,
        ErrorCategory.INTEGRITY_VIOLATION,
    }

    # Categories that are safe to skip (idempotent)
    SKIP_CATEGORIES: set[ErrorCategory] = {
        ErrorCategory.DUPLICATE,
    }

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
    ) -> None:
        """Initialize the error handler.

        Args:
            max_attempts: Maximum retry attempts before DLQ
            base_delay_seconds: Base delay for exponential backoff
            max_delay_seconds: Maximum delay cap
        """
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._max_delay = max_delay_seconds

    def handle(
        self,
        error: Exception,
        attempt: int = 1,
        context: dict[str, Any] | None = None,
    ) -> ErrorDecision:
        """Handle an error and decide the action.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-based)
            context: Optional context for logging

        Returns:
            ErrorDecision with action and details
        """
        category = categorize_error(error)

        # Log the error
        logger.debug(
            "Handling error: category=%s, attempt=%d/%d, error=%s",
            category.value,
            attempt,
            self._max_attempts,
            error,
        )

        # Constitutional errors MUST propagate (P5)
        if category in self.PROPAGATE_CATEGORIES:
            logger.critical(
                "Constitutional error - PROPAGATING: %s (category=%s)",
                error,
                category.value,
            )
            return ErrorDecision(
                action=ErrorAction.PROPAGATE,
                category=category,
                should_log=True,
                log_level="critical",
                context=context,
            )

        # Duplicates are safe to skip (idempotent)
        if category in self.SKIP_CATEGORIES:
            logger.debug(
                "Duplicate detected - SKIPPING: %s",
                error,
            )
            return ErrorDecision(
                action=ErrorAction.SKIP,
                category=category,
                should_log=True,
                log_level="debug",
                context=context,
            )

        # Immediate DLQ categories (permanent failures)
        if category in self.IMMEDIATE_DLQ_CATEGORIES:
            logger.warning(
                "Permanent error - routing to DLQ: %s (category=%s)",
                error,
                category.value,
            )
            return ErrorDecision(
                action=ErrorAction.DEAD_LETTER,
                category=category,
                should_log=True,
                log_level="warning",
                context=context,
            )

        # Retryable categories
        if category in self.RETRYABLE_CATEGORIES:
            if attempt < self._max_attempts:
                delay = self._calculate_delay(category, attempt)
                logger.warning(
                    "Transient error - RETRYING in %.1fs: %s (attempt %d/%d, category=%s)",
                    delay,
                    error,
                    attempt,
                    self._max_attempts,
                    category.value,
                )
                return ErrorDecision(
                    action=ErrorAction.RETRY,
                    category=category,
                    should_log=True,
                    log_level="warning",
                    retry_delay_seconds=delay,
                    context=context,
                )
            else:
                logger.error(
                    "Max retries exhausted - routing to DLQ: %s (attempts=%d, category=%s)",
                    error,
                    attempt,
                    category.value,
                )
                return ErrorDecision(
                    action=ErrorAction.DEAD_LETTER,
                    category=category,
                    should_log=True,
                    log_level="error",
                    context=context,
                )

        # Unknown category - treat as retryable but log for investigation
        if attempt < self._max_attempts:
            delay = self._calculate_delay(category, attempt)
            logger.warning(
                "Unknown error category - RETRYING: %s (attempt %d/%d)",
                error,
                attempt,
                self._max_attempts,
            )
            return ErrorDecision(
                action=ErrorAction.RETRY,
                category=category,
                should_log=True,
                log_level="warning",
                retry_delay_seconds=delay,
                context=context,
            )
        else:
            logger.error(
                "Unknown error - max retries exhausted, routing to DLQ: %s",
                error,
            )
            return ErrorDecision(
                action=ErrorAction.DEAD_LETTER,
                category=category,
                should_log=True,
                log_level="error",
                context=context,
            )

    def _calculate_delay(self, category: ErrorCategory, attempt: int) -> float:
        """Calculate retry delay with decorrelated jitter.

        Args:
            category: Error category
            attempt: Current attempt number

        Returns:
            Delay in seconds
        """
        # Get base delay for this category
        base = self.RETRY_DELAYS.get(category, self._base_delay)

        if attempt <= 1:
            return base

        previous = base * (2 ** (attempt - 2))
        delay = random.uniform(base, previous * 3)
        return min(delay, self._max_delay)


# Register common error types
# These will be imported and registered by domain modules


class WitnessWriteError(Exception):
    """Error writing to witness log (constitutional - P5)."""

    pass


class IntegrityViolationError(Exception):
    """Hash chain or integrity check failed (constitutional)."""

    pass


class DuplicateVoteError(Exception):
    """Vote has already been processed (idempotent)."""

    pass


class ValidationTimeoutError(Exception):
    """Validation request timed out (transient)."""

    pass


class ValidatorRateLimitError(Exception):
    """Validator LLM rate limited (transient)."""

    pass


class InvalidMessageError(Exception):
    """Message format or content is invalid (permanent)."""

    pass


class SchemaValidationError(Exception):
    """Avro schema validation failed (permanent)."""

    pass


# Register built-in error types
register_error_category(WitnessWriteError, ErrorCategory.WITNESS_FAILURE)
register_error_category(IntegrityViolationError, ErrorCategory.INTEGRITY_VIOLATION)
register_error_category(DuplicateVoteError, ErrorCategory.DUPLICATE)
register_error_category(ValidationTimeoutError, ErrorCategory.TIMEOUT)
register_error_category(ValidatorRateLimitError, ErrorCategory.RATE_LIMIT)
register_error_category(InvalidMessageError, ErrorCategory.INVALID_MESSAGE)
register_error_category(SchemaValidationError, ErrorCategory.SCHEMA_ERROR)

# Register standard library exceptions
register_error_category(TimeoutError, ErrorCategory.TIMEOUT)
register_error_category(ConnectionError, ErrorCategory.NETWORK)
