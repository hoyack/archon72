"""Unit tests for EntropySourceStub.

Tests the stub implementation of EntropySourceProtocol.
"""

import warnings

import pytest

from src.domain.errors.witness_selection import EntropyUnavailableError
from src.infrastructure.stubs.entropy_source_stub import (
    DEV_MODE_WARNING,
    EntropySourceStub,
    SecureEntropySourceStub,
)


class TestEntropySourceStub:
    """Tests for EntropySourceStub."""

    def test_dev_mode_warning_on_init(self) -> None:
        """Stub emits DEV MODE warning on initialization."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = EntropySourceStub()

            assert len(w) == 1
            assert DEV_MODE_WARNING in str(w[0].message)

    def test_can_suppress_warning(self) -> None:
        """Warning can be suppressed."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = EntropySourceStub(warn_on_init=False)

            assert len(w) == 0

    @pytest.mark.asyncio
    async def test_get_entropy_returns_bytes(self) -> None:
        """get_entropy returns bytes."""
        stub = EntropySourceStub(warn_on_init=False)

        entropy = await stub.get_entropy()

        assert isinstance(entropy, bytes)
        assert len(entropy) >= 32

    @pytest.mark.asyncio
    async def test_get_entropy_returns_configured_value(self) -> None:
        """get_entropy returns configured entropy."""
        stub = EntropySourceStub(warn_on_init=False)
        custom_entropy = b"custom_entropy_value_32_bytes!!"
        stub.set_entropy(custom_entropy)

        entropy = await stub.get_entropy()

        assert entropy == custom_entropy

    @pytest.mark.asyncio
    async def test_set_entropy_from_seed(self) -> None:
        """set_entropy_from_seed creates deterministic entropy."""
        stub = EntropySourceStub(warn_on_init=False)

        stub.set_entropy_from_seed("test-seed")
        entropy1 = await stub.get_entropy()

        stub.set_entropy_from_seed("test-seed")
        entropy2 = await stub.get_entropy()

        assert entropy1 == entropy2

    @pytest.mark.asyncio
    async def test_set_failure_causes_error(self) -> None:
        """set_failure causes get_entropy to raise."""
        stub = EntropySourceStub(warn_on_init=False)
        stub.set_failure(True, reason="Test failure")

        with pytest.raises(EntropyUnavailableError) as exc_info:
            await stub.get_entropy()

        assert "Test failure" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_source_identifier(self) -> None:
        """get_source_identifier returns stub identifier."""
        stub = EntropySourceStub(warn_on_init=False)

        identifier = await stub.get_source_identifier()

        assert identifier == "dev-stub"

    @pytest.mark.asyncio
    async def test_is_available_default_true(self) -> None:
        """is_available returns True by default."""
        stub = EntropySourceStub(warn_on_init=False)

        available = await stub.is_available()

        assert available is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_failure_set(self) -> None:
        """is_available returns False when failure is configured."""
        stub = EntropySourceStub(warn_on_init=False)
        stub.set_failure(True)

        available = await stub.is_available()

        assert available is False

    @pytest.mark.asyncio
    async def test_set_availability(self) -> None:
        """set_availability controls is_available result."""
        stub = EntropySourceStub(warn_on_init=False)
        stub.set_availability(False)

        available = await stub.is_available()

        assert available is False

    def test_reset_restores_defaults(self) -> None:
        """reset restores stub to default state."""
        stub = EntropySourceStub(warn_on_init=False)
        stub.set_entropy(b"custom")
        stub.set_failure(True)

        stub.reset()

        assert not stub._should_fail
        assert stub._is_available

    def test_current_entropy_property(self) -> None:
        """current_entropy property returns configured entropy."""
        stub = EntropySourceStub(warn_on_init=False)
        custom = b"custom_entropy_for_test_32_bytes"
        stub.set_entropy(custom)

        assert stub.current_entropy == custom

    def test_short_entropy_warning(self) -> None:
        """Setting short entropy emits warning."""
        stub = EntropySourceStub(warn_on_init=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            stub.set_entropy(b"short")

            assert len(w) == 1
            assert "32 bytes" in str(w[0].message)


class TestSecureEntropySourceStub:
    """Tests for SecureEntropySourceStub."""

    def test_dev_mode_warning_on_init(self) -> None:
        """Stub emits DEV MODE warning on initialization."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = SecureEntropySourceStub()

            assert len(w) == 1
            assert "DEV MODE" in str(w[0].message)

    @pytest.mark.asyncio
    async def test_get_entropy_returns_32_bytes(self) -> None:
        """get_entropy returns 32 bytes from os.urandom."""
        stub = SecureEntropySourceStub(warn_on_init=False)

        entropy = await stub.get_entropy()

        assert len(entropy) == 32

    @pytest.mark.asyncio
    async def test_get_entropy_returns_different_values(self) -> None:
        """get_entropy returns different values each call."""
        stub = SecureEntropySourceStub(warn_on_init=False)

        entropy1 = await stub.get_entropy()
        entropy2 = await stub.get_entropy()

        # Very unlikely to be the same
        assert entropy1 != entropy2

    @pytest.mark.asyncio
    async def test_get_source_identifier(self) -> None:
        """get_source_identifier returns secure stub identifier."""
        stub = SecureEntropySourceStub(warn_on_init=False)

        identifier = await stub.get_source_identifier()

        assert identifier == "dev-secure-stub"

    @pytest.mark.asyncio
    async def test_set_failure_causes_error(self) -> None:
        """set_failure causes get_entropy to raise."""
        stub = SecureEntropySourceStub(warn_on_init=False)
        stub.set_failure(True, reason="Test failure")

        with pytest.raises(EntropyUnavailableError):
            await stub.get_entropy()
