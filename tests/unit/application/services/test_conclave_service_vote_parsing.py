"""Unit tests for ConclaveService vote parsing.

These tests cover robustness against differing vote formats:
- Conclave prompt: "I VOTE AYE|NAY" / "I ABSTAIN"
- Archon system prompts (e.g., Kings): "Vote: FOR|NAY|ABSTAIN"
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.services.conclave_service import ConclaveConfig, ConclaveService
from src.domain.models.conclave import VoteChoice


@pytest.fixture
def service(tmp_path) -> ConclaveService:
    """Create a ConclaveService instance suitable for unit testing helpers."""
    orchestrator = MagicMock()
    config = ConclaveConfig(
        checkpoint_dir=tmp_path / "checkpoints",
        output_dir=tmp_path / "output",
    )
    return ConclaveService(orchestrator=orchestrator, archon_profiles=[], config=config)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"choice":"AYE"}\n', VoteChoice.AYE),
        ('{"choice":"NAY"}\n', VoteChoice.NAY),
        ('{"choice":"ABSTAIN"}\n', VoteChoice.ABSTAIN),
        ('{"choice":"AYE"}\n\nReason...\n', VoteChoice.AYE),
        ("Vote: FOR\n\nReason...\n", VoteChoice.AYE),
        ("Vote: NAY\n\nReason...\n", VoteChoice.NAY),
        ("Vote: ABSTAIN\n\nReason...\n", VoteChoice.ABSTAIN),
        ("I VOTE AYE\n", VoteChoice.AYE),
        ("I VOTE NAY\n", VoteChoice.NAY),
        ("I ABSTAIN\n", VoteChoice.ABSTAIN),
        ("VOTE: I VOTE AYE\n", VoteChoice.AYE),
        ("vote nay\n", VoteChoice.NAY),
        ("- AYE\n", VoteChoice.AYE),
        ("**Vote: FOR**\n", VoteChoice.AYE),
        ("**I VOTE NAY.**\n", VoteChoice.NAY),
        ("No explicit vote here.\n", VoteChoice.ABSTAIN),
    ],
)
def test_parse_vote_accepts_common_formats(
    service: ConclaveService, content: str, expected: VoteChoice
) -> None:
    assert service._parse_vote(content) == expected
