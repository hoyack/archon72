#!/usr/bin/env python3
"""
Create Kafka topics for async vote validation.

ADR-003: Topic Design and Partitioning
- Stage-per-topic with vote_id partitioning
- Different retention policies per topic purpose

Usage:
    python scripts/create_kafka_topics.py [--bootstrap-servers localhost:19092]
"""

import argparse
import sys
from dataclasses import dataclass

try:
    from confluent_kafka.admin import AdminClient, NewTopic, ConfigResource
except ImportError:
    print("ERROR: confluent-kafka not installed. Run: pip install confluent-kafka")
    sys.exit(1)


@dataclass
class TopicConfig:
    """Configuration for a Kafka topic."""

    name: str
    partitions: int
    replication_factor: int
    retention_ms: int | None  # None = infinite
    cleanup_policy: str  # "delete" or "compact"
    description: str


# ADR-003: Topic Configuration
TOPICS = [
    TopicConfig(
        name="conclave.votes.cast",
        partitions=6,
        replication_factor=1,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        cleanup_policy="delete",
        description="Raw votes as captured (optimistic)",
    ),
    TopicConfig(
        name="conclave.votes.validation-started",
        partitions=6,
        replication_factor=1,
        retention_ms=7 * 24 * 60 * 60 * 1000,
        cleanup_policy="delete",
        description="Validation job initiated",
    ),
    TopicConfig(
        name="conclave.votes.deliberation-results",
        partitions=6,
        replication_factor=1,
        retention_ms=30 * 24 * 60 * 60 * 1000,
        cleanup_policy="delete",
        description="Individual deliberator outputs",
    ),
    TopicConfig(
        name="conclave.votes.adjudication-results",
        partitions=3,
        replication_factor=1,
        retention_ms=30 * 24 * 60 * 60 * 1000,
        cleanup_policy="delete",
        description="Witness adjudication outcomes",
    ),
    TopicConfig(
        name="conclave.votes.pending-validation",
        partitions=6,
        replication_factor=1,  # Single node for dev
        retention_ms=7 * 24 * 60 * 60 * 1000,  # 7 days
        cleanup_policy="delete",
        description="Votes awaiting async validation",
    ),
    TopicConfig(
        name="conclave.votes.validation-requests",
        partitions=6,
        replication_factor=1,
        retention_ms=7 * 24 * 60 * 60 * 1000,  # 7 days
        cleanup_policy="delete",
        description="Per-validator validation requests (Round 7 mitigation)",
    ),
    TopicConfig(
        name="conclave.votes.validation-results",
        partitions=6,
        replication_factor=1,
        retention_ms=30 * 24 * 60 * 60 * 1000,  # 30 days
        cleanup_policy="delete",
        description="Individual validator responses (audit trail)",
    ),
    TopicConfig(
        name="conclave.votes.witness-requests",
        partitions=3,
        replication_factor=1,
        retention_ms=7 * 24 * 60 * 60 * 1000,  # 7 days
        cleanup_policy="delete",
        description="Witness requests after secretary consensus",
    ),
    TopicConfig(
        name="conclave.votes.witness.events",
        partitions=3,
        replication_factor=1,
        retention_ms=None,  # Infinite - governance audit trail
        cleanup_policy="delete",
        description="Witness observations for validated votes",
    ),
    TopicConfig(
        name="conclave.votes.validated",
        partitions=6,
        replication_factor=1,
        retention_ms=90 * 24 * 60 * 60 * 1000,  # 90 days
        cleanup_policy="compact",  # Keep latest per vote_id
        description="Final consensus results",
    ),
    TopicConfig(
        name="conclave.votes.overrides",
        partitions=3,
        replication_factor=1,
        retention_ms=None,
        cleanup_policy="delete",
        description="Corrections applied at reconciliation",
    ),
    TopicConfig(
        name="conclave.votes.dead-letter",
        partitions=1,
        replication_factor=1,
        retention_ms=None,  # Infinite - never delete failed validations
        cleanup_policy="delete",
        description="Failed validations for review",
    ),
    TopicConfig(
        name="conclave.witness.statements",
        partitions=3,
        replication_factor=1,
        retention_ms=None,
        cleanup_policy="delete",
        description="Formal witness statements",
    ),
    TopicConfig(
        name="conclave.witness.retorts",
        partitions=3,
        replication_factor=1,
        retention_ms=None,
        cleanup_policy="delete",
        description="Witness retort records",
    ),
    TopicConfig(
        name="conclave.sessions.checkpoints",
        partitions=1,
        replication_factor=1,
        retention_ms=None,
        cleanup_policy="delete",
        description="Session checkpoint snapshots",
    ),
    TopicConfig(
        name="conclave.sessions.transcripts",
        partitions=1,
        replication_factor=1,
        retention_ms=None,
        cleanup_policy="compact",
        description="Final transcripts (compacted)",
    ),
]


def create_topics(bootstrap_servers: str, dry_run: bool = False) -> bool:
    """
    Create all required Kafka topics.

    Args:
        bootstrap_servers: Kafka bootstrap servers address
        dry_run: If True, only print what would be created

    Returns:
        True if all topics created successfully
    """
    if dry_run:
        print(f"DRY RUN: Would connect to {bootstrap_servers}")
        for topic in TOPICS:
            print(f"  Would create: {topic.name}")
            print(f"    Partitions: {topic.partitions}")
            print(f"    Retention: {topic.retention_ms}ms" if topic.retention_ms else "    Retention: infinite")
            print(f"    Cleanup: {topic.cleanup_policy}")
        return True

    print(f"Connecting to Kafka at {bootstrap_servers}...")

    admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})

    # Check existing topics
    metadata = admin_client.list_topics(timeout=10)
    existing_topics = set(metadata.topics.keys())

    # Build list of topics to create
    new_topics = []
    for topic in TOPICS:
        if topic.name in existing_topics:
            print(f"  SKIP: {topic.name} (already exists)")
            continue

        config = {"cleanup.policy": topic.cleanup_policy}
        if topic.retention_ms is not None:
            config["retention.ms"] = str(topic.retention_ms)
        else:
            # Infinite retention
            config["retention.ms"] = "-1"

        new_topic = NewTopic(
            topic=topic.name,
            num_partitions=topic.partitions,
            replication_factor=topic.replication_factor,
            config=config,
        )
        new_topics.append(new_topic)
        print(f"  CREATE: {topic.name} ({topic.description})")

    if not new_topics:
        print("\nAll topics already exist.")
        return True

    # Create topics
    print(f"\nCreating {len(new_topics)} topics...")
    futures = admin_client.create_topics(new_topics, operation_timeout=30)

    success = True
    for topic_name, future in futures.items():
        try:
            future.result()  # Wait for creation
            print(f"  OK: {topic_name}")
        except Exception as e:
            print(f"  FAILED: {topic_name} - {e}")
            success = False

    return success


def verify_topics(bootstrap_servers: str) -> bool:
    """Verify all required topics exist with correct configuration."""
    print(f"\nVerifying topics on {bootstrap_servers}...")

    admin_client = AdminClient({"bootstrap.servers": bootstrap_servers})
    metadata = admin_client.list_topics(timeout=10)
    existing_topics = set(metadata.topics.keys())

    all_ok = True
    for topic in TOPICS:
        if topic.name not in existing_topics:
            print(f"  MISSING: {topic.name}")
            all_ok = False
        else:
            topic_metadata = metadata.topics[topic.name]
            partition_count = len(topic_metadata.partitions)
            if partition_count != topic.partitions:
                print(f"  WARN: {topic.name} has {partition_count} partitions, expected {topic.partitions}")
            else:
                print(f"  OK: {topic.name} ({partition_count} partitions)")

    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create Kafka topics for async vote validation (ADR-003)"
    )
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:19092",
        help="Kafka bootstrap servers (default: localhost:19092)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without actually creating",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify topics exist instead of creating",
    )

    args = parser.parse_args()

    try:
        if args.verify:
            success = verify_topics(args.bootstrap_servers)
        else:
            success = create_topics(args.bootstrap_servers, dry_run=args.dry_run)

        if success:
            print("\nDone.")
            return 0
        else:
            print("\nCompleted with errors.")
            return 1

    except Exception as e:
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
