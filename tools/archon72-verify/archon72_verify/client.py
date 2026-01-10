"""HTTP client for Archon 72 Observer API.

FR44: No authentication required for read endpoints.
FR48: Rate limits identical for all users.
"""

from typing import Optional

import httpx


class ObserverClient:
    """Client for Archon 72 Observer API.

    Provides methods to fetch events and verification spec
    from the public Observer API (FR44: no auth required).

    Example:
        async with ObserverClient() as client:
            events = await client.get_events(1, 1000)
            spec = await client.get_verification_spec()
    """

    DEFAULT_BASE_URL = "https://api.archon72.io"

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize client.

        Args:
            base_url: API base URL. Defaults to production.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
        )

    async def __aenter__(self) -> "ObserverClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def get_events(
        self,
        start_sequence: int,
        end_sequence: int,
        page_size: int = 1000,
    ) -> list[dict]:
        """Fetch events by sequence range with pagination.

        Args:
            start_sequence: First sequence number.
            end_sequence: Last sequence number.
            page_size: Events per request.

        Returns:
            List of event dictionaries.
        """
        events: list[dict] = []
        offset = 0

        while True:
            response = await self._client.get(
                "/v1/observer/events",
                params={
                    "limit": page_size,
                    "offset": offset,
                },
            )
            response.raise_for_status()
            data = response.json()

            batch = data["events"]
            # Filter by sequence range
            for event in batch:
                if start_sequence <= event["sequence"] <= end_sequence:
                    events.append(event)

            if not data["pagination"]["has_more"]:
                break

            offset += page_size

        return events

    async def get_event_by_id(self, event_id: str) -> dict:
        """Fetch single event by ID.

        Args:
            event_id: Event UUID as string.

        Returns:
            Event dictionary.
        """
        response = await self._client.get(f"/v1/observer/events/{event_id}")
        response.raise_for_status()
        return response.json()

    async def get_event_by_sequence(self, sequence: int) -> dict:
        """Fetch single event by sequence number.

        Args:
            sequence: Event sequence number.

        Returns:
            Event dictionary.
        """
        response = await self._client.get(
            f"/v1/observer/events/sequence/{sequence}"
        )
        response.raise_for_status()
        return response.json()

    async def get_verification_spec(self) -> dict:
        """Fetch verification specification.

        Returns the HashVerificationSpec documenting exact
        hash computation method (FR62, FR63).

        Returns:
            Verification spec dictionary.
        """
        response = await self._client.get("/v1/observer/verification-spec")
        response.raise_for_status()
        return response.json()

    async def get_schema(self) -> dict:
        """Fetch schema documentation.

        Returns versioned schema documentation (FR50).

        Returns:
            Schema documentation dictionary.
        """
        response = await self._client.get("/v1/observer/schema")
        response.raise_for_status()
        return response.json()

    async def get_events_as_of(
        self,
        as_of_sequence: int,
        include_proof: bool = True,
        page_size: int = 1000,
    ) -> dict:
        """Fetch events as of a specific sequence with proof (FR88, FR89).

        Args:
            as_of_sequence: Maximum sequence number to include.
            include_proof: Whether to include hash chain proof.
            page_size: Events per request.

        Returns:
            Response dictionary including events, pagination, historical_query, and proof.
        """
        response = await self._client.get(
            "/v1/observer/events",
            params={
                "as_of_sequence": as_of_sequence,
                "include_proof": str(include_proof).lower(),
                "limit": page_size,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_merkle_proof(self, sequence: int) -> Optional[dict]:
        """Fetch Merkle proof for a specific event sequence (FR136, FR137).

        Args:
            sequence: Event sequence number.

        Returns:
            Merkle proof dictionary, or None if not available
            (e.g., event is in pending interval).
        """
        response = await self._client.get(
            f"/v1/observer/events/sequence/{sequence}/merkle-proof"
        )
        if response.status_code == 404:
            # Event may be in pending interval
            return None
        response.raise_for_status()
        return response.json()

    async def list_checkpoints(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """List checkpoint anchors (FR138).

        Args:
            limit: Maximum checkpoints to return.
            offset: Number to skip.

        Returns:
            Response dictionary with checkpoints and pagination.
        """
        response = await self._client.get(
            "/v1/observer/checkpoints",
            params={
                "limit": limit,
                "offset": offset,
            },
        )
        response.raise_for_status()
        return response.json()

    async def export_events(
        self,
        format: str = "jsonl",
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        event_types: Optional[list[str]] = None,
    ):
        """Stream export events for regulatory reporting (FR139).

        Args:
            format: Export format ('jsonl' or 'csv').
            start_sequence: First sequence to export.
            end_sequence: Last sequence to export.
            start_date: Filter from date (ISO 8601).
            end_date: Filter until date (ISO 8601).
            event_types: Filter by event types.

        Yields:
            Lines of export data (JSONL or CSV).
        """
        params = {"format": format}
        if start_sequence is not None:
            params["start_sequence"] = start_sequence
        if end_sequence is not None:
            params["end_sequence"] = end_sequence
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if event_types:
            params["event_type"] = ",".join(event_types)

        async with self._client.stream(
            "GET",
            "/v1/observer/export",
            params=params,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    yield line

    async def get_attestation(
        self,
        start_sequence: int,
        end_sequence: int,
    ) -> dict:
        """Get attestation metadata for an export range (FR140).

        Args:
            start_sequence: First sequence in export range.
            end_sequence: Last sequence in export range.

        Returns:
            Attestation metadata dictionary.
        """
        response = await self._client.get(
            "/v1/observer/export/attestation",
            params={
                "start_sequence": start_sequence,
                "end_sequence": end_sequence,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
