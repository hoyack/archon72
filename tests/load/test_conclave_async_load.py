import os
import time

import pytest

from src.application.services.async_vote_validator import AsyncVoteValidator
from src.domain.models.conclave import VoteChoice


class StubValidationOrchestrator:
    async def execute_validation_task(self, task_type, validator_archon_id, vote_payload):
        return {
            "vote_choice": "AYE",
            "confidence": 0.9,
            "raw_response": "AYE",
            "parse_success": True,
            "metadata": {"task_type": task_type},
        }

    async def execute_witness_adjudication(
        self,
        witness_archon_id,
        vote_payload,
        deliberator_results,
    ):
        return {
            "final_vote": "AYE",
            "retort": False,
            "retort_reason": None,
            "witness_statement": "confirmed",
        }


@pytest.mark.load
@pytest.mark.asyncio
async def test_conclave_async_load() -> None:
    """Load test the async validation pipeline with synthetic votes."""
    archons = int(os.environ.get("CONCLAVE_LOAD_ARCHONS", "72"))
    motions = int(os.environ.get("CONCLAVE_LOAD_MOTIONS", "64"))
    concurrency = int(os.environ.get("CONCLAVE_LOAD_CONCURRENCY", "8"))
    timeout = float(os.environ.get("CONCLAVE_LOAD_TIMEOUT", "300"))

    orchestrator = StubValidationOrchestrator()
    validator = AsyncVoteValidator(
        voting_concurrency=concurrency,
        secretary_text_id="secretary-text",
        secretary_json_id="secretary-json",
        witness_id="witness",
        orchestrator=orchestrator,
        kafka_publisher=None,
    )

    start = time.time()
    for motion_index in range(motions):
        for archon_index in range(archons):
            await validator.submit_vote(
                vote_id=f"vote-{motion_index}-{archon_index}",
                session_id="load-session",
                motion_id=f"motion-{motion_index}",
                archon_id=f"archon-{archon_index}",
                archon_name=f"Archon {archon_index}",
                optimistic_choice=VoteChoice.AYE,
                vote_payload={
                    "vote_id": f"vote-{motion_index}-{archon_index}",
                    "session_id": "load-session",
                    "motion_id": f"motion-{motion_index}",
                    "archon_id": f"archon-{archon_index}",
                    "archon_name": f"Archon {archon_index}",
                    "motion_title": f"Motion {motion_index}",
                    "motion_text": "Load test motion text",
                    "raw_content": "AYE",
                },
            )

    await validator.drain(timeout=timeout)

    duration = time.time() - start
    assert validator.total_completed == archons * motions
    assert duration <= timeout
