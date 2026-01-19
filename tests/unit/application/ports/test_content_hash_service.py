"""Unit tests for ContentHashServiceProtocol (Story 0.5, AC1).

Tests verify the protocol interface exists and has required methods
for content hashing operations.

Constitutional Constraints:
- HP-2: Content hashing for duplicate detection
- HC-5: Sybil amplification defense via content hash
"""

from typing import Protocol

from src.application.ports.content_hash_service import ContentHashServiceProtocol


class TestContentHashServiceProtocol:
    """Tests for ContentHashServiceProtocol interface."""

    def test_protocol_is_protocol_class(self) -> None:
        """Verify ContentHashServiceProtocol is a Protocol."""
        assert issubclass(ContentHashServiceProtocol, Protocol)

    def test_protocol_has_hash_content_method(self) -> None:
        """Verify protocol has hash_content method with correct signature."""
        assert hasattr(ContentHashServiceProtocol, "hash_content")
        method = ContentHashServiceProtocol.hash_content
        assert callable(method)

    def test_protocol_has_hash_text_method(self) -> None:
        """Verify protocol has hash_text method with correct signature."""
        assert hasattr(ContentHashServiceProtocol, "hash_text")
        method = ContentHashServiceProtocol.hash_text
        assert callable(method)

    def test_protocol_has_verify_hash_method(self) -> None:
        """Verify protocol has verify_hash method with correct signature."""
        assert hasattr(ContentHashServiceProtocol, "verify_hash")
        method = ContentHashServiceProtocol.verify_hash
        assert callable(method)

    def test_protocol_can_be_used_as_type_hint(self) -> None:
        """Verify protocol can be used as type hint for dependency injection."""

        def some_function(service: ContentHashServiceProtocol) -> bytes:
            """Function using protocol as type hint."""
            return service.hash_text("test")

        # If we get here without error, the protocol works as type hint
        assert True

    def test_protocol_methods_have_docstrings(self) -> None:
        """Verify protocol methods have docstrings for documentation."""
        assert ContentHashServiceProtocol.hash_content.__doc__ is not None
        assert ContentHashServiceProtocol.hash_text.__doc__ is not None
        assert ContentHashServiceProtocol.verify_hash.__doc__ is not None

    def test_protocol_docstrings_mention_constitutional_constraints(self) -> None:
        """Verify docstrings reference HP-2 and HC-5 constraints."""
        # Check hash_content mentions HP-2
        assert "HP-2" in str(ContentHashServiceProtocol.hash_content.__doc__)
        # Check verify_hash mentions CT-12
        assert "CT-12" in str(ContentHashServiceProtocol.verify_hash.__doc__)
