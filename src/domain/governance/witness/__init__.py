"""Knight Witness domain models.

Story: consent-gov-6-1: Knight Witness Domain Model

This module defines the Knight witness capability for the consent-based
governance system. The Knight observes all branch actions and records
factual observations without judgment.

Knight's Role: Observer, Not Judge
---------------------------------
What Knight DOES:
  - Observes all branch actions
  - Records factual observations
  - Detects timing anomalies
  - Detects hash chain gaps
  - Routes statements to Prince Panel queue

What Knight does NOT do:
  - Make judgments about violations
  - Recommend remedies
  - Enforce rules
  - Block actions

The Knight is analogous to a court reporter:
  - Records everything accurately
  - Does not interrupt proceedings
  - Does not offer opinions
  - Provides transcript for others to judge

Why Observation-Only?
--------------------
Separation of witness and judicial powers:
  - Observer who judges is a conflict of interest
  - Observation must be neutral to be trusted
  - Judgment requires deliberation (panels)
  - Knight's value is in completeness, not interpretation

If Knight could judge:
  - Knight becomes a single point of failure
  - Knight's biases affect all outcomes
  - No appeal possible from Knight judgment
  - Separation of powers violated

Suppression Prevention (NFR-CONST-07):
-------------------------------------
Mechanisms:
1. Two-phase emission: intent -> observation -> commit
   - Observation emitted BEFORE state changes
   - If action fails, observation still recorded

2. Immutable statements:
   - No delete method exists
   - No modify method exists
   - Append-only ledger enforces this

3. Gap detection:
   - Hash chain reveals missing statements
   - Gap itself becomes violation evidence
   - Knight has dual path: bus + ledger poll

References:
    - FR33: Knight can observe and record violations across all branches
    - FR34: Knight can publish witness statements (observation only, no judgment)
    - NFR-CONST-07: Witness statements cannot be suppressed by any role
    - AD-16: Knight Observation Pattern (passive subscription)
"""

from src.domain.governance.witness.errors import JudgmentLanguageError
from src.domain.governance.witness.observation_content import ObservationContent
from src.domain.governance.witness.observation_type import ObservationType
from src.domain.governance.witness.witness_statement import WitnessStatement
from src.domain.governance.witness.witness_statement_factory import (
    WitnessStatementFactory,
)

__all__ = [
    "ObservationType",
    "ObservationContent",
    "WitnessStatement",
    "WitnessStatementFactory",
    "JudgmentLanguageError",
]
