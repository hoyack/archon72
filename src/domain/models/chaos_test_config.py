"""Chaos test configuration model for deliberation resilience testing.

Story 2B.8: Deliberation Chaos Testing (NFR-9.5)

This module defines configuration for chaos testing scenarios that validate
system resilience under various failure conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChaosScenario(Enum):
    """Enumeration of chaos test scenarios (Story 2B.8, NFR-9.5).

    Each scenario represents a specific failure mode to inject
    during deliberation testing.

    Attributes:
        ARCHON_TIMEOUT_MID_PHASE: One Archon stops responding during deliberation
        SERVICE_RESTART: Deliberation service killed and restarted
        DATABASE_CONNECTION_FAILURE: Database connection severed for configured duration
        CREWAI_API_DEGRADATION: Latency injected into CrewAI calls
        WITNESS_WRITE_FAILURE: Event writer becomes unavailable
        NETWORK_PARTITION: Network partition between components
    """

    ARCHON_TIMEOUT_MID_PHASE = "archon_timeout_mid_phase"
    SERVICE_RESTART = "service_restart"
    DATABASE_CONNECTION_FAILURE = "database_connection_failure"
    CREWAI_API_DEGRADATION = "crewai_api_degradation"
    WITNESS_WRITE_FAILURE = "witness_write_failure"
    NETWORK_PARTITION = "network_partition"


# Schema version for serialization compatibility
CHAOS_CONFIG_SCHEMA_VERSION = 1

# Validation bounds
MIN_INJECTION_DURATION_SECONDS = 1
MAX_INJECTION_DURATION_SECONDS = 300
MIN_RECOVERY_TIMEOUT_SECONDS = 1
MIN_LATENCY_INJECTION_MS = 0


@dataclass(frozen=True, eq=True)
class ChaosTestConfig:
    """Configuration for chaos testing deliberation systems (Story 2B.8, NFR-9.5).

    Defines the parameters for chaos test execution including scenario type,
    injection duration, and recovery expectations.

    Attributes:
        scenario: Type of chaos to inject.
        injection_duration_seconds: How long to inject the fault (default: 30).
        injection_probability: Probability of fault occurring (default: 1.0).
        affected_components: List of components to target.
        recovery_timeout_seconds: How long to wait for recovery (default: 60).
        enable_audit_logging: Whether to capture detailed chaos logs (default: True).
        latency_injection_ms: For API_DEGRADATION, the latency to inject (default: 500).

    Raises:
        ValueError: If any configuration value is invalid.

    Example:
        >>> config = ChaosTestConfig(
        ...     scenario=ChaosScenario.ARCHON_TIMEOUT_MID_PHASE,
        ...     injection_duration_seconds=10,
        ... )
        >>> config.scenario
        <ChaosScenario.ARCHON_TIMEOUT_MID_PHASE: 'archon_timeout_mid_phase'>
    """

    scenario: ChaosScenario
    injection_duration_seconds: int = field(default=30)
    injection_probability: float = field(default=1.0)
    affected_components: tuple[str, ...] = field(default_factory=tuple)
    recovery_timeout_seconds: int = field(default=60)
    enable_audit_logging: bool = field(default=True)
    latency_injection_ms: int = field(default=500)

    def __post_init__(self) -> None:
        """Validate configuration invariants."""
        if self.injection_duration_seconds < MIN_INJECTION_DURATION_SECONDS:
            raise ValueError(
                f"injection_duration_seconds must be >= {MIN_INJECTION_DURATION_SECONDS}, "
                f"got {self.injection_duration_seconds}"
            )
        if self.injection_duration_seconds > MAX_INJECTION_DURATION_SECONDS:
            raise ValueError(
                f"injection_duration_seconds must be <= {MAX_INJECTION_DURATION_SECONDS}, "
                f"got {self.injection_duration_seconds}"
            )
        if not 0.0 <= self.injection_probability <= 1.0:
            raise ValueError(
                f"injection_probability must be 0.0-1.0, got {self.injection_probability}"
            )
        if self.recovery_timeout_seconds < MIN_RECOVERY_TIMEOUT_SECONDS:
            raise ValueError(
                f"recovery_timeout_seconds must be >= {MIN_RECOVERY_TIMEOUT_SECONDS}, "
                f"got {self.recovery_timeout_seconds}"
            )
        if self.latency_injection_ms < MIN_LATENCY_INJECTION_MS:
            raise ValueError(
                f"latency_injection_ms must be >= {MIN_LATENCY_INJECTION_MS}, "
                f"got {self.latency_injection_ms}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "scenario": self.scenario.value,
            "injection_duration_seconds": self.injection_duration_seconds,
            "injection_probability": self.injection_probability,
            "affected_components": list(self.affected_components),
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "enable_audit_logging": self.enable_audit_logging,
            "latency_injection_ms": self.latency_injection_ms,
            "schema_version": CHAOS_CONFIG_SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChaosTestConfig:
        """Create instance from dictionary.

        Args:
            data: Dictionary with configuration values.

        Returns:
            New ChaosTestConfig instance.

        Raises:
            KeyError: If required keys are missing.
            ValueError: If values are invalid.
        """
        return cls(
            scenario=ChaosScenario(data["scenario"]),
            injection_duration_seconds=data.get("injection_duration_seconds", 30),
            injection_probability=data.get("injection_probability", 1.0),
            affected_components=tuple(data.get("affected_components", [])),
            recovery_timeout_seconds=data.get("recovery_timeout_seconds", 60),
            enable_audit_logging=data.get("enable_audit_logging", True),
            latency_injection_ms=data.get("latency_injection_ms", 500),
        )
