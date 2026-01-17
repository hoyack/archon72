"""Queue priority enum for Prince Panel queue items.

Story: consent-gov-6-3: Witness Statement Routing

This module defines the priority levels for queued witness statements.
Priority affects queue ordering and determines review urgency.

Priority Assignment Rules:
-------------------------
CRITICAL: Hash chain gaps, integrity issues (immediate attention)
HIGH: Consent violations, coercion blocked (review within 24h)
MEDIUM: Timing anomalies (review within 72h)
LOW: Other potential violations (normal queue processing)

Constitutional Truths Honored:
- CT-11: Silent failure destroys legitimacy -> Critical priority for integrity
- CT-12: Witnessing creates accountability -> All items tracked

References:
    - AC6: Queue includes priority based on observation type
"""

from __future__ import annotations

from enum import Enum


class QueuePriority(Enum):
    """Priority levels for panel queue items.

    Priority determines the order in which statements are reviewed
    by the Prince Panel. Higher priority items are reviewed first.

    Note: Priority is assigned by the routing service based on
    observation type and content analysis. It is NOT a judgment
    about the statement's validity.
    """

    CRITICAL = "critical"
    """Integrity issues requiring immediate attention.

    Assigned to:
    - Hash chain gaps (potential tampering/suppression)
    - Integrity verification failures
    - System-level anomalies

    Expected response: Immediate panel review, possible system halt.
    """

    HIGH = "high"
    """Consent/coercion violations requiring urgent review.

    Assigned to:
    - Consent violations detected
    - Coercion patterns blocked
    - Role boundary violations

    Expected response: Review within 24 hours.
    """

    MEDIUM = "medium"
    """Timing anomalies requiring investigation.

    Assigned to:
    - Timing anomalies (suspicious delays/accelerations)
    - Sequence irregularities
    - Process timing violations

    Expected response: Review within 72 hours.
    """

    LOW = "low"
    """Other potential violations for normal processing.

    Assigned to:
    - Other potential violations not matching above categories
    - Observations requiring routine review

    Expected response: Review during normal queue processing.
    """
