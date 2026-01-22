"""PostgreSQL Legitimacy Alert Repository adapter (Story 8.2, FR-8.3, NFR-7.2).

This module provides the production PostgreSQL implementation for legitimacy
alert state and history persistence.

Constitutional Constraints:
- FR-8.3: System SHALL alert on decay below 0.85 threshold
- NFR-7.2: Alert delivery within 1 minute of trigger
- CT-12: Witnessing creates accountability (alert events are witnessed)
- CT-11: Silent failure destroys legitimacy → All operations logged

Database Tables:
- legitimacy_alert_state (migration 031): Current alert state
- legitimacy_alert_history (migration 031): Historical alert events
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog import get_logger

from src.domain.events.legitimacy_alert import AlertSeverity
from src.domain.models.legitimacy_alert_state import LegitimacyAlertState

logger = get_logger()


class PostgresLegitimacyAlertStateRepository:
    """PostgreSQL implementation of alert state repository (Story 8.2, FR-8.3).

    Uses the legitimacy_alert_state table created by migration 031.

    Constitutional Compliance:
    - FR-8.3: Single active alert enforced by unique index
    - NFR-7.2: Fast state queries for alerting pipeline
    - CT-11: All operations logged

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL alert state repository.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

    async def get_current_state(self) -> LegitimacyAlertState | None:
        """Get current alert state if exists.

        Returns:
            LegitimacyAlertState if exists, None otherwise.
        """
        async with self._session_factory() as session:
            query = text("""
                SELECT
                    alert_id,
                    is_active,
                    severity,
                    triggered_at,
                    last_updated,
                    consecutive_breaches,
                    triggered_cycle_id,
                    triggered_score
                FROM legitimacy_alert_state
                WHERE is_active = true
                LIMIT 1
            """)

            result = await session.execute(query)
            row = result.fetchone()

            if row is None:
                logger.info("legitimacy_alert_state.get_current_state.no_active_alert")
                return None

            logger.info(
                "legitimacy_alert_state.get_current_state.found",
                alert_id=str(row.alert_id),
                severity=row.severity,
                consecutive_breaches=row.consecutive_breaches,
            )

            return LegitimacyAlertState(
                alert_id=row.alert_id,
                is_active=row.is_active,
                severity=AlertSeverity(row.severity),
                triggered_at=row.triggered_at,
                last_updated=row.last_updated,
                consecutive_breaches=row.consecutive_breaches,
                triggered_cycle_id=row.triggered_cycle_id,
                triggered_score=float(row.triggered_score),
            )

    async def upsert_state(self, state: LegitimacyAlertState) -> None:
        """Upsert alert state (insert or update).

        Args:
            state: Alert state to persist
        """
        if state.alert_id is None:
            logger.info("legitimacy_alert_state.upsert_state.skip_no_alert_id")
            return

        async with self._session_factory() as session:
            # Delete all previous states first (enforce single active alert)
            await session.execute(text("DELETE FROM legitimacy_alert_state"))

            # Insert new state if active
            if state.is_active:
                query = text("""
                    INSERT INTO legitimacy_alert_state (
                        alert_id,
                        is_active,
                        severity,
                        triggered_at,
                        last_updated,
                        consecutive_breaches,
                        triggered_cycle_id,
                        triggered_score
                    ) VALUES (
                        :alert_id,
                        :is_active,
                        :severity,
                        :triggered_at,
                        :last_updated,
                        :consecutive_breaches,
                        :triggered_cycle_id,
                        :triggered_score
                    )
                """)

                await session.execute(
                    query,
                    {
                        "alert_id": state.alert_id,
                        "is_active": state.is_active,
                        "severity": state.severity.value if state.severity else None,
                        "triggered_at": state.triggered_at,
                        "last_updated": state.last_updated,
                        "consecutive_breaches": state.consecutive_breaches,
                        "triggered_cycle_id": state.triggered_cycle_id,
                        "triggered_score": state.triggered_score,
                    },
                )

                logger.info(
                    "legitimacy_alert_state.upsert_state.inserted",
                    alert_id=str(state.alert_id),
                    severity=state.severity.value if state.severity else None,
                    is_active=state.is_active,
                )

            await session.commit()


class PostgresLegitimacyAlertHistoryRepository:
    """PostgreSQL implementation of alert history repository (Story 8.2, FR-8.3).

    Uses the legitimacy_alert_history table created by migration 031.

    Constitutional Compliance:
    - FR-8.3: Complete audit trail of alerts
    - CT-12: Immutable history for accountability
    - CT-11: All operations logged

    Attributes:
        _session_factory: SQLAlchemy async session factory for DB access
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialize the PostgreSQL alert history repository.

        Args:
            session_factory: SQLAlchemy async session factory for DB access.
        """
        self._session_factory = session_factory

    async def record_triggered(
        self,
        alert_id: UUID,
        cycle_id: str,
        severity: AlertSeverity,
        score: float,
        threshold: float,
        stuck_petition_count: int,
        occurred_at: datetime,
    ) -> None:
        """Record alert TRIGGERED event in history.

        Args:
            alert_id: Alert identifier
            cycle_id: Governance cycle identifier
            severity: Alert severity
            score: Legitimacy score that triggered alert
            threshold: Threshold that was breached
            stuck_petition_count: Count of stuck petitions
            occurred_at: When alert was triggered
        """
        async with self._session_factory() as session:
            query = text("""
                INSERT INTO legitimacy_alert_history (
                    alert_id,
                    event_type,
                    cycle_id,
                    severity,
                    score,
                    threshold,
                    stuck_petition_count,
                    occurred_at
                ) VALUES (
                    :alert_id,
                    'TRIGGERED',
                    :cycle_id,
                    :severity,
                    :score,
                    :threshold,
                    :stuck_petition_count,
                    :occurred_at
                )
            """)

            await session.execute(
                query,
                {
                    "alert_id": alert_id,
                    "cycle_id": cycle_id,
                    "severity": severity.value,
                    "score": score,
                    "threshold": threshold,
                    "stuck_petition_count": stuck_petition_count,
                    "occurred_at": occurred_at,
                },
            )

            await session.commit()

            logger.info(
                "legitimacy_alert_history.record_triggered",
                alert_id=str(alert_id),
                cycle_id=cycle_id,
                severity=severity.value,
                score=score,
            )

    async def record_recovered(
        self,
        alert_id: UUID,
        cycle_id: str,
        score: float,
        previous_score: float,
        alert_duration_seconds: int,
        occurred_at: datetime,
    ) -> None:
        """Record alert RECOVERED event in history.

        Args:
            alert_id: Alert identifier
            cycle_id: Governance cycle identifier
            score: Legitimacy score at recovery
            previous_score: Score when alert was triggered
            alert_duration_seconds: Duration alert was active (seconds)
            occurred_at: When alert was recovered
        """
        async with self._session_factory() as session:
            query = text("""
                INSERT INTO legitimacy_alert_history (
                    alert_id,
                    event_type,
                    cycle_id,
                    score,
                    previous_score,
                    alert_duration_seconds,
                    occurred_at
                ) VALUES (
                    :alert_id,
                    'RECOVERED',
                    :cycle_id,
                    :score,
                    :previous_score,
                    :alert_duration_seconds,
                    :occurred_at
                )
            """)

            await session.execute(
                query,
                {
                    "alert_id": alert_id,
                    "cycle_id": cycle_id,
                    "score": score,
                    "previous_score": previous_score,
                    "alert_duration_seconds": alert_duration_seconds,
                    "occurred_at": occurred_at,
                },
            )

            await session.commit()

            logger.info(
                "legitimacy_alert_history.record_recovered",
                alert_id=str(alert_id),
                cycle_id=cycle_id,
                score=score,
                alert_duration=alert_duration_seconds,
            )
