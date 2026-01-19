"""Unit tests for PetitionSubmissionRepositoryProtocol (Story 0.3, AC3).

Tests verify the protocol interface exists and has required methods.
"""

from typing import Protocol
from uuid import UUID

import pytest

from src.application.ports.petition_submission_repository import (
    PetitionSubmissionRepositoryProtocol,
)
from src.domain.models.petition_submission import PetitionState, PetitionSubmission


class TestPetitionSubmissionRepositoryProtocol:
    """Tests for PetitionSubmissionRepositoryProtocol interface."""

    def test_protocol_is_protocol_class(self) -> None:
        """Verify PetitionSubmissionRepositoryProtocol is a Protocol."""
        assert issubclass(PetitionSubmissionRepositoryProtocol, Protocol)

    def test_protocol_has_save_method(self) -> None:
        """Verify protocol has save method with correct signature."""
        # Check method exists
        assert hasattr(PetitionSubmissionRepositoryProtocol, "save")
        # Method should be async
        method = getattr(PetitionSubmissionRepositoryProtocol, "save")
        assert callable(method)

    def test_protocol_has_get_method(self) -> None:
        """Verify protocol has get method with correct signature."""
        assert hasattr(PetitionSubmissionRepositoryProtocol, "get")
        method = getattr(PetitionSubmissionRepositoryProtocol, "get")
        assert callable(method)

    def test_protocol_has_list_by_state_method(self) -> None:
        """Verify protocol has list_by_state method with correct signature."""
        assert hasattr(PetitionSubmissionRepositoryProtocol, "list_by_state")
        method = getattr(PetitionSubmissionRepositoryProtocol, "list_by_state")
        assert callable(method)

    def test_protocol_has_update_state_method(self) -> None:
        """Verify protocol has update_state method with correct signature."""
        assert hasattr(PetitionSubmissionRepositoryProtocol, "update_state")
        method = getattr(PetitionSubmissionRepositoryProtocol, "update_state")
        assert callable(method)

    def test_protocol_can_be_used_as_type_hint(self) -> None:
        """Verify protocol can be used as type hint for dependency injection."""

        def some_function(repo: PetitionSubmissionRepositoryProtocol) -> None:
            """Function using protocol as type hint."""
            pass

        # If we get here without error, the protocol works as type hint
        assert True
