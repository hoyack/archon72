"""Admission Gate Service for Motion validation.

The Admission Gate evaluates Motions (not Seeds) before they can enter the
agenda-eligible queue. This is the key control point for "Speech is unlimited.
Agenda is scarce."

Validation Levels (from Motion Gates spec):
1. Structural: Required fields present
2. Standing: Sponsor is King, realm matches
3. Content: WHAT defined, no HOW in normative fields
4. Ambiguity: No "as needed", "TBD" in action-bearing fields
5. Scope: Single primary_realm or explicit cross-realm co-sponsors

Hardening (Motion Gates Hardening Spec):
- H4: Cross-realm escalation - 4+ realms requires Council Head approval

Constitutional Constraints:
- I1: No Silent Loss - all rejections recorded with reason codes
- I3: Admission Gate applies to Motions only (not Seeds)
- I4: Anti-forgery - invalid artifacts recorded as malformed
- D4: No Silent Rewrite - gate MUST NOT modify content
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.application.services.base import LoggingMixin
from src.domain.models.motion_seed import (
    KING_IDS,
    VALID_REALMS,
    AdmissionRejectReason,
    AdmissionRecord,
    AdmissionStatus,
    get_king_realm,
    is_king,
    validate_king_realm_match,
)


@dataclass
class MotionCandidate:
    """A Motion candidate submitted for admission gate evaluation.

    This is the input format for the gate. It mirrors Motion structure
    but is evaluated before becoming a valid Motion.
    """

    motion_id: str
    title: str
    realm_assignment: dict[str, Any]  # Contains primary_realm, primary_sponsor, etc.
    normative_intent: str  # WHAT - normative intent
    constraints: str  # WHAT-level guardrails
    success_criteria: str
    submitted_at: datetime
    source_seed_refs: list[str]  # Seed IDs for provenance

    # Optional fields
    co_sponsors: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# Patterns that indicate HOW (implementation detail) rather than WHAT (normative intent)
HOW_INDICATORS = [
    # Technical implementation
    r"\bapi\s+endpoint",
    r"\bdatabase\s+schema",
    r"\bjson\s+format",
    r"\bsql\s+query",
    r"\brest\s+api",
    r"\bhttp\s+request",
    r"\bimplementation\s+steps",
    r"\btechnical\s+design",
    r"\bcode\s+changes",
    r"\bfile\s+path",
    r"\bmodule\s+name",
    r"\bclass\s+name",
    r"\bfunction\s+name",
    # Procedural detail
    r"\bfirst,?\s+then",
    r"\bstep\s+\d+",
    r"\bprocedure:",
    r"\balgorithm:",
    # Architecture specifics
    r"\bmicroservice",
    r"\bcontainer",
    r"\bdeployment",
    r"\binfrastructure",
    r"\bkubernetes",
    r"\bdocker",
]

# Patterns that indicate ambiguity in action-bearing fields
AMBIGUITY_INDICATORS = [
    r"\bas\s+needed",
    r"\btbd\b",
    r"\bto\s+be\s+determined",
    r"\bet\s+cetera",
    r"\betc\.?\b",
    r"\bwhatever",
    r"\bsomehow",
    r"\bunspecified",
    r"\bundefined",
    r"\bpending\s+decision",
    r"\bfuture\s+discussion",
]

# Compile patterns for efficiency
HOW_PATTERNS = [re.compile(p, re.IGNORECASE) for p in HOW_INDICATORS]
AMBIGUITY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in AMBIGUITY_INDICATORS]

# H4: Cross-realm escalation threshold
# Motions spanning this many or more realms require Council Head approval
CROSS_REALM_ESCALATION_THRESHOLD = 4


class AdmissionGateService(LoggingMixin):
    """Service for evaluating Motion admission.

    The gate validates Motions against structural, standing, content,
    ambiguity, and scope requirements before they can enter the agenda queue.

    The gate MUST NOT modify Motion content (D4: No Silent Rewrite).
    All rejections MUST be recorded with explicit reason codes (I1: No Silent Loss).
    """

    def __init__(self) -> None:
        """Initialize the Admission Gate service."""
        self._init_logger(component="motion_gates")

    def evaluate(self, candidate: MotionCandidate) -> AdmissionRecord:
        """Evaluate a Motion candidate for admission.

        Runs all validation levels in order:
        1. Structural validation
        2. Standing validation
        3. Content validation
        4. Ambiguity validation
        5. Scope validation

        Args:
            candidate: The Motion candidate to evaluate

        Returns:
            AdmissionRecord with status and any rejection reasons
        """
        log = self._log_operation("evaluate", motion_id=candidate.motion_id)
        log.info("admission_gate_started")

        record = AdmissionRecord.create(
            motion_id=candidate.motion_id,
            status=AdmissionStatus.PENDING,
        )

        # Run all validations
        self._validate_structural(candidate, record)
        self._validate_standing(candidate, record)
        self._validate_content(candidate, record)
        self._validate_ambiguity(candidate, record)
        self._validate_scope(candidate, record)

        # Determine final status
        if record.rejection_reasons:
            record.status = AdmissionStatus.REJECTED
            log.warning(
                "admission_rejected",
                reasons=[r.value for r in record.rejection_reasons],
                count=len(record.rejection_reasons),
            )
        else:
            record.status = AdmissionStatus.ADMITTED
            log.info("admission_granted")

        return record

    def _validate_structural(
        self, candidate: MotionCandidate, record: AdmissionRecord
    ) -> None:
        """Validate structural requirements (required fields)."""
        log = self._log_operation("validate_structural", motion_id=candidate.motion_id)

        # Check title
        if not candidate.title or not candidate.title.strip():
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_TITLE,
                "Motion must have a non-empty title",
            )
            log.debug("structural_failed", field="title")

        # Check normative_intent
        if not candidate.normative_intent or not candidate.normative_intent.strip():
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_NORMATIVE_INTENT,
                "Motion must define normative intent (WHAT)",
            )
            log.debug("structural_failed", field="normative_intent")

        # Check success_criteria
        if not candidate.success_criteria or not candidate.success_criteria.strip():
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_SUCCESS_CRITERIA,
                "Motion must define success criteria",
            )
            log.debug("structural_failed", field="success_criteria")

        # Check realm_assignment
        realm = candidate.realm_assignment
        if not realm:
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_REALM_ASSIGNMENT,
                "Motion must have realm assignment",
            )
            log.debug("structural_failed", field="realm_assignment")
        elif not realm.get("primary_realm"):
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_REALM_ASSIGNMENT,
                "Motion must have primary_realm in realm_assignment",
            )
            log.debug("structural_failed", field="primary_realm")
        elif not realm.get("primary_sponsor_id"):
            record.structural_valid = False
            record.add_rejection(
                AdmissionRejectReason.MISSING_SPONSOR,
                "Motion must have primary_sponsor_id in realm_assignment",
            )
            log.debug("structural_failed", field="primary_sponsor_id")

    def _validate_standing(
        self, candidate: MotionCandidate, record: AdmissionRecord
    ) -> None:
        """Validate sponsor standing (King check, realm match)."""
        log = self._log_operation("validate_standing", motion_id=candidate.motion_id)

        realm = candidate.realm_assignment
        if not realm:
            return  # Already caught by structural validation

        sponsor_id = realm.get("primary_sponsor_id")
        primary_realm = realm.get("primary_realm")

        # Check sponsor is a King
        if sponsor_id and not is_king(sponsor_id):
            record.standing_valid = False
            record.add_rejection(
                AdmissionRejectReason.SPONSOR_NOT_KING,
                f"Primary sponsor {sponsor_id} is not a King. Only Kings may introduce Motions.",
            )
            log.debug("standing_failed", reason="not_king", sponsor_id=sponsor_id)
            return

        # Check sponsor owns the realm
        if sponsor_id and primary_realm:
            if not validate_king_realm_match(sponsor_id, primary_realm):
                record.standing_valid = False
                king_realm = get_king_realm(sponsor_id)
                record.add_rejection(
                    AdmissionRejectReason.SPONSOR_WRONG_REALM,
                    f"King {sponsor_id} owns realm {king_realm}, not {primary_realm}",
                )
                log.debug(
                    "standing_failed",
                    reason="wrong_realm",
                    sponsor_id=sponsor_id,
                    primary_realm=primary_realm,
                    king_realm=king_realm,
                )

        # Check co-sponsors for cross-realm motions
        if candidate.co_sponsors:
            for cosponsor in candidate.co_sponsors:
                cosponsor_id = cosponsor.get("king_id")
                cosponsor_realm = cosponsor.get("realm_id")

                if cosponsor_id and not is_king(cosponsor_id):
                    record.standing_valid = False
                    record.add_rejection(
                        AdmissionRejectReason.INVALID_COSPONSOR,
                        f"Co-sponsor {cosponsor_id} is not a King",
                    )
                    log.debug(
                        "standing_failed",
                        reason="invalid_cosponsor",
                        cosponsor_id=cosponsor_id,
                    )

                if cosponsor_id and cosponsor_realm:
                    if not validate_king_realm_match(cosponsor_id, cosponsor_realm):
                        record.standing_valid = False
                        record.add_rejection(
                            AdmissionRejectReason.INVALID_COSPONSOR,
                            f"Co-sponsor {cosponsor_id} does not own realm {cosponsor_realm}",
                        )
                        log.debug(
                            "standing_failed",
                            reason="cosponsor_wrong_realm",
                            cosponsor_id=cosponsor_id,
                            cosponsor_realm=cosponsor_realm,
                        )

    def _validate_content(
        self, candidate: MotionCandidate, record: AdmissionRecord
    ) -> None:
        """Validate content (WHAT vs HOW in normative fields)."""
        log = self._log_operation("validate_content", motion_id=candidate.motion_id)

        # Check normative_intent for HOW content
        how_matches = self._find_how_patterns(candidate.normative_intent)
        if how_matches:
            record.content_valid = False
            record.add_rejection(
                AdmissionRejectReason.HOW_IN_NORMATIVE_INTENT,
                f"normative_intent contains implementation details (HOW): {', '.join(how_matches[:3])}",
            )
            log.debug(
                "content_failed",
                field="normative_intent",
                how_patterns=how_matches[:3],
            )

        # Check constraints for HOW content
        if candidate.constraints:
            how_matches = self._find_how_patterns(candidate.constraints)
            if how_matches:
                record.content_valid = False
                record.add_rejection(
                    AdmissionRejectReason.HOW_IN_CONSTRAINTS,
                    f"constraints contains implementation details (HOW): {', '.join(how_matches[:3])}",
                )
                log.debug(
                    "content_failed",
                    field="constraints",
                    how_patterns=how_matches[:3],
                )

        # Check success_criteria for HOW content
        how_matches = self._find_how_patterns(candidate.success_criteria)
        if how_matches:
            record.content_valid = False
            record.add_rejection(
                AdmissionRejectReason.HOW_IN_SUCCESS_CRITERIA,
                f"success_criteria contains implementation details (HOW): {', '.join(how_matches[:3])}",
            )
            log.debug(
                "content_failed",
                field="success_criteria",
                how_patterns=how_matches[:3],
            )

    def _validate_ambiguity(
        self, candidate: MotionCandidate, record: AdmissionRecord
    ) -> None:
        """Validate ambiguity (no 'as needed', 'TBD' in action-bearing fields)."""
        log = self._log_operation("validate_ambiguity", motion_id=candidate.motion_id)

        # Check normative_intent for ambiguity
        ambiguity_matches = self._find_ambiguity_patterns(candidate.normative_intent)
        if ambiguity_matches:
            record.ambiguity_valid = False
            record.add_rejection(
                AdmissionRejectReason.AMBIGUOUS_SCOPE,
                f"normative_intent contains ambiguous terms: {', '.join(ambiguity_matches[:3])}",
            )
            log.debug(
                "ambiguity_failed",
                field="normative_intent",
                patterns=ambiguity_matches[:3],
            )

        # Check success_criteria for ambiguity
        ambiguity_matches = self._find_ambiguity_patterns(candidate.success_criteria)
        if ambiguity_matches:
            record.ambiguity_valid = False
            record.add_rejection(
                AdmissionRejectReason.AMBIGUOUS_SCOPE,
                f"success_criteria contains ambiguous terms: {', '.join(ambiguity_matches[:3])}",
            )
            log.debug(
                "ambiguity_failed",
                field="success_criteria",
                patterns=ambiguity_matches[:3],
            )

    def _validate_scope(
        self, candidate: MotionCandidate, record: AdmissionRecord
    ) -> None:
        """Validate scope (single primary_realm or explicit cross-realm).

        H4 Escalation Policy: Motions spanning 4+ realms are REJECTED with
        requires_escalation=True. This prevents automatic admission of broad
        cross-realm motions that could affect multiple governance domains.

        The requires_escalation flag indicates the motion needs Council Head
        review and can be resubmitted with explicit approval. Future enhancement
        could implement a DEFERRED status with approval workflow.
        """
        log = self._log_operation("validate_scope", motion_id=candidate.motion_id)

        realm = candidate.realm_assignment
        if not realm:
            return

        primary_realm = realm.get("primary_realm")

        # Validate realm is known
        if primary_realm and primary_realm not in VALID_REALMS:
            record.scope_valid = False
            record.add_rejection(
                AdmissionRejectReason.CONFLICTING_REALMS,
                f"Unknown realm: {primary_realm}. Must be one of the 9 defined realms.",
            )
            log.debug("scope_failed", reason="unknown_realm", realm=primary_realm)

        # If claiming cross-realm, must have co-sponsors for each additional realm
        if candidate.co_sponsors:
            claimed_realms = {primary_realm}
            for cosponsor in candidate.co_sponsors:
                cosponsor_realm = cosponsor.get("realm_id")
                if cosponsor_realm:
                    if cosponsor_realm not in VALID_REALMS:
                        record.scope_valid = False
                        record.add_rejection(
                            AdmissionRejectReason.CONFLICTING_REALMS,
                            f"Unknown co-sponsor realm: {cosponsor_realm}",
                        )
                        log.debug(
                            "scope_failed",
                            reason="unknown_cosponsor_realm",
                            realm=cosponsor_realm,
                        )
                    claimed_realms.add(cosponsor_realm)

            # H4: Escalation for motions spanning 4+ realms
            if len(claimed_realms) >= CROSS_REALM_ESCALATION_THRESHOLD:
                record.scope_valid = False
                record.add_rejection(
                    AdmissionRejectReason.EXCESSIVE_REALM_SPAN,
                    f"Motion spans {len(claimed_realms)} realms (threshold: {CROSS_REALM_ESCALATION_THRESHOLD}). "
                    f"Requires Council Head approval for cross-realm escalation (H4).",
                )
                record.requires_escalation = True
                record.escalation_realm_count = len(claimed_realms)
                log.info(
                    "h4_escalation_required",
                    realm_count=len(claimed_realms),
                    threshold=CROSS_REALM_ESCALATION_THRESHOLD,
                )
            elif len(claimed_realms) > 2:
                # Warning for 3 realms (below threshold but notable)
                record.warnings.append(
                    f"Motion spans {len(claimed_realms)} realms - approaching escalation threshold"
                )
                log.debug("scope_warning", realm_count=len(claimed_realms))

    def _find_how_patterns(self, text: str) -> list[str]:
        """Find HOW pattern matches in text."""
        if not text:
            return []
        matches = []
        for pattern in HOW_PATTERNS:
            if pattern.search(text):
                matches.append(pattern.pattern)
        return matches

    def _find_ambiguity_patterns(self, text: str) -> list[str]:
        """Find ambiguity pattern matches in text."""
        if not text:
            return []
        matches = []
        for pattern in AMBIGUITY_PATTERNS:
            if pattern.search(text):
                matches.append(pattern.pattern)
        return matches

    def defer(
        self,
        motion_id: str,
        reason: str,
        until: datetime | None = None,
    ) -> AdmissionRecord:
        """Defer a Motion for quota or capacity reasons.

        Args:
            motion_id: The Motion ID
            reason: Reason for deferral
            until: Optional datetime when to reconsider

        Returns:
            AdmissionRecord with DEFERRED status
        """
        log = self._log_operation("defer", motion_id=motion_id)

        record = AdmissionRecord.create(
            motion_id=motion_id,
            status=AdmissionStatus.DEFERRED,
        )
        record.deferred_reason = reason
        record.deferred_until = until

        log.info("admission_deferred", reason=reason)
        return record
