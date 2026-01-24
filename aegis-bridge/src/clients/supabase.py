"""Supabase client wrapper for petition operations."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from supabase import create_client, Client

from src.config import SupabaseConfig


@dataclass
class PetitionRecord:
    """Petition record from Supabase with realm data."""

    id: str
    user_id: str
    future_vision: str
    petition_type: str
    realm_api_value: str
    status: str
    submitted_at: str
    retry_count: int

    @classmethod
    def from_supabase(cls, data: dict[str, Any]) -> "PetitionRecord":
        """Create PetitionRecord from Supabase response data."""
        # Get realm from joined data
        realm_api_value = "realm_unassigned"
        if data.get("realms") and data["realms"].get("api_value"):
            realm_api_value = data["realms"]["api_value"]

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            future_vision=data["future_vision"],
            petition_type=data.get("petition_type", "GENERAL"),
            realm_api_value=realm_api_value,
            status=data["status"],
            submitted_at=data["submitted_at"],
            retry_count=data.get("retry_count", 0),
        )


class SupabaseClient:
    """Client for Supabase petition operations."""

    def __init__(self, config: SupabaseConfig):
        """Initialize Supabase client.

        Args:
            config: Supabase connection configuration.
        """
        self.config = config
        self._client: Client = create_client(config.url, config.service_key)

    async def fetch_pending_petitions(self, limit: int = 100) -> list[PetitionRecord]:
        """Fetch pending petitions with realm join.

        Args:
            limit: Maximum number of petitions to fetch.

        Returns:
            List of PetitionRecord objects.
        """
        response = (
            self._client.table(self.config.table_petitions)
            .select("*, realms(api_value)")
            .eq("status", "pending")
            .order("submitted_at")
            .limit(limit)
            .execute()
        )

        return [PetitionRecord.from_supabase(row) for row in response.data]

    async def mark_processing(self, petition_ids: list[str]) -> None:
        """Mark petitions as processing (optimistic lock).

        Args:
            petition_ids: List of petition IDs to mark.
        """
        if not petition_ids:
            return

        self._client.table(self.config.table_petitions).update(
            {
                "status": "processing",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).in_("id", petition_ids).execute()

    async def mark_submitted(
        self,
        petition_id: str,
        archon72_petition_id: str,
        archon72_state: str,
    ) -> None:
        """Mark petition as successfully submitted to Archon72.

        Args:
            petition_id: Supabase petition ID.
            archon72_petition_id: Petition ID returned by Archon72.
            archon72_state: Initial state from Archon72 (usually RECEIVED).
        """
        self._client.table(self.config.table_petitions).update(
            {
                "status": "submitted",
                "archon72_petition_id": archon72_petition_id,
                "archon72_state": archon72_state,
                "archon72_submitted_at": datetime.now(timezone.utc).isoformat(),
                "processing_error": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", petition_id).execute()

    async def mark_failed(
        self,
        petition_id: str,
        error: str,
        increment_retry: bool = True,
    ) -> None:
        """Mark petition as failed.

        Args:
            petition_id: Supabase petition ID.
            error: Error message to record.
            increment_retry: Whether to increment retry count.
        """
        # First get current retry count if incrementing
        update_data: dict[str, Any] = {
            "status": "failed",
            "processing_error": error[:1000],  # Limit error length
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if increment_retry:
            # Fetch current retry_count and increment
            response = (
                self._client.table(self.config.table_petitions)
                .select("retry_count")
                .eq("id", petition_id)
                .single()
                .execute()
            )
            current_count = response.data.get("retry_count", 0) if response.data else 0
            update_data["retry_count"] = current_count + 1

        self._client.table(self.config.table_petitions).update(update_data).eq(
            "id", petition_id
        ).execute()

    async def mark_dead_letter(self, petition_id: str, error: str) -> None:
        """Mark petition as dead letter (exceeded max retries).

        Args:
            petition_id: Supabase petition ID.
            error: Final error message.
        """
        self._client.table(self.config.table_petitions).update(
            {
                "status": "dead_letter",
                "processing_error": f"DEAD_LETTER: {error[:900]}",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", petition_id).execute()

    async def reset_to_pending(self, petition_id: str) -> None:
        """Reset a failed petition back to pending for retry.

        Args:
            petition_id: Supabase petition ID.
        """
        self._client.table(self.config.table_petitions).update(
            {
                "status": "pending",
                "processing_error": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", petition_id).execute()
