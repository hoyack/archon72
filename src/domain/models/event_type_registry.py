"""Event Type Registry - FR52 Operational-Constitutional Separation.

This module provides a centralized source of truth for event types,
distinguishing between constitutional events (event store) and
operational metrics (Prometheus/operational storage).

Constitutional Constraint (FR52):
- Operational metrics NEVER enter event store
- Constitutional events NEVER go to operational storage
- This registry is the authoritative source for classification

Usage:
    from src.domain.models.event_type_registry import EventTypeRegistry

    # Check if a type is allowed in event store
    if EventTypeRegistry.is_valid_constitutional_type("deliberation_output"):
        # Safe to write to event store
        ...

    # Check if a type is operational
    if EventTypeRegistry.is_operational_type("uptime_recorded"):
        # Must use Prometheus, not event store
        ...
"""


class EventTypeRegistry:
    """Centralized registry of event and metric types.

    This class provides class-level constants and methods for classifying
    data types as constitutional or operational.

    Constitutional types (CONSTITUTIONAL_TYPES) are the ONLY types allowed
    in the constitutional event store. All other types must use operational
    storage.

    Operational types (OPERATIONAL_TYPES) are explicitly forbidden from
    the event store and must use Prometheus or operational DB.
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
            # Prohibited language events (Story 9.1, FR55)
            "prohibited.language.blocked",
            # Publication scan events (Story 9.2, FR56)
            "publication.scanned",
            "publication.blocked",
            # User content prohibition events (Story 9.4, FR58)
            "user_content.prohibited",
            "user_content.cleared",
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

    @classmethod
    def is_valid_constitutional_type(cls, event_type: str) -> bool:
        """Check if an event type is valid for the constitutional event store.

        Args:
            event_type: The event type to check.

        Returns:
            True if the type is allowed in the event store, False otherwise.
        """
        if not event_type:
            return False
        return event_type in cls.CONSTITUTIONAL_TYPES

    @classmethod
    def is_operational_type(cls, data_type: str) -> bool:
        """Check if a data type is operational (forbidden in event store).

        Args:
            data_type: The data type to check.

        Returns:
            True if the type is operational metrics, False otherwise.
        """
        if not data_type:
            return False
        return data_type in cls.OPERATIONAL_TYPES
