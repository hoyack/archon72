"""Bootstrap wiring for startup services."""

from __future__ import annotations

from src.application.services.configuration_floor_enforcement_service import (
    ConfigurationFloorEnforcementService,
)
from src.application.services.pre_operational_verification_service import (
    PreOperationalVerificationService,
)
from src.infrastructure.stubs.checkpoint_repository_stub import (
    CheckpointRepositoryStub,
)
from src.infrastructure.stubs.event_replicator_stub import EventReplicatorStub
from src.infrastructure.stubs.halt_checker_stub import HaltCheckerStub
from src.infrastructure.stubs.halt_trigger_stub import HaltTriggerStub
from src.infrastructure.stubs.hash_verifier_stub import HashVerifierStub
from src.infrastructure.stubs.keeper_key_registry_stub import KeeperKeyRegistryStub
from src.infrastructure.stubs.witness_pool_monitor_stub import (
    WitnessPoolMonitorStub,
)

_configuration_floor_service: ConfigurationFloorEnforcementService | None = None
_pre_operational_service: PreOperationalVerificationService | None = None


def get_configuration_floor_enforcement_service() -> ConfigurationFloorEnforcementService:
    """Get configuration floor enforcement service with stub dependencies."""
    global _configuration_floor_service
    if _configuration_floor_service is None:
        _configuration_floor_service = ConfigurationFloorEnforcementService(
            halt_trigger=HaltTriggerStub()
        )
    return _configuration_floor_service


def get_pre_operational_verification_service() -> PreOperationalVerificationService:
    """Get pre-operational verification service with stub dependencies."""
    global _pre_operational_service
    if _pre_operational_service is None:
        _pre_operational_service = PreOperationalVerificationService(
            hash_verifier=HashVerifierStub(),
            witness_pool_monitor=WitnessPoolMonitorStub(),
            keeper_key_registry=KeeperKeyRegistryStub(),
            checkpoint_repository=CheckpointRepositoryStub(),
            halt_checker=HaltCheckerStub(),
            event_replicator=EventReplicatorStub(),
        )
    return _pre_operational_service


def set_configuration_floor_enforcement_service(
    service: ConfigurationFloorEnforcementService,
) -> None:
    """Set custom configuration floor enforcement service."""
    global _configuration_floor_service
    _configuration_floor_service = service


def set_pre_operational_verification_service(
    service: PreOperationalVerificationService,
) -> None:
    """Set custom pre-operational verification service."""
    global _pre_operational_service
    _pre_operational_service = service


def reset_startup_services() -> None:
    """Reset startup service singletons."""
    global _configuration_floor_service
    global _pre_operational_service
    _configuration_floor_service = None
    _pre_operational_service = None
