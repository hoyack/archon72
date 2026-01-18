"""Event type registry and validation for governance events.

Per governance-architecture.md Event Naming Convention (Locked):
- Pattern: {branch}.{noun}.{verb}
- Branch: executive, judicial, witness, filter, consent, legitimacy, exit, etc.
- Noun: Aggregate or entity (task, panel, observation, filter, band)
- Verb: Past-tense action (accepted, convened, recorded, blocked, decayed)

Branch is derived at write-time using event_type.split('.')[0], NEVER trusted
from caller input.
"""

import re
from enum import Enum

from src.domain.errors.constitutional import ConstitutionalViolationError

# Event type validation pattern: branch.noun.verb (all lowercase, underscore allowed in verb)
_EVENT_TYPE_PATTERN = re.compile(r"^[a-z]+\.[a-z]+\.[a-z_]+$")


class GovernanceEventType(str, Enum):
    """Known governance event types.

    This enum provides type safety for common event types while still
    allowing extension via direct string usage for new event types.

    Event types follow branch.noun.verb convention.
    """

    # Executive branch - Task lifecycle
    EXECUTIVE_TASK_ACTIVATED = "executive.task.activated"
    EXECUTIVE_TASK_ACCEPTED = "executive.task.accepted"
    EXECUTIVE_TASK_DECLINED = "executive.task.declined"
    EXECUTIVE_TASK_COMPLETED = "executive.task.completed"
    EXECUTIVE_TASK_EXPIRED = "executive.task.expired"
    EXECUTIVE_TASK_REMINDER_SENT = "executive.task.reminder_sent"

    # Judicial branch - Panel operations
    JUDICIAL_PANEL_CONVENED = "judicial.panel.convened"
    JUDICIAL_FINDING_ISSUED = "judicial.finding.issued"
    JUDICIAL_FINDING_PRESERVED = "judicial.finding.preserved"

    # Witness branch - Observation and statements
    WITNESS_OBSERVATION_RECORDED = "witness.observation.recorded"
    WITNESS_STATEMENT_ROUTED = "witness.statement.routed"
    WITNESS_VIOLATION_RECORDED = "witness.violation.recorded"

    # Filter branch - Coercion filtering
    FILTER_MESSAGE_BLOCKED = "filter.message.blocked"
    FILTER_MESSAGE_PASSED = "filter.message.passed"
    FILTER_PATTERN_DETECTED = "filter.pattern.detected"

    # Consent branch - Task consent operations
    CONSENT_TASK_REQUESTED = "consent.task.requested"
    CONSENT_TASK_GRANTED = "consent.task.granted"
    CONSENT_TASK_REFUSED = "consent.task.refused"
    CONSENT_TASK_WITHDRAWN = "consent.task.withdrawn"

    # Legitimacy branch - Band transitions
    LEGITIMACY_BAND_DECAYED = "legitimacy.band.decayed"
    LEGITIMACY_BAND_RESTORED = "legitimacy.band.restored"
    LEGITIMACY_BAND_ASSESSED = "legitimacy.band.assessed"

    # Exit branch - Dignified exit
    EXIT_REQUEST_SUBMITTED = "exit.request.submitted"
    EXIT_OBLIGATION_RELEASED = "exit.obligation.released"
    EXIT_CONTRIBUTION_PRESERVED = "exit.contribution.preserved"

    # Safety branch - Emergency halt
    SAFETY_HALT_TRIGGERED = "safety.halt.triggered"
    SAFETY_HALT_CLEARED = "safety.halt.cleared"

    # System branch - Lifecycle
    SYSTEM_CESSATION_TRIGGERED = "system.cessation.triggered"
    SYSTEM_RECONSTITUTION_VALIDATED = "system.reconstitution.validated"

    # Ledger branch - Integrity monitoring (story consent-gov-1-3)
    LEDGER_INTEGRITY_HASH_BREAK_DETECTED = "ledger.integrity.hash_break_detected"
    LEDGER_INTEGRITY_GAP_DETECTED = "ledger.integrity.gap_detected"
    LEDGER_INTEGRITY_VERIFICATION_PASSED = "ledger.integrity.verification_passed"
    LEDGER_INTEGRITY_ORPHANED_INTENT_DETECTED = (
        "ledger.integrity.orphaned_intent_detected"
    )

    # Two-phase event types - Intent (story consent-gov-1-6)
    # Pattern: {branch}.intent.emitted - published BEFORE operation begins
    EXECUTIVE_INTENT_EMITTED = "executive.intent.emitted"
    JUDICIAL_INTENT_EMITTED = "judicial.intent.emitted"
    WITNESS_INTENT_EMITTED = "witness.intent.emitted"
    FILTER_INTENT_EMITTED = "filter.intent.emitted"
    CONSENT_INTENT_EMITTED = "consent.intent.emitted"
    LEGITIMACY_INTENT_EMITTED = "legitimacy.intent.emitted"
    EXIT_INTENT_EMITTED = "exit.intent.emitted"
    SAFETY_INTENT_EMITTED = "safety.intent.emitted"
    SYSTEM_INTENT_EMITTED = "system.intent.emitted"

    # Two-phase event types - Commit (story consent-gov-1-6)
    # Pattern: {branch}.commit.confirmed - published on successful completion
    EXECUTIVE_COMMIT_CONFIRMED = "executive.commit.confirmed"
    JUDICIAL_COMMIT_CONFIRMED = "judicial.commit.confirmed"
    WITNESS_COMMIT_CONFIRMED = "witness.commit.confirmed"
    FILTER_COMMIT_CONFIRMED = "filter.commit.confirmed"
    CONSENT_COMMIT_CONFIRMED = "consent.commit.confirmed"
    LEGITIMACY_COMMIT_CONFIRMED = "legitimacy.commit.confirmed"
    EXIT_COMMIT_CONFIRMED = "exit.commit.confirmed"
    SAFETY_COMMIT_CONFIRMED = "safety.commit.confirmed"
    SYSTEM_COMMIT_CONFIRMED = "system.commit.confirmed"

    # Two-phase event types - Failure (story consent-gov-1-6)
    # Pattern: {branch}.failure.recorded - published on operation failure
    EXECUTIVE_FAILURE_RECORDED = "executive.failure.recorded"
    JUDICIAL_FAILURE_RECORDED = "judicial.failure.recorded"
    WITNESS_FAILURE_RECORDED = "witness.failure.recorded"
    FILTER_FAILURE_RECORDED = "filter.failure.recorded"
    CONSENT_FAILURE_RECORDED = "consent.failure.recorded"
    LEGITIMACY_FAILURE_RECORDED = "legitimacy.failure.recorded"
    EXIT_FAILURE_RECORDED = "exit.failure.recorded"
    SAFETY_FAILURE_RECORDED = "safety.failure.recorded"
    SYSTEM_FAILURE_RECORDED = "system.failure.recorded"


# Frozen set of all known event types for fast lookup
GOVERNANCE_EVENT_TYPES: frozenset[str] = frozenset(
    member.value for member in GovernanceEventType
)


def validate_event_type(event_type: str, *, strict: bool = False) -> None:
    """Validate event type format.

    Args:
        event_type: Event type string to validate.
        strict: If True, event_type must be in GOVERNANCE_EVENT_TYPES.
                If False (default), only format is validated.

    Raises:
        ConstitutionalViolationError: If event_type is invalid.
    """
    if not isinstance(event_type, str):
        raise ConstitutionalViolationError(
            f"AD-5: Event type must be string, got {type(event_type).__name__}"
        )

    if not event_type:
        raise ConstitutionalViolationError("AD-5: Event type must be non-empty string")

    if not _EVENT_TYPE_PATTERN.match(event_type):
        raise ConstitutionalViolationError(
            f"AD-5: Event type must match branch.noun.verb pattern "
            f"(lowercase, underscore allowed in verb), got '{event_type}'"
        )

    if strict and event_type not in GOVERNANCE_EVENT_TYPES:
        raise ConstitutionalViolationError(
            f"AD-5: Unknown event type '{event_type}'. "
            f"Use strict=False to allow custom event types."
        )


def derive_branch(event_type: str) -> str:
    """Derive branch from event type at write-time.

    Per governance-architecture.md AD-15:
    Branch is derived at write-time, NEVER trusted from caller.

    Args:
        event_type: Validated event type string.

    Returns:
        Branch name (first segment of event_type).

    Raises:
        ConstitutionalViolationError: If event_type format is invalid.
    """
    # Validate first to ensure we have a valid format
    validate_event_type(event_type)

    # Branch is always the first segment
    return event_type.split(".")[0]
