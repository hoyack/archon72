"""Petition extractor - transforms and processes petitions from Supabase."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.clients.archon72 import (
    Archon72Client,
    PermanentError,
    SubmitPetitionRequest,
    SubmitPetitionResponse,
    TransientError,
)
from src.clients.supabase import PetitionRecord, SupabaseClient
from src.config import ProcessingConfig

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a single petition."""

    petition_id: str
    success: bool
    archon72_petition_id: str | None = None
    archon72_state: str | None = None
    error: str | None = None
    should_retry: bool = False


@dataclass
class BatchResult:
    """Result of processing a batch of petitions."""

    total: int
    successful: int
    failed: int
    retryable: int
    results: list[ProcessingResult]


class PetitionExtractor:
    """Extracts and processes petitions from Supabase to Archon72.

    Direct mode: Pulls petitions, transforms, submits, and updates status.
    No queue involved - synchronous processing.
    """

    def __init__(
        self,
        supabase: SupabaseClient,
        archon72: Archon72Client,
        config: ProcessingConfig,
    ):
        """Initialize extractor.

        Args:
            supabase: Supabase client for data access.
            archon72: Archon72 API client for submission.
            config: Processing configuration.
        """
        self.supabase = supabase
        self.archon72 = archon72
        self.config = config

    def transform(self, petition: PetitionRecord) -> SubmitPetitionRequest:
        """Transform Supabase petition to Archon72 API request.

        Args:
            petition: Petition record from Supabase.

        Returns:
            SubmitPetitionRequest ready for Archon72 API.
        """
        return SubmitPetitionRequest(
            type=petition.petition_type,
            text=petition.future_vision,
            submitter_id=petition.user_id,
            realm=petition.realm_api_value,
        )

    async def process_single(self, petition: PetitionRecord) -> ProcessingResult:
        """Process a single petition.

        Args:
            petition: Petition record to process.

        Returns:
            ProcessingResult with success/failure details.
        """
        idempotency_key = f"aegis-{petition.id}"

        try:
            # Transform
            request = self.transform(petition)

            # Submit (or dry run)
            if self.config.dry_run:
                logger.info(f"[DRY RUN] Would submit petition {petition.id}")
                logger.info(f"  Payload: {request.to_dict()}")
                return ProcessingResult(
                    petition_id=petition.id,
                    success=True,
                    archon72_petition_id="dry-run-id",
                    archon72_state="DRY_RUN",
                )

            response = await self.archon72.submit_petition(request, idempotency_key)

            # Update Supabase on success
            await self.supabase.mark_submitted(
                petition_id=petition.id,
                archon72_petition_id=response.petition_id,
                archon72_state=response.state,
            )

            logger.info(
                f"Submitted petition {petition.id} -> {response.petition_id} ({response.state})"
            )

            return ProcessingResult(
                petition_id=petition.id,
                success=True,
                archon72_petition_id=response.petition_id,
                archon72_state=response.state,
            )

        except PermanentError as e:
            # Non-retryable error
            logger.error(f"Permanent error for petition {petition.id}: {e}")

            await self.supabase.mark_failed(
                petition_id=petition.id,
                error=str(e),
                increment_retry=False,
            )

            return ProcessingResult(
                petition_id=petition.id,
                success=False,
                error=str(e),
                should_retry=False,
            )

        except TransientError as e:
            # Retryable error
            logger.warning(
                f"Transient error for petition {petition.id}: {e} "
                f"(retry_after={e.retry_after}s)"
            )

            # Check if exceeded max retries
            if petition.retry_count >= self.config.max_retries:
                logger.error(
                    f"Petition {petition.id} exceeded max retries ({self.config.max_retries})"
                )
                await self.supabase.mark_dead_letter(petition.id, str(e))
                return ProcessingResult(
                    petition_id=petition.id,
                    success=False,
                    error=f"DEAD_LETTER: {e}",
                    should_retry=False,
                )

            await self.supabase.mark_failed(
                petition_id=petition.id,
                error=str(e),
                increment_retry=True,
            )

            return ProcessingResult(
                petition_id=petition.id,
                success=False,
                error=str(e),
                should_retry=True,
            )

        except Exception as e:
            # Unexpected error - treat as transient
            logger.exception(f"Unexpected error for petition {petition.id}: {e}")

            await self.supabase.mark_failed(
                petition_id=petition.id,
                error=f"Unexpected: {e}",
                increment_retry=True,
            )

            return ProcessingResult(
                petition_id=petition.id,
                success=False,
                error=str(e),
                should_retry=True,
            )

    async def process_batch(self) -> BatchResult:
        """Process a batch of pending petitions.

        Fetches pending petitions, marks them as processing,
        then processes each one.

        Returns:
            BatchResult with aggregate statistics.
        """
        # Fetch pending petitions
        petitions = await self.supabase.fetch_pending_petitions(self.config.batch_size)

        if not petitions:
            logger.info("No pending petitions to process")
            return BatchResult(
                total=0,
                successful=0,
                failed=0,
                retryable=0,
                results=[],
            )

        logger.info(f"Processing {len(petitions)} pending petitions")

        # Mark as processing (optimistic lock)
        petition_ids = [p.id for p in petitions]
        await self.supabase.mark_processing(petition_ids)

        # Process each petition
        results: list[ProcessingResult] = []
        for petition in petitions:
            result = await self.process_single(petition)
            results.append(result)

        # Aggregate results
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        retryable = sum(1 for r in results if r.should_retry)

        logger.info(
            f"Batch complete: {successful} successful, {failed} failed "
            f"({retryable} retryable)"
        )

        return BatchResult(
            total=len(results),
            successful=successful,
            failed=failed,
            retryable=retryable,
            results=results,
        )
