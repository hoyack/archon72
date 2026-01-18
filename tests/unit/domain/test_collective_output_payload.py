"""Unit tests for CollectiveOutputPayload and related types (Story 2.3, FR11).

Tests the domain event types for collective output irreducibility:
- AuthorType enum validation
- VoteCounts dataclass
- CollectiveOutputPayload frozen dataclass with FR11 constraints

Constitutional Constraints:
- FR11: Collective outputs attributed to Conclave, not individuals
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

from uuid import uuid4

import pytest


class TestAuthorType:
    """Tests for AuthorType enum."""

    def test_collective_value_exists(self) -> None:
        """AuthorType should have COLLECTIVE value."""
        from src.domain.events.collective_output import AuthorType

        assert AuthorType.COLLECTIVE is not None
        assert AuthorType.COLLECTIVE.value == "COLLECTIVE"

    def test_individual_value_exists(self) -> None:
        """AuthorType should have INDIVIDUAL value."""
        from src.domain.events.collective_output import AuthorType

        assert AuthorType.INDIVIDUAL is not None
        assert AuthorType.INDIVIDUAL.value == "INDIVIDUAL"

    def test_from_string_collective(self) -> None:
        """AuthorType should be creatable from string 'COLLECTIVE'."""
        from src.domain.events.collective_output import AuthorType

        assert AuthorType("COLLECTIVE") == AuthorType.COLLECTIVE

    def test_from_string_individual(self) -> None:
        """AuthorType should be creatable from string 'INDIVIDUAL'."""
        from src.domain.events.collective_output import AuthorType

        assert AuthorType("INDIVIDUAL") == AuthorType.INDIVIDUAL


class TestVoteCounts:
    """Tests for VoteCounts frozen dataclass."""

    def test_create_valid_vote_counts(self) -> None:
        """VoteCounts should accept valid non-negative counts."""
        from src.domain.events.collective_output import VoteCounts

        vc = VoteCounts(yes_count=50, no_count=20, abstain_count=2)
        assert vc.yes_count == 50
        assert vc.no_count == 20
        assert vc.abstain_count == 2

    def test_vote_counts_immutable(self) -> None:
        """VoteCounts should be frozen (immutable)."""
        from src.domain.events.collective_output import VoteCounts

        vc = VoteCounts(yes_count=10, no_count=5, abstain_count=0)
        with pytest.raises(AttributeError):
            vc.yes_count = 20  # type: ignore[misc]

    def test_vote_counts_total(self) -> None:
        """VoteCounts should provide total property."""
        from src.domain.events.collective_output import VoteCounts

        vc = VoteCounts(yes_count=36, no_count=30, abstain_count=6)
        assert vc.total == 72

    def test_vote_counts_negative_yes_rejected(self) -> None:
        """VoteCounts should reject negative yes_count."""
        from src.domain.events.collective_output import VoteCounts

        with pytest.raises(ValueError, match="yes_count must be non-negative"):
            VoteCounts(yes_count=-1, no_count=10, abstain_count=0)

    def test_vote_counts_negative_no_rejected(self) -> None:
        """VoteCounts should reject negative no_count."""
        from src.domain.events.collective_output import VoteCounts

        with pytest.raises(ValueError, match="no_count must be non-negative"):
            VoteCounts(yes_count=10, no_count=-5, abstain_count=0)

    def test_vote_counts_negative_abstain_rejected(self) -> None:
        """VoteCounts should reject negative abstain_count."""
        from src.domain.events.collective_output import VoteCounts

        with pytest.raises(ValueError, match="abstain_count must be non-negative"):
            VoteCounts(yes_count=10, no_count=5, abstain_count=-2)


class TestCollectiveOutputPayload:
    """Tests for CollectiveOutputPayload frozen dataclass (FR11)."""

    @pytest.fixture
    def valid_payload_kwargs(self) -> dict:
        """Valid kwargs for creating a CollectiveOutputPayload."""
        from src.domain.events.collective_output import AuthorType, VoteCounts

        return {
            "output_id": uuid4(),
            "author_type": AuthorType.COLLECTIVE,
            "contributing_agents": ("archon-1", "archon-2"),
            "content_hash": "a" * 64,
            "vote_counts": VoteCounts(yes_count=70, no_count=2, abstain_count=0),
            "dissent_percentage": 2.78,
            "unanimous": False,
            "linked_vote_event_ids": (uuid4(), uuid4()),
        }

    def test_create_valid_collective_output(self, valid_payload_kwargs: dict) -> None:
        """CollectiveOutputPayload should accept valid collective output."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        assert payload.output_id == valid_payload_kwargs["output_id"]
        assert payload.author_type.value == "COLLECTIVE"
        assert len(payload.contributing_agents) == 2

    def test_payload_is_frozen(self, valid_payload_kwargs: dict) -> None:
        """CollectiveOutputPayload should be frozen (immutable)."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        with pytest.raises(AttributeError):
            payload.unanimous = True  # type: ignore[misc]

    def test_single_agent_rejected_fr11(self, valid_payload_kwargs: dict) -> None:
        """FR11: Collective output requires multiple participants."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["contributing_agents"] = ("archon-1",)
        with pytest.raises(
            ValueError, match="FR11: Collective output requires multiple participants"
        ):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_zero_agents_rejected_fr11(self, valid_payload_kwargs: dict) -> None:
        """FR11: Collective output cannot have zero agents."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["contributing_agents"] = ()
        with pytest.raises(
            ValueError, match="FR11: Collective output requires multiple participants"
        ):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_72_agents_accepted(self, valid_payload_kwargs: dict) -> None:
        """Collective output should accept 72 agents (full Conclave)."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["contributing_agents"] = tuple(
            f"archon-{i}" for i in range(72)
        )
        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        assert len(payload.contributing_agents) == 72

    def test_invalid_content_hash_length(self, valid_payload_kwargs: dict) -> None:
        """Content hash must be 64 characters (SHA-256)."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["content_hash"] = "a" * 32  # Too short
        with pytest.raises(ValueError, match="content_hash must be 64 character"):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_invalid_content_hash_non_hex_characters(
        self, valid_payload_kwargs: dict
    ) -> None:
        """Content hash must contain only hexadecimal characters."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["content_hash"] = "z" * 64  # Invalid hex
        with pytest.raises(ValueError, match="hexadecimal characters"):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_valid_content_hash_uppercase_accepted(
        self, valid_payload_kwargs: dict
    ) -> None:
        """Content hash should accept uppercase hex characters."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["content_hash"] = "A" * 64  # Uppercase hex is valid
        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        assert payload.content_hash == "A" * 64

    def test_invalid_output_id_type(self, valid_payload_kwargs: dict) -> None:
        """output_id must be UUID."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["output_id"] = "not-a-uuid"
        with pytest.raises(TypeError, match="output_id must be UUID"):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_dissent_percentage_range(self, valid_payload_kwargs: dict) -> None:
        """Dissent percentage must be 0.0 to 100.0."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        # Valid edge cases
        valid_payload_kwargs["dissent_percentage"] = 0.0
        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        assert payload.dissent_percentage == 0.0

        valid_payload_kwargs["dissent_percentage"] = 100.0
        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        assert payload.dissent_percentage == 100.0

    def test_dissent_percentage_negative_rejected(
        self, valid_payload_kwargs: dict
    ) -> None:
        """Dissent percentage cannot be negative."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["dissent_percentage"] = -1.0
        with pytest.raises(ValueError, match="dissent_percentage must be between"):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_dissent_percentage_over_100_rejected(
        self, valid_payload_kwargs: dict
    ) -> None:
        """Dissent percentage cannot exceed 100."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        valid_payload_kwargs["dissent_percentage"] = 100.1
        with pytest.raises(ValueError, match="dissent_percentage must be between"):
            CollectiveOutputPayload(**valid_payload_kwargs)

    def test_to_dict_conversion(self, valid_payload_kwargs: dict) -> None:
        """CollectiveOutputPayload should convert to dict for JSON."""
        from src.domain.events.collective_output import CollectiveOutputPayload

        payload = CollectiveOutputPayload(**valid_payload_kwargs)
        d = payload.to_dict()
        assert "output_id" in d
        assert d["author_type"] == "COLLECTIVE"
        assert "contributing_agents" in d
        assert "vote_counts" in d
        assert "dissent_percentage" in d
        assert "unanimous" in d


class TestCollectiveOutputEventType:
    """Tests for COLLECTIVE_OUTPUT_EVENT_TYPE constant."""

    def test_event_type_constant_exists(self) -> None:
        """COLLECTIVE_OUTPUT_EVENT_TYPE should be defined."""
        from src.domain.events.collective_output import COLLECTIVE_OUTPUT_EVENT_TYPE

        assert COLLECTIVE_OUTPUT_EVENT_TYPE is not None

    def test_event_type_format(self) -> None:
        """Event type should follow lowercase.dot.notation."""
        from src.domain.events.collective_output import COLLECTIVE_OUTPUT_EVENT_TYPE

        assert COLLECTIVE_OUTPUT_EVENT_TYPE == "collective.output"
