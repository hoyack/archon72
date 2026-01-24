"""Webhook Delivery Adapter port (Story 7.2, Task 7).

Protocol defining the interface for webhook delivery.

Constitutional Constraints:
- FR-7.3: System SHALL notify Observer on fate assignment
- CT-12: Witnessing creates accountability - all deliveries logged

Developer Golden Rules:
1. Protocol-based DI - all implementations through ports
2. HTTPS only for webhook URLs
3. Configurable timeouts and retries
"""

from abc import abstractmethod
from datetime import datetime
from typing import Protocol
from uuid import UUID


class WebhookDeliveryAdapterProtocol(Protocol):
    """Protocol for webhook delivery operations (FR-7.3, Task 7).

    This adapter handles:
    - HTTP POST to configured webhook URLs
    - Timeout handling
    - Response validation

    Constitutional Constraints:
    - FR-7.3: System SHALL notify Observer on fate assignment
    - CT-12: All deliveries logged for witnessing
    """

    @abstractmethod
    async def deliver(
        self,
        url: str,
        petition_id: UUID,
        fate: str,
        fate_reason: str | None,
        fate_timestamp: datetime,
    ) -> bool:
        """Deliver a fate notification to a webhook URL.

        Performs an HTTP POST to the configured URL with the
        notification payload as JSON.

        Args:
            url: HTTPS URL to POST to.
            petition_id: UUID of the fated petition.
            fate: Terminal fate (ACKNOWLEDGED, REFERRED, ESCALATED).
            fate_reason: Reason for fate (for ACKNOWLEDGED).
            fate_timestamp: When the fate was assigned.

        Returns:
            True if delivery succeeded (2xx response), False otherwise.

        Note:
            This method should NOT raise exceptions for delivery failures.
            Return False instead to allow retry scheduling.
        """
        ...

    @abstractmethod
    def get_timeout_seconds(self) -> float:
        """Get the configured timeout for webhook delivery.

        Returns:
            Timeout in seconds for HTTP requests.
        """
        ...

    @abstractmethod
    def get_delivery_count(self) -> int:
        """Get the total number of delivery attempts.

        Returns:
            Total delivery attempts (for metrics/testing).
        """
        ...
