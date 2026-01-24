import random
import sys
import types

import pytest

fastavro_stub = types.ModuleType("fastavro")
fastavro_stub.parse_schema = lambda schema: schema  # type: ignore[assignment]
fastavro_stub.schemaless_writer = lambda *args, **kwargs: None  # type: ignore[assignment]
fastavro_stub.schemaless_reader = lambda *args, **kwargs: {}  # type: ignore[assignment]
schema_stub = types.ModuleType("fastavro.schema")
schema_stub.load_schema = lambda *args, **kwargs: {}  # type: ignore[assignment]
sys.modules.setdefault("fastavro", fastavro_stub)
sys.modules.setdefault("fastavro.schema", schema_stub)

from src.workers.error_handler import (
    ErrorAction,
    ErrorCategory,
    ErrorHandler,
    WitnessWriteError,
)


class TestRateLimitDetection:
    """Verify rate limit strings are detected as transient."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "too many concurrent requests",
            "rate limit exceeded",
            "429 Too Many Requests",
            "503 Service Unavailable",
            "temporarily unavailable",
            "OllamaException - {\"error\":\"too many concurrent requests\"}",
        ],
    )
    def test_transient_errors_return_retry(self, error_message: str) -> None:
        handler = ErrorHandler(max_attempts=3)
        error = Exception(error_message)

        decision = handler.handle(error, attempt=1)

        assert decision.action == ErrorAction.RETRY
        assert decision.category == ErrorCategory.RATE_LIMIT

    def test_max_retries_returns_dead_letter(self) -> None:
        handler = ErrorHandler(max_attempts=3)
        error = Exception("too many concurrent requests")

        decision = handler.handle(error, attempt=3)

        assert decision.action == ErrorAction.DEAD_LETTER
        assert decision.category == ErrorCategory.RATE_LIMIT


class TestDecorrelatedJitter:
    """Verify backoff stays within bounds and has variance."""

    def test_backoff_respects_max_delay(self) -> None:
        handler = ErrorHandler(
            max_attempts=10,
            base_delay_seconds=1.0,
            max_delay_seconds=10.0,
        )

        for attempt in range(1, 10):
            delay = handler._calculate_delay(ErrorCategory.RATE_LIMIT, attempt)
            assert delay <= 10.0, f"Attempt {attempt} exceeded max_delay"

    def test_backoff_has_jitter(self) -> None:
        handler = ErrorHandler(
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
        )
        random.seed(0)

        delays = [
            handler._calculate_delay(ErrorCategory.RATE_LIMIT, 3) for _ in range(10)
        ]
        unique_delays = set(delays)

        assert len(unique_delays) > 1, "No jitter detected"


class TestConstitutionalErrors:
    """Verify witness errors propagate (P5)."""

    def test_witness_error_propagates(self) -> None:
        handler = ErrorHandler()

        decision = handler.handle(WitnessWriteError("witness failed"), attempt=1)

        assert decision.action == ErrorAction.PROPAGATE
