"""Integration tests for legitimacy metrics computation (Story 8.1, FR-8.1, FR-8.2).

Tests the full legitimacy metrics computation flow including:
- Database petition querying
- Metrics computation
- Storage to legitimacy_metrics table
- Retrieval and trend analysis

Constitutional Constraints:
- FR-8.1: System SHALL compute legitimacy decay metric per cycle
- FR-8.2: Decay formula: (fated_petitions / total_petitions) within SLA
- NFR-1.5: Metric computation completes within 60 seconds
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.application.services.legitimacy_metrics_service import (
    LegitimacyMetricsService,
)


@pytest.mark.integration
class TestLegitimacyMetricsComputationIntegration:
    """Integration tests for legitimacy metrics computation flow."""

    def test_compute_and_store_metrics_full_flow(self, test_db):
        """Test full flow: compute metrics, store, retrieve."""
        # Given: Create test petitions in the database
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # Create 10 petitions: 8 fated (ACKNOWLEDGED), 2 still in RECEIVED
        petition_ids = []
        with test_db.cursor() as cursor:
            # 8 fated petitions
            for i in range(8):
                petition_id = uuid4()
                petition_ids.append(petition_id)
                created_at = cycle_start + timedelta(hours=i)
                updated_at = created_at + timedelta(hours=1)  # Fated after 1 hour

                cursor.execute(
                    """
                    INSERT INTO petition_submissions (
                        id,
                        type,
                        text,
                        submitter_id,
                        state,
                        content_hash,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(petition_id),
                        "GENERAL",
                        f"Test petition {i}",
                        str(uuid4()),
                        "ACKNOWLEDGED",
                        b"test_hash",
                        created_at,
                        updated_at,
                    ),
                )

            # 2 unfated petitions (still in RECEIVED)
            for i in range(8, 10):
                petition_id = uuid4()
                petition_ids.append(petition_id)
                created_at = cycle_start + timedelta(hours=i)

                cursor.execute(
                    """
                    INSERT INTO petition_submissions (
                        id,
                        type,
                        text,
                        submitter_id,
                        state,
                        content_hash,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(petition_id),
                        "GENERAL",
                        f"Test petition {i}",
                        str(uuid4()),
                        "RECEIVED",
                        b"test_hash",
                        created_at,
                        created_at,  # Not updated yet
                    ),
                )

            test_db.commit()

        # When: Compute metrics
        service = LegitimacyMetricsService(test_db)
        cycle_id = "2026-W04"

        metrics = service.compute_metrics(cycle_id, cycle_start, cycle_end)

        # Then: Verify computed metrics
        assert metrics.cycle_id == cycle_id
        assert metrics.total_petitions == 10
        assert metrics.fated_petitions == 8
        assert metrics.legitimacy_score == 0.8  # FR-8.2: 8/10
        assert metrics.average_time_to_fate == 3600.0  # 1 hour in seconds
        assert metrics.median_time_to_fate == 3600.0

        # When: Store metrics
        service.store_metrics(metrics)

        # Then: Verify stored metrics can be retrieved
        retrieved = service.get_metrics(cycle_id)
        assert retrieved is not None
        assert retrieved.cycle_id == cycle_id
        assert retrieved.legitimacy_score == 0.8
        assert retrieved.total_petitions == 10
        assert retrieved.fated_petitions == 8

    def test_compute_metrics_with_varying_fate_times(self, test_db):
        """Test metrics computation with varying time-to-fate durations."""
        # Given: Petitions with varying fate times
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        fate_times = [1800, 3600, 5400, 7200, 9000]  # 0.5h, 1h, 1.5h, 2h, 2.5h

        with test_db.cursor() as cursor:
            for i, fate_time_seconds in enumerate(fate_times):
                petition_id = uuid4()
                created_at = cycle_start + timedelta(hours=i)
                updated_at = created_at + timedelta(seconds=fate_time_seconds)

                cursor.execute(
                    """
                    INSERT INTO petition_submissions (
                        id,
                        type,
                        text,
                        submitter_id,
                        state,
                        content_hash,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(petition_id),
                        "GENERAL",
                        f"Test petition {i}",
                        str(uuid4()),
                        "ACKNOWLEDGED",
                        b"test_hash",
                        created_at,
                        updated_at,
                    ),
                )

            test_db.commit()

        # When
        service = LegitimacyMetricsService(test_db)
        metrics = service.compute_metrics("2026-W04", cycle_start, cycle_end)

        # Then
        assert metrics.total_petitions == 5
        assert metrics.fated_petitions == 5
        assert metrics.legitimacy_score == 1.0  # All fated
        assert metrics.average_time_to_fate == sum(fate_times) / len(fate_times)
        assert metrics.median_time_to_fate == 5400.0  # Middle value

    def test_compute_metrics_with_zero_petitions(self, test_db):
        """Test metrics computation with no petitions in cycle."""
        # Given: Empty cycle period
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # When
        service = LegitimacyMetricsService(test_db)
        metrics = service.compute_metrics("2026-W04", cycle_start, cycle_end)

        # Then
        assert metrics.total_petitions == 0
        assert metrics.fated_petitions == 0
        assert metrics.legitimacy_score is None
        assert metrics.average_time_to_fate is None
        assert metrics.median_time_to_fate is None

        # And: Can still store and retrieve
        service.store_metrics(metrics)
        retrieved = service.get_metrics("2026-W04")
        assert retrieved is not None
        assert retrieved.legitimacy_score is None

    def test_get_recent_metrics_returns_ordered_list(self, test_db):
        """Test retrieval of recent metrics in chronological order."""
        # Given: Multiple cycles with metrics
        service = LegitimacyMetricsService(test_db)

        cycles = [
            ("2026-W03", datetime(2026, 1, 13, 0, 0, 0, tzinfo=timezone.utc)),
            ("2026-W04", datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)),
            ("2026-W05", datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)),
        ]

        for cycle_id, cycle_start in cycles:
            cycle_end = cycle_start + timedelta(days=7)
            metrics = service.compute_metrics(cycle_id, cycle_start, cycle_end)
            service.store_metrics(metrics)

        # When
        recent_metrics = service.get_recent_metrics(limit=3)

        # Then
        assert len(recent_metrics) == 3
        assert recent_metrics[0].cycle_id == "2026-W05"  # Most recent first
        assert recent_metrics[1].cycle_id == "2026-W04"
        assert recent_metrics[2].cycle_id == "2026-W03"

    def test_metrics_health_status_integration(self, test_db):
        """Test health status determination in full integration."""
        # Given: Cycles with different health levels
        service = LegitimacyMetricsService(test_db)
        cycle_start = datetime(2026, 1, 20, 0, 0, 0, tzinfo=timezone.utc)
        cycle_end = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

        # Create petitions for 60% fated (CRITICAL)
        with test_db.cursor() as cursor:
            for i in range(10):
                petition_id = uuid4()
                created_at = cycle_start + timedelta(hours=i)
                state = "ACKNOWLEDGED" if i < 6 else "RECEIVED"
                updated_at = (
                    created_at + timedelta(hours=1) if state == "ACKNOWLEDGED" else created_at
                )

                cursor.execute(
                    """
                    INSERT INTO petition_submissions (
                        id,
                        type,
                        text,
                        submitter_id,
                        state,
                        content_hash,
                        created_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(petition_id),
                        "GENERAL",
                        f"Test petition {i}",
                        str(uuid4()),
                        state,
                        b"test_hash",
                        created_at,
                        updated_at,
                    ),
                )

            test_db.commit()

        # When
        metrics = service.compute_metrics("2026-W04", cycle_start, cycle_end)
        service.store_metrics(metrics)

        # Then
        retrieved = service.get_metrics("2026-W04")
        assert retrieved.legitimacy_score == 0.6
        assert retrieved.health_status() == "CRITICAL"  # < 0.70
        assert retrieved.is_healthy(threshold=0.85) is False


@pytest.fixture
def test_db(test_database_connection):
    """Provide test database connection with petition_submissions table."""
    conn = test_database_connection

    # Ensure legitimacy_metrics table exists
    with conn.cursor() as cursor:
        # Create legitimacy_metrics table if not exists (from migration)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS legitimacy_metrics (
                metrics_id UUID PRIMARY KEY,
                cycle_id TEXT NOT NULL UNIQUE,
                cycle_start TIMESTAMPTZ NOT NULL,
                cycle_end TIMESTAMPTZ NOT NULL,
                total_petitions INT NOT NULL,
                fated_petitions INT NOT NULL,
                legitimacy_score DECIMAL(5, 4),
                average_time_to_fate DECIMAL(12, 2),
                median_time_to_fate DECIMAL(12, 2),
                computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

        # Ensure petition_submissions enum types exist
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'petition_type_enum'
                      AND n.nspname = current_schema()
                ) THEN
                    CREATE TYPE petition_type_enum AS ENUM (
                        'GENERAL',
                        'CESSATION',
                        'GRIEVANCE',
                        'COLLABORATION'
                    );
                END IF;
            END $$;
            """
        )
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE t.typname = 'petition_state_enum'
                      AND n.nspname = current_schema()
                ) THEN
                    CREATE TYPE petition_state_enum AS ENUM (
                        'RECEIVED',
                        'DELIBERATING',
                        'ACKNOWLEDGED',
                        'REFERRED',
                        'ESCALATED'
                    );
                END IF;
            END $$;
            """
        )

        # Ensure petition_submissions table exists (align with migration)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS petition_submissions (
                id UUID PRIMARY KEY,
                type petition_type_enum NOT NULL,
                text TEXT NOT NULL,
                submitter_id UUID,
                state petition_state_enum NOT NULL DEFAULT 'RECEIVED',
                content_hash BYTEA,
                realm TEXT NOT NULL DEFAULT 'default',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT petition_text_length CHECK (char_length(text) <= 10000)
            )
            """
        )

        conn.commit()

    yield conn

    # Cleanup
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM legitimacy_metrics")
        cursor.execute("DELETE FROM petition_submissions")
        conn.commit()
