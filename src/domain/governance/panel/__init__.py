"""Prince Panel domain models for judicial review.

Story: consent-gov-6-4: Prince Panel Domain Model

This module defines the Prince Panel judicial review mechanics for the
consent-based governance system. Panels review witness statements and
issue formal findings.

Panel Design Principles:
-----------------------
1. Minimum 3 members: Prevents single-point decisions
2. Deliberation required: Multiple perspectives included
3. Dissent preserved: Minority opinion recorded (FR39)
4. Corrective, not punitive: Dignity preservation

Why ≥3 Members? (FR36)
----------------------
Single person decisions:
  - No check on individual bias
  - No deliberation required
  - No dissent possible
  - Single point of failure

Two person panels:
  - Deadlock possible
  - Still limited perspective

Three or more:
  - Deliberation required
  - Majority can decide
  - Dissent can be recorded
  - Multiple perspectives included

Remedy Philosophy:
-----------------
Remedies are CORRECTIVE, not PUNITIVE:
  - WARNING: Formal notice
  - CORRECTION: Require action change
  - ESCALATION: Route to higher authority
  - HALT_RECOMMENDATION: Recommend system halt

Explicitly NOT available (dignity preservation):
  - Reputation penalties
  - Access restrictions
  - Punitive fines
  - Permanent marks

Why no punitive remedies?
  - Consent-based system respects dignity
  - Refusal is penalty-free (Golden Rule)
  - Correction addresses problem
  - Punishment creates fear → coercion

Dissent Preservation (FR39):
---------------------------
Dissent is NOT:
  - Overruled
  - Suppressed
  - Hidden

Dissent IS:
  - Recorded alongside finding
  - Visible to observers
  - Part of official record
  - Valuable for appeals/review

References:
    - FR36: Human Operator can convene panel (≥3 members)
    - FR37: Prince Panel can review witness artifacts
    - FR38: Prince Panel can issue formal finding with remedy
    - FR39: Prince Panel can record dissent in finding
"""

from src.domain.governance.panel.determination import Determination
from src.domain.governance.panel.dissent import Dissent
from src.domain.governance.panel.errors import InvalidPanelComposition
from src.domain.governance.panel.finding_record import FindingRecord
from src.domain.governance.panel.member_status import MemberStatus
from src.domain.governance.panel.panel_finding import PanelFinding
from src.domain.governance.panel.panel_member import PanelMember
from src.domain.governance.panel.panel_status import PanelStatus
from src.domain.governance.panel.prince_panel import PrincePanel
from src.domain.governance.panel.recusal import RecusalRequest
from src.domain.governance.panel.remedy_type import RemedyType
from src.domain.governance.panel.review_session import ReviewedArtifact, ReviewSession

__all__ = [
    "PanelStatus",
    "MemberStatus",
    "PanelMember",
    "RemedyType",
    "Determination",
    "Dissent",
    "PanelFinding",
    "PrincePanel",
    "InvalidPanelComposition",
    "RecusalRequest",
    "ReviewSession",
    "ReviewedArtifact",
    "FindingRecord",
]
