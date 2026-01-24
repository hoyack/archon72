import asyncio
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

from src.application.ports.vote_publisher import PublishResponse, PublishResult


class _DummyMessage:
    def __init__(self, validator_id: str) -> None:
        self._validator_id = validator_id

    def headers(self) -> list[tuple[str, bytes]]:
        return [("validator_id", self._validator_id.encode("utf-8"))]

    def value(self) -> bytes:
        return b"dummy"


class _DummySerializer:
    def __init__(self, request_data: dict[str, object]) -> None:
        self._request_data = request_data

    def deserialize(self, schema_name: str, data: bytes) -> dict[str, object]:
        return self._request_data


class _DummyValidator:
    def __init__(self) -> None:
        self.current = 0
        self.max_seen = 0

    async def validate_vote(
        self, raw_response: str, optimistic_choice: str
    ) -> tuple[str, float]:
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        await asyncio.sleep(0.05)
        self.current -= 1
        return "APPROVE", 0.9


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.workers.validator_worker as validator_worker

    max_concurrent = 2
    monkeypatch.setattr(
        validator_worker,
        "OLLAMA_SEMAPHORE",
        asyncio.Semaphore(max_concurrent),
    )

    validator = _DummyValidator()
    worker = validator_worker.ValidatorWorker(
        bootstrap_servers="localhost:19092",
        schema_registry_url="http://localhost:18081",
        consumer_group="test-group",
        validator_id="furcas_validator",
        validator=validator,
    )

    request_data = {
        "vote_id": "vote-1",
        "session_id": "session-1",
        "raw_response": "raw",
        "optimistic_choice": "APPROVE",
        "attempt": 1,
    }

    worker._serializer = _DummySerializer(request_data)

    async def _publish_result_stub(*_args, **_kwargs) -> PublishResponse:
        return PublishResponse(result=PublishResult.SUCCESS)

    worker._publish_result = _publish_result_stub

    messages = [_DummyMessage("furcas_validator") for _ in range(10)]
    await asyncio.gather(*(worker._process_message(msg) for msg in messages))

    assert validator.max_seen <= max_concurrent
