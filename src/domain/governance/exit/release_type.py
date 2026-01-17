"""Release type enum for obligation release.

Story: consent-gov-7.2: Obligation Release

Defines the types of release that occur when a Cluster exits:
- NULLIFIED_ON_EXIT: Pre-consent tasks (never agreed to)
- RELEASED_ON_EXIT: Post-consent tasks (work preserved)

Constitutional Truths Honored:
- Golden Rule: Refusal is penalty-free
- Exit preserves dignity by preserving work
"""

from __future__ import annotations

from enum import Enum


class ReleaseType(str, Enum):
    """Type of obligation release during exit.

    Per FR44: All obligations released on exit.

    Categories:
    - NULLIFIED_ON_EXIT: Pre-consent tasks (Cluster never agreed)
    - RELEASED_ON_EXIT: Post-consent tasks (work is preserved)

    The distinction matters:
    - Pre-consent: Clean void (as if task never happened)
    - Post-consent: Work acknowledged and preserved for attribution
    """

    NULLIFIED_ON_EXIT = "nullified_on_exit"
    """Pre-consent task voided on exit.

    Applies to: AUTHORIZED, ACTIVATED, ROUTED states.
    No work to preserve - Cluster never agreed.
    """

    RELEASED_ON_EXIT = "released_on_exit"
    """Post-consent task released with work preserved.

    Applies to: ACCEPTED, IN_PROGRESS, REPORTED, AGGREGATED states.
    Work preserved for attribution - Cluster's contribution acknowledged.
    """
