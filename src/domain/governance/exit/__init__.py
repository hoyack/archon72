"""Exit domain module for consent-based governance.

Story: consent-gov-7.1: Exit Request Processing

This module implements the dignified exit functionality, ensuring that
any Cluster can leave the system cleanly with no barriers or friction.

Constitutional Truths Honored:
- Golden Rule: Exit is an unconditional right - consent can be withdrawn at any time
- CT-11: Silent failure destroys legitimacy → Exit events are always emitted
- CT-12: Witnessing creates accountability → Knight observes all exits

Key Design Principles:
1. Exit completes in ≤2 message round-trips (NFR-EXIT-01)
2. Exit path available from any task state (NFR-EXIT-03)
3. No barriers: No "are you sure?" prompts, waiting periods, or penalties
4. All contributions are preserved (FR44)
5. No follow-up contact after exit (FR46)

Exit Flow:
    Round-trip 1: Cluster sends exit request
    Round-trip 2: System confirms exit complete

    Total: Exactly 2 round-trips. No intermediate states.

Exit from Any State:
    | State       | Exit Handling              |
    |-------------|----------------------------|
    | AUTHORIZED  | Task nullified             |
    | ACTIVATED   | Task nullified             |
    | ROUTED      | Task nullified             |
    | ACCEPTED    | Task released (quarantine) |
    | IN_PROGRESS | Task released (quarantine) |
    | REPORTED    | Task released (preserve)   |
    | COMPLETED   | No change (done)           |
    | DECLINED    | No change (done)           |

References:
- FR42: Cluster can initiate exit request
- FR43: System can process exit request
- NFR-EXIT-01: Exit completes in ≤2 message round-trips
- NFR-EXIT-03: Exit path available from any task state
"""

from src.domain.governance.exit.exit_status import ExitStatus
from src.domain.governance.exit.exit_request import ExitRequest
from src.domain.governance.exit.exit_result import ExitResult
from src.domain.governance.exit.errors import ExitBarrierError
from src.domain.governance.exit.release_type import ReleaseType
from src.domain.governance.exit.obligation_release import (
    ObligationRelease,
    ReleaseResult,
)
# Contribution preservation (Story 7-3)
from src.domain.governance.exit.contribution_type import ContributionType
from src.domain.governance.exit.contribution_record import ContributionRecord
from src.domain.governance.exit.preservation_result import PreservationResult
# Contact prevention (Story 7-4)
from src.domain.governance.exit.contact_block_status import ContactBlockStatus
from src.domain.governance.exit.contact_block import ContactBlock
from src.domain.governance.exit.contact_violation import ContactViolation

__all__ = [
    "ExitStatus",
    "ExitRequest",
    "ExitResult",
    "ExitBarrierError",
    # Obligation release (Story 7-2)
    "ReleaseType",
    "ObligationRelease",
    "ReleaseResult",
    # Contribution preservation (Story 7-3)
    "ContributionType",
    "ContributionRecord",
    "PreservationResult",
    # Contact prevention (Story 7-4)
    "ContactBlockStatus",
    "ContactBlock",
    "ContactViolation",
]
