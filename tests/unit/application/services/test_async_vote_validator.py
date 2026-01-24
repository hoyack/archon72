import pytest

from src.application.services.async_vote_validator import (
    AdjudicationResult,
    AsyncVoteValidator,
    DeliberatorResult,
    ReconciliationTimeoutError,
    VoteValidationJob,
    WitnessRuling,
)
from src.domain.models.conclave import VoteChoice


class StubOrchestrator:
    async def execute_validation_task(
        self, task_type, validator_archon_id, vote_payload
    ):
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
            "final_vote": "NAY",
            "retort": True,
            "retort_reason": "no_consensus",
            "witness_statement": "retort issued",
        }


def make_job(optimistic_choice: VoteChoice = VoteChoice.ABSTAIN):
    return VoteValidationJob(
        vote_id="vote-1",
        session_id="session-1",
        motion_id="motion-1",
        archon_id="archon-1",
        archon_name="Archon One",
        optimistic_choice=optimistic_choice,
        vote_payload={"raw_content": "AYE"},
    )


def make_result(choice: VoteChoice):
    return DeliberatorResult(
        deliberator_type="text_analysis",
        validator_archon_id="validator-1",
        vote_choice=choice,
        confidence=0.8,
        raw_response="",
        parse_success=True,
        latency_ms=10,
    )


def make_result_missing_choice():
    return DeliberatorResult(
        deliberator_type="text_analysis",
        validator_archon_id="validator-1",
        vote_choice=None,
        confidence=0.0,
        raw_response="",
        parse_success=False,
        latency_ms=10,
        error="parse_failure",
    )


def test_parse_vote_choice():
    validator = AsyncVoteValidator(
        voting_concurrency=2,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )

    assert validator._parse_vote_choice("AYE") == VoteChoice.AYE
    assert validator._parse_vote_choice("yes") == VoteChoice.AYE
    assert validator._parse_vote_choice("NAY") == VoteChoice.NAY
    assert validator._parse_vote_choice("against") == VoteChoice.NAY
    assert validator._parse_vote_choice("abstain") == VoteChoice.ABSTAIN


@pytest.mark.asyncio
async def test_witness_adjudicate_unanimous():
    validator = AsyncVoteValidator(
        voting_concurrency=2,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )
    job = make_job()
    job.deliberator_results = {
        "text_analysis": make_result(VoteChoice.AYE),
        "json_validation": make_result(VoteChoice.AYE),
        "witness_confirm": make_result(VoteChoice.AYE),
    }

    result = await validator._witness_adjudicate(job)
    assert isinstance(result, AdjudicationResult)
    assert result.consensus is True
    assert result.final_vote == VoteChoice.AYE
    assert result.ruling == WitnessRuling.CONFIRMED


@pytest.mark.asyncio
async def test_witness_adjudicate_witness_dissent_retorts():
    validator = AsyncVoteValidator(
        voting_concurrency=2,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )
    job = make_job()
    job.deliberator_results = {
        "text_analysis": make_result(VoteChoice.AYE),
        "json_validation": make_result(VoteChoice.AYE),
        "witness_confirm": make_result(VoteChoice.NAY),
    }

    result = await validator._witness_adjudicate(job)
    assert result.consensus is True
    assert result.final_vote == VoteChoice.AYE
    assert result.ruling == WitnessRuling.RETORT
    assert result.retort_reason == "witness_dissent"


@pytest.mark.asyncio
async def test_witness_adjudicate_no_secretary_consensus_preserves_optimistic():
    validator = AsyncVoteValidator(
        voting_concurrency=2,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )
    job = make_job(optimistic_choice=VoteChoice.NAY)
    job.deliberator_results = {
        "text_analysis": make_result(VoteChoice.AYE),
        "json_validation": make_result(VoteChoice.NAY),
        "witness_confirm": make_result(VoteChoice.ABSTAIN),
    }

    result = await validator._witness_adjudicate(job)
    assert result.ruling == WitnessRuling.RETORT
    assert result.final_vote == VoteChoice.NAY
    assert result.retort_reason == "no_secretary_consensus"


@pytest.mark.asyncio
async def test_witness_adjudicate_parse_failures_do_not_force_abstain():
    validator = AsyncVoteValidator(
        voting_concurrency=2,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )
    job = make_job(optimistic_choice=VoteChoice.NAY)
    job.deliberator_results = {
        "text_analysis": make_result_missing_choice(),
        "json_validation": make_result_missing_choice(),
        "witness_confirm": make_result_missing_choice(),
    }

    result = await validator._witness_adjudicate(job)
    assert result.ruling == WitnessRuling.RETORT
    assert result.final_vote == VoteChoice.NAY


@pytest.mark.asyncio
async def test_drain_timeout_raises():
    validator = AsyncVoteValidator(
        voting_concurrency=1,
        secretary_text_id="s1",
        secretary_json_id="s2",
        witness_id="w1",
        orchestrator=StubOrchestrator(),
    )
    job = make_job()
    validator.pending_jobs[job.vote_id] = job

    with pytest.raises(ReconciliationTimeoutError):
        await validator.drain(timeout_seconds=0.01)
