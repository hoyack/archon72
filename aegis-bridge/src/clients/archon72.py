"""Archon72 API client for petition submission."""

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import Archon72Config


class Archon72Error(Exception):
    """Base exception for Archon72 API errors."""

    def __init__(
        self, message: str, status_code: int | None = None, detail: Any = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class TransientError(Archon72Error):
    """Transient error that should be retried."""

    def __init__(
        self,
        message: str,
        status_code: int,
        retry_after: int | None = None,
        detail: Any = None,
    ):
        super().__init__(message, status_code, detail)
        self.retry_after = retry_after


class PermanentError(Archon72Error):
    """Permanent error that should not be retried."""

    pass


@dataclass
class SubmitPetitionRequest:
    """Request payload for petition submission."""

    type: str  # GENERAL, GRIEVANCE, CESSATION, COLLABORATION, META
    text: str
    submitter_id: str
    realm: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to API payload dict."""
        return {
            "type": self.type,
            "text": self.text,
            "submitter_id": self.submitter_id,
            "realm": self.realm,
        }


@dataclass
class SubmitPetitionResponse:
    """Response from successful petition submission."""

    petition_id: str
    state: str
    type: str
    content_hash: str
    realm: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubmitPetitionResponse":
        """Create from API response dict."""
        return cls(
            petition_id=data["petition_id"],
            state=data["state"],
            type=data["type"],
            content_hash=data["content_hash"],
            realm=data["realm"],
            created_at=data["created_at"],
        )


class Archon72Client:
    """Client for Archon72 petition submission API."""

    def __init__(self, config: Archon72Config):
        """Initialize Archon72 client.

        Args:
            config: Archon72 API configuration.
        """
        self.config = config
        self._base_url = config.api_url.rstrip("/")
        self._timeout = config.timeout_seconds

    async def submit_petition(
        self,
        request: SubmitPetitionRequest,
        idempotency_key: str | None = None,
    ) -> SubmitPetitionResponse:
        """Submit a petition to Archon72.

        Args:
            request: Petition submission request.
            idempotency_key: Optional idempotency key for deduplication.

        Returns:
            SubmitPetitionResponse on success.

        Raises:
            TransientError: For retryable errors (429, 503, 5xx).
            PermanentError: For non-retryable errors (400, 404).
            Archon72Error: For other errors.
        """
        url = f"{self._base_url}{self.config.submit_endpoint}"

        headers = {"Content-Type": "application/json"}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    url,
                    json=request.to_dict(),
                    headers=headers,
                )
            except httpx.TimeoutException as e:
                raise TransientError(
                    f"Request timeout after {self._timeout}s",
                    status_code=0,
                    retry_after=5,
                ) from e
            except httpx.RequestError as e:
                raise TransientError(
                    f"Request failed: {e}",
                    status_code=0,
                    retry_after=5,
                ) from e

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> SubmitPetitionResponse:
        """Handle API response.

        Args:
            response: HTTP response from Archon72.

        Returns:
            SubmitPetitionResponse on success.

        Raises:
            TransientError: For retryable errors.
            PermanentError: For non-retryable errors.
        """
        status = response.status_code

        # Success
        if status == 201:
            return SubmitPetitionResponse.from_dict(response.json())

        # Parse error detail if available
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        # Rate limited - transient, use Retry-After
        if status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise TransientError(
                "Rate limit exceeded",
                status_code=status,
                retry_after=retry_after,
                detail=detail,
            )

        # Service unavailable (queue full, halted) - transient
        if status == 503:
            retry_after = int(response.headers.get("Retry-After", "60"))
            raise TransientError(
                "Service unavailable",
                status_code=status,
                retry_after=retry_after,
                detail=detail,
            )

        # Server errors - transient
        if 500 <= status < 600:
            raise TransientError(
                f"Server error: {status}",
                status_code=status,
                retry_after=30,
                detail=detail,
            )

        # Bad request - permanent (validation error)
        if status == 400:
            error_msg = (
                detail.get("detail", str(detail))
                if isinstance(detail, dict)
                else str(detail)
            )
            raise PermanentError(
                f"Validation error: {error_msg}",
                status_code=status,
                detail=detail,
            )

        # Not found - permanent
        if status == 404:
            raise PermanentError(
                "Not found",
                status_code=status,
                detail=detail,
            )

        # Other client errors - permanent
        if 400 <= status < 500:
            raise PermanentError(
                f"Client error: {status}",
                status_code=status,
                detail=detail,
            )

        # Unknown status
        raise Archon72Error(
            f"Unexpected status code: {status}",
            status_code=status,
            detail=detail,
        )

    async def health_check(self) -> bool:
        """Check if Archon72 API is reachable.

        Returns:
            True if healthy, False otherwise.
        """
        # Prefer the versioned health endpoint; fall back to legacy root path.
        urls = (
            f"{self._base_url}/v1/health",
            f"{self._base_url}/health",
        )

        async with httpx.AsyncClient(timeout=5) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                except Exception:
                    continue
                if response.status_code == 200:
                    return True
                if response.status_code != 404:
                    return False
        return False
