"""Kafka audit publisher for async vote validation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.infrastructure.adapters.kafka.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class KafkaAuditPublisher:
    """Publish audit events to Kafka with circuit breaker protection."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic_prefix: str = "conclave",
        circuit_breaker: CircuitBreaker | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic_prefix = topic_prefix.strip(".")
        self._timeout = timeout_seconds
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=3,
            reset_timeout=30.0,
        )
        self._producer = None

        try:
            from confluent_kafka import Producer
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning(
                "KafkaAuditPublisher unavailable: %s",
                exc,
            )
            self._producer = None
        else:
            self._producer = Producer({"bootstrap.servers": self._bootstrap_servers})

    def _resolve_topic(self, topic: str) -> str:
        if topic.startswith(f"{self._topic_prefix}."):
            return topic
        return f"{self._topic_prefix}.{topic}"

    def _publish_sync(self, topic: str, payload: bytes) -> None:
        if not self._producer:
            return

        def delivery(err, msg):
            if err:
                raise RuntimeError(str(err))

        self._producer.produce(topic, payload, on_delivery=delivery)
        self._producer.flush(self._timeout)

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish an audit event. Errors are logged but do not raise."""
        if not self._producer:
            return

        if not self._circuit_breaker.should_allow_request():
            logger.warning("Kafka audit circuit open; skipping publish")
            return

        full_topic = self._resolve_topic(topic)
        payload = json.dumps(message, ensure_ascii=True).encode("utf-8")

        try:
            await asyncio.to_thread(self._publish_sync, full_topic, payload)
            self._circuit_breaker.record_success()
        except Exception as exc:
            logger.warning(
                "Kafka audit publish failed: %s",
                exc,
            )
            self._circuit_breaker.record_failure()
