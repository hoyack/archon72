"""Messaging adapters for infrastructure layer.

This module contains adapters for messaging and event streaming operations.

Available adapters:
- HaltStreamPublisher: Redis Streams publisher for halt signals (Story 3.3)
- HaltStreamConsumer: Redis Streams consumer for halt signals (Story 3.3)
- DualChannelHaltTransportImpl: Combined dual-channel halt transport (Story 3.3)
"""

from src.infrastructure.adapters.messaging.dual_channel_halt_impl import (
    DualChannelHaltTransportImpl,
)
from src.infrastructure.adapters.messaging.halt_stream_consumer import (
    DEFAULT_CONSUMER_GROUP,
    HaltStreamConsumer,
)
from src.infrastructure.adapters.messaging.halt_stream_publisher import (
    DEFAULT_HALT_STREAM_NAME,
    HaltStreamPublisher,
)

__all__: list[str] = [
    "DEFAULT_HALT_STREAM_NAME",
    "DEFAULT_CONSUMER_GROUP",
    "HaltStreamPublisher",
    "HaltStreamConsumer",
    "DualChannelHaltTransportImpl",
]
