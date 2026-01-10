"""Separation Validator Stub - FR52 Operational-Constitutional Separation.

This stub implements the SeparationValidatorPort with hardcoded classification
of constitutional and operational data types based on the Archon 72 codebase.

Constitutional Constraint (FR52):
- Operational metrics (uptime, latency, errors) NEVER enter event store
- Constitutional events (votes, deliberations, halts) NEVER go to ops storage
"""

from src.application.ports.separation_validator import (
    DataClassification,
    SeparationValidatorPort,
)


class SeparationValidatorStub(SeparationValidatorPort):
    """Stub implementation of SeparationValidatorPort.

    Provides hardcoded classification for constitutional and operational
    data types based on the existing Archon 72 event types.
    """

    # Constitutional event types (ALLOWED in event store)
    # Gathered from src/domain/events/*.py
    CONSTITUTIONAL_TYPES: frozenset[str] = frozenset(
        {
            # Event base types
            "event",
            # Deliberation events
            "deliberation_output",
            "deliberation_started",
            "deliberation_completed",
            "output_view",
            "procedural_record",
            # Vote events
            "vote_cast",
            "vote_tallied",
            "unanimous_vote",
            # Agent events
            "agent_unresponsive",
            "certified_result",
            "collective_output",
            "context_bundle_created",
            # Halt and fork events
            "halt_triggered",
            "halt_cleared",
            "fork_detected",
            "fork_signal_rate_limit",
            "recovery_waiting_period_started",
            "recovery_completed",
            "sequence_gap_detected",
            # Rollback events
            "rollback_target_selected",
            "rollback_completed",
            # Override events
            "override_event",
            "override_applied",
            "override_expired",
            "override_abuse",
            # Constitutional crisis events
            "constitutional_crisis",
            "anti_success_alert",
            "governance_review_required",
            # Witness events
            "witness_selection",
            "witness_anomaly",
            # Key generation events
            "key_generation_ceremony",
            "keeper_availability",
            "independence_attestation",
            # Breach events
            "breach",
            "breach_declared",
            "escalation",
            # Cessation events
            "cessation",
            "cessation_executed",
            "cessation_agenda",
            "cessation_deliberation",
            "deliberation_recording_failed",
            # Threshold events
            "threshold",
            "threshold_updated",
            # Amendment events
            "amendment",
            "amendment_proposed",
            "amendment_visible",
            # Collusion events
            "collusion",
            "collusion_suspected",
            # Hash verification events
            "hash_verification",
            "hash_chain_verified",
            # Topic events
            "topic_rate_limit",
            "topic_diversity_alert",
            "topic_manipulation",
            # Seed validation events
            "seed_validation",
            # Configuration events
            "configuration_floor",
            # Petition events
            "petition",
            "petition_submitted",
            "petition_closed",
            # Trigger events
            "trigger_condition_changed",
            # Integrity events
            "integrity_case",
            # Signing events
            "signing",
        }
    )

    # Operational data types (NEVER in event store, go to Prometheus/ops storage)
    OPERATIONAL_TYPES: frozenset[str] = frozenset(
        {
            # Metrics (Story 8.1)
            "uptime_recorded",
            "latency_measured",
            "error_logged",
            "error_rate",
            "request_counted",
            "request_duration",
            # Service lifecycle
            "service_start",
            "service_stop",
            "service_restart",
            # Health checks
            "health_check",
            "health_status",
            "readiness_check",
            "liveness_check",
            # Resource metrics
            "memory_usage",
            "cpu_usage",
            "disk_usage",
            "connection_count",
            # Performance metrics
            "response_time",
            "throughput",
            "queue_depth",
            # Debugging/logging
            "debug_log",
            "trace_log",
            "info_log",
            "warning_log",
        }
    )

    def classify_data(self, data_type: str) -> DataClassification:
        """Classify a data type as constitutional, operational, or unknown.

        Args:
            data_type: The type identifier for the data.

        Returns:
            DataClassification indicating where this data should be stored.
        """
        if not data_type:
            return DataClassification.UNKNOWN

        if data_type in self.CONSTITUTIONAL_TYPES:
            return DataClassification.CONSTITUTIONAL

        if data_type in self.OPERATIONAL_TYPES:
            return DataClassification.OPERATIONAL

        return DataClassification.UNKNOWN

    def is_constitutional(self, data_type: str) -> bool:
        """Check if a data type is constitutional (event store eligible).

        Args:
            data_type: The type identifier to check.

        Returns:
            True if the data type belongs in the constitutional event store.
        """
        return self.classify_data(data_type) == DataClassification.CONSTITUTIONAL

    def is_operational(self, data_type: str) -> bool:
        """Check if a data type is operational (Prometheus/ops storage).

        Args:
            data_type: The type identifier to check.

        Returns:
            True if the data type belongs in operational storage.
        """
        return self.classify_data(data_type) == DataClassification.OPERATIONAL

    def get_allowed_event_types(self) -> set[str]:
        """Get all constitutional event types allowed in event store.

        Returns:
            Set of event type strings that are permitted in the event store.
        """
        return set(self.CONSTITUTIONAL_TYPES)
