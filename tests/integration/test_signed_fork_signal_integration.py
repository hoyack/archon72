"""Integration tests for Signed Fork Detection Signals (Story 3.8, FR84-FR85).

Tests the full integration of fork signal signing and rate limiting
using real components (stubs for HSM/external services).

Constitutional Constraints:
- FR84: Fork detection signals MUST be signed by detecting service
- FR85: Rate limit: 3 signals/hour/source prevents DoS spam
- CT-11: Silent failure destroys legitimacy
- CT-12: Witnessing creates accountability
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.services.fork_monitoring_service import (
    ForkHandleResult,
    ForkMonitoringService,
)
from src.domain.events.fork_detected import ForkDetectedPayload
from src.domain.models.signed_fork_signal import SignedForkSignal
from src.infrastructure.stubs.fork_monitor_stub import ForkMonitorStub
from src.infrastructure.stubs.fork_signal_rate_limiter_stub import (
    ForkSignalRateLimiterStub,
)


class MockSigningService:
    """Mock signing service for integration tests."""

    def __init__(self) -> None:
        self.sign_call_count = 0
        self.verify_call_count = 0
        self._signatures: dict[bytes, str] = {}

    async def sign_fork_signal(
        self, signable_content: bytes
    ) -> tuple[str, str, int]:
        """Sign content and return signature."""
        self.sign_call_count += 1
        # Generate deterministic signature for content
        import hashlib

        sig_hash = hashlib.sha256(signable_content).hexdigest()[:32]
        signature = f"sig_{sig_hash}"
        self._signatures[signable_content] = signature
        return (signature, "test-key-001", 1)

    async def verify_fork_signal(
        self, signable_content: bytes, signature: str, key_id: str
    ) -> bool:
        """Verify signature."""
        self.verify_call_count += 1
        expected_sig = self._signatures.get(signable_content)
        return signature == expected_sig


class TestSignedForkSignalCreationIntegration:
    """Integration tests for signed fork signal creation (FR84)."""

    @pytest.fixture
    def fork_monitor_stub(self) -> ForkMonitorStub:
        """Create a ForkMonitorStub."""
        return ForkMonitorStub(monitoring_interval_seconds=1)

    @pytest.fixture
    def signing_service(self) -> MockSigningService:
        """Create a mock signing service."""
        return MockSigningService()

    @pytest.fixture
    def rate_limiter(self) -> ForkSignalRateLimiterStub:
        """Create a rate limiter stub."""
        return ForkSignalRateLimiterStub()

    @pytest.fixture
    def on_fork_detected(self) -> AsyncMock:
        """Create a mock callback."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        fork_monitor_stub: ForkMonitorStub,
        on_fork_detected: AsyncMock,
        signing_service: MockSigningService,
        rate_limiter: ForkSignalRateLimiterStub,
    ) -> ForkMonitoringService:
        """Create service with all components."""
        return ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=on_fork_detected,
            service_id="integration-test",
            signing_service=signing_service,
            rate_limiter=rate_limiter,
        )

    @pytest.mark.asyncio
    async def test_end_to_end_signed_signal_creation(
        self,
        service: ForkMonitoringService,
        signing_service: MockSigningService,
    ) -> None:
        """Should create and sign fork signal end-to-end (FR84)."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="integration-test",
        )

        signed_signal = await service.create_signed_fork_signal(fork)

        # Verify signal structure
        assert isinstance(signed_signal, SignedForkSignal)
        assert signed_signal.fork_payload == fork
        assert signed_signal.signing_key_id == "test-key-001"
        assert signed_signal.sig_alg_version == 1
        assert signed_signal.signature.startswith("sig_")

        # Verify signing was called
        assert signing_service.sign_call_count == 1

    @pytest.mark.asyncio
    async def test_signal_roundtrip_verification(
        self,
        service: ForkMonitoringService,
        signing_service: MockSigningService,
    ) -> None:
        """Should verify signal created by same service (FR84, AC2)."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="integration-test",
        )

        # Create signed signal
        signed_signal = await service.create_signed_fork_signal(fork)

        # Verify same signal
        is_valid = await service.validate_fork_signal(signed_signal)

        assert is_valid is True
        assert signing_service.verify_call_count == 1

    @pytest.mark.asyncio
    async def test_tampered_signal_fails_verification(
        self,
        service: ForkMonitoringService,
        signing_service: MockSigningService,
    ) -> None:
        """Should reject signal with tampered signature (FR84)."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="integration-test",
        )

        # Create signed signal then tamper
        original_signal = await service.create_signed_fork_signal(fork)
        tampered_signal = SignedForkSignal(
            fork_payload=fork,
            signature="tampered_signature",  # Invalid signature
            signing_key_id=original_signal.signing_key_id,
            sig_alg_version=original_signal.sig_alg_version,
        )

        # Verification should fail
        is_valid = await service.validate_fork_signal(tampered_signal)

        assert is_valid is False


class TestRateLimitingIntegration:
    """Integration tests for fork signal rate limiting (FR85)."""

    @pytest.fixture
    def fork_monitor_stub(self) -> ForkMonitorStub:
        """Create a ForkMonitorStub."""
        return ForkMonitorStub(monitoring_interval_seconds=1)

    @pytest.fixture
    def signing_service(self) -> MockSigningService:
        """Create a mock signing service."""
        return MockSigningService()

    @pytest.fixture
    def rate_limiter(self) -> ForkSignalRateLimiterStub:
        """Create a rate limiter stub with default 3/hour limit."""
        return ForkSignalRateLimiterStub()

    @pytest.fixture
    def on_fork_detected(self) -> AsyncMock:
        """Create a mock callback."""
        return AsyncMock()

    @pytest.fixture
    def service(
        self,
        fork_monitor_stub: ForkMonitorStub,
        on_fork_detected: AsyncMock,
        signing_service: MockSigningService,
        rate_limiter: ForkSignalRateLimiterStub,
    ) -> ForkMonitoringService:
        """Create service with all components."""
        return ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=on_fork_detected,
            service_id="rate-limit-test",
            signing_service=signing_service,
            rate_limiter=rate_limiter,
        )

    @pytest.mark.asyncio
    async def test_allows_signals_up_to_threshold(
        self,
        service: ForkMonitoringService,
        signing_service: MockSigningService,
    ) -> None:
        """Should allow 3 signals per hour (FR85 threshold)."""
        results: list[ForkHandleResult] = []

        # Send 3 signals (within limit)
        for i in range(3):
            fork = ForkDetectedPayload(
                conflicting_event_ids=(uuid4(), uuid4()),
                prev_hash=f"{i:064x}",
                content_hashes=("b" * 64, "c" * 64),
                detection_timestamp=datetime.now(timezone.utc),
                detecting_service_id="rate-limit-test",
            )
            result = await service.handle_fork_with_rate_limit(fork)
            results.append(result)

        # All 3 should succeed
        for result in results:
            assert result.rate_limited is False
            assert result.signed_signal is not None

        assert signing_service.sign_call_count == 3

    @pytest.mark.asyncio
    async def test_blocks_fourth_signal(
        self,
        service: ForkMonitoringService,
        signing_service: MockSigningService,
    ) -> None:
        """Should block 4th signal in the hour (FR85)."""
        # Send 3 signals (fill limit)
        for i in range(3):
            fork = ForkDetectedPayload(
                conflicting_event_ids=(uuid4(), uuid4()),
                prev_hash=f"{i:064x}",
                content_hashes=("b" * 64, "c" * 64),
                detection_timestamp=datetime.now(timezone.utc),
                detecting_service_id="rate-limit-test",
            )
            await service.handle_fork_with_rate_limit(fork)

        # 4th signal should be blocked
        fork4 = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="3" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="rate-limit-test",
        )
        result = await service.handle_fork_with_rate_limit(fork4)

        assert result.rate_limited is True
        assert result.signed_signal is None
        # Only 3 signatures should have been created
        assert signing_service.sign_call_count == 3

    @pytest.mark.asyncio
    async def test_different_sources_tracked_independently(
        self,
        service: ForkMonitoringService,
        rate_limiter: ForkSignalRateLimiterStub,
    ) -> None:
        """Should track rate limits per source independently (FR85)."""
        # Fill up rate-limit-test's limit
        for i in range(3):
            fork = ForkDetectedPayload(
                conflicting_event_ids=(uuid4(), uuid4()),
                prev_hash=f"{i:064x}",
                content_hashes=("b" * 64, "c" * 64),
                detection_timestamp=datetime.now(timezone.utc),
                detecting_service_id="rate-limit-test",
            )
            await service.handle_fork_with_rate_limit(fork)

        # other-service should still be allowed
        other_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="d" * 64,
            content_hashes=("e" * 64, "f" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="other-service",
        )
        result = await service.handle_fork_with_rate_limit(other_fork)

        assert result.rate_limited is False
        assert result.signed_signal is not None

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(
        self,
        service: ForkMonitoringService,
        rate_limiter: ForkSignalRateLimiterStub,
    ) -> None:
        """Should allow signals after window expires (FR85)."""
        # Fill up limit
        for i in range(3):
            fork = ForkDetectedPayload(
                conflicting_event_ids=(uuid4(), uuid4()),
                prev_hash=f"{i:064x}",
                content_hashes=("b" * 64, "c" * 64),
                detection_timestamp=datetime.now(timezone.utc),
                detecting_service_id="rate-limit-test",
            )
            await service.handle_fork_with_rate_limit(fork)

        # Simulate window expiry by backdating signals
        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=2)
        rate_limiter._signal_counts["rate-limit-test"] = [old_time, old_time, old_time]

        # New signal should be allowed
        new_fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="new" + "0" * 61,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=now,
            detecting_service_id="rate-limit-test",
        )
        result = await service.handle_fork_with_rate_limit(new_fork)

        assert result.rate_limited is False
        assert result.signed_signal is not None


class TestMonitoringWithSigningIntegration:
    """Integration tests for monitoring loop with signing."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_creates_signed_signals(self) -> None:
        """Monitoring loop should integrate with signing (FR84)."""
        fork_monitor_stub = ForkMonitorStub(monitoring_interval_seconds=1)
        signing_service = MockSigningService()
        rate_limiter = ForkSignalRateLimiterStub()

        signed_signals: list[SignedForkSignal] = []

        async def on_fork_with_signing(fork: ForkDetectedPayload) -> None:
            """Callback that creates signed signal."""
            # In real integration, this would use the service
            signable = fork.signable_content()
            sig, key_id, alg_ver = await signing_service.sign_fork_signal(signable)
            signal = SignedForkSignal(
                fork_payload=fork,
                signature=sig,
                signing_key_id=key_id,
                sig_alg_version=alg_ver,
            )
            signed_signals.append(signal)

        service = ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=on_fork_with_signing,
            service_id="monitoring-signing-test",
            signing_service=signing_service,
            rate_limiter=rate_limiter,
        )

        # Inject a fork
        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="monitoring-signing-test",
        )
        fork_monitor_stub.inject_fork(fork)

        # Start monitoring
        await service.start_monitoring()
        await asyncio.sleep(0.15)  # Let it detect
        await service.stop_monitoring()

        # Should have created a signed signal
        assert len(signed_signals) >= 1
        assert all(isinstance(s, SignedForkSignal) for s in signed_signals)


class TestConstitutionalCompliance:
    """Tests verifying constitutional constraint compliance."""

    @pytest.mark.asyncio
    async def test_fr84_signals_are_always_signed(self) -> None:
        """FR84: All fork signals MUST be signed."""
        fork_monitor_stub = ForkMonitorStub()
        signing_service = MockSigningService()
        rate_limiter = ForkSignalRateLimiterStub()
        on_fork = AsyncMock()

        service = ForkMonitoringService(
            fork_monitor=fork_monitor_stub,
            on_fork_detected=on_fork,
            service_id="fr84-test",
            signing_service=signing_service,
            rate_limiter=rate_limiter,
        )

        fork = ForkDetectedPayload(
            conflicting_event_ids=(uuid4(), uuid4()),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime.now(timezone.utc),
            detecting_service_id="fr84-test",
        )

        signal = await service.create_signed_fork_signal(fork)

        # FR84: Signature MUST be present
        assert signal.signature is not None
        assert len(signal.signature) > 0

        # FR84: Key ID MUST be present (for verification)
        assert signal.signing_key_id is not None
        assert len(signal.signing_key_id) > 0

    @pytest.mark.asyncio
    async def test_fr85_rate_limit_threshold_is_3(self) -> None:
        """FR85: Rate limit threshold MUST be 3 signals per hour."""
        from src.application.ports.fork_signal_rate_limiter import (
            ForkSignalRateLimiterPort,
        )

        # Verify constant value
        assert ForkSignalRateLimiterPort.RATE_LIMIT_THRESHOLD == 3
        assert ForkSignalRateLimiterPort.RATE_LIMIT_WINDOW_HOURS == 1

    @pytest.mark.asyncio
    async def test_ct12_signable_content_deterministic(self) -> None:
        """CT-12: Signable content MUST be deterministic for accountability."""
        fork = ForkDetectedPayload(
            conflicting_event_ids=(
                uuid4(),
                uuid4(),
            ),
            prev_hash="a" * 64,
            content_hashes=("b" * 64, "c" * 64),
            detection_timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            detecting_service_id="ct12-test",
        )

        # Multiple calls should return identical bytes
        content1 = fork.signable_content()
        content2 = fork.signable_content()
        content3 = fork.signable_content()

        assert content1 == content2 == content3
