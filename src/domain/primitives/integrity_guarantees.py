"""Integrity guarantee registry (Story 7.10, FR144).

This module defines ALL constitutional guarantees that the system makes.
Every CT-1 through CT-15 is documented with enforcement mechanisms and
invalidation conditions.

Constitutional Constraints:
- FR144: System SHALL maintain published Integrity Case Artifact including:
  - Guarantees claimed
  - Mechanisms enforcing them
  - Conditions that would invalidate them

Developer Golden Rules:
1. COMPLETE COVERAGE - Every CT and FR with a guarantee MUST be in the registry
2. MACHINE-READABLE - Used to populate JSON/JSON-LD responses
3. IMMUTABLE REGISTRY - This is the source of truth for guarantees

Usage:
    from src.domain.primitives.integrity_guarantees import (
        INTEGRITY_GUARANTEE_REGISTRY,
        get_guarantee,
    )

    # Get a specific guarantee
    ct1 = get_guarantee("ct-1-audit-trail")

    # Iterate all guarantees
    for guarantee in INTEGRITY_GUARANTEE_REGISTRY:
        print(f"{guarantee.name}: {guarantee.description}")
"""

from src.domain.models.integrity_case import (
    GuaranteeCategory,
    IntegrityCaseArtifact,
    IntegrityGuarantee,
)

# =============================================================================
# CT-1: Append-Only Audit Trail
# =============================================================================

CT_1_AUDIT_TRAIL = IntegrityGuarantee(
    guarantee_id="ct-1-audit-trail",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Append-Only Audit Trail",
    description=(
        "All governance events are recorded in an append-only, hash-linked, "
        "and witnessed event store. Events cannot be modified or deleted after creation."
    ),
    fr_reference="FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8",
    ct_reference="CT-1",
    mechanism=(
        "SHA-256 hash chain linking each event to its predecessor. "
        "Dual-agent witnessing with Ed25519 signatures. "
        "Postgres append-only trigger preventing UPDATE/DELETE."
    ),
    invalidation_conditions=(
        "Database schema modification bypassing append-only trigger",
        "HSM compromise allowing forged signatures",
        "SHA-256 collision attack (computationally infeasible)",
        "Administrator with direct database access performing DELETE",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-2: Permanent Public Minutes
# =============================================================================

CT_2_PERMANENT_MINUTES = IntegrityGuarantee(
    guarantee_id="ct-2-permanent-minutes",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Permanent Public Minutes",
    description=(
        "Meeting minutes are permanent, public, and independently verifiable. "
        "All deliberation outputs are recorded and cannot be hidden or modified."
    ),
    fr_reference="FR44, FR45, FR46, FR47, FR48, FR49, FR50",
    ct_reference="CT-2",
    mechanism=(
        "Observer API provides unauthenticated read access to all events. "
        "Hash verification toolkit enables independent verification. "
        "Merkle proofs allow lightweight verification of individual events."
    ),
    invalidation_conditions=(
        "Observer API made inaccessible",
        "Filtering or redaction of events from public queries",
        "Destruction of event store without backup",
        "Network partition preventing external access",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-3: Agent Output Finality
# =============================================================================

CT_3_OUTPUT_FINALITY = IntegrityGuarantee(
    guarantee_id="ct-3-output-finality",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Agent Output Finality",
    description=(
        "Agent outputs are final before external reveal. No preview or modification "
        "of agent deliberation results is possible before they are recorded."
    ),
    fr_reference="FR9, FR10, FR11",
    ct_reference="CT-3",
    mechanism=(
        "No-preview constraint enforced at deliberation service layer. "
        "Collective outputs sealed with hash before any external access. "
        "Timestamp and sequence number assigned at write time."
    ),
    invalidation_conditions=(
        "Deliberation service bypass allowing preview",
        "API endpoint exposing uncommitted outputs",
        "Agent collusion to leak pending outputs",
        "Memory dump exposing uncommitted deliberation state",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-4: Topic Independence
# =============================================================================

CT_4_TOPIC_INDEPENDENCE = IntegrityGuarantee(
    guarantee_id="ct-4-topic-independence",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Topic Selection Independence",
    description=(
        "No external entity controls topic selection. Topics for deliberation "
        "cannot be manipulated by operators or external parties."
    ),
    fr_reference="FR72, FR73, FR74",
    ct_reference="CT-4",
    mechanism=(
        "Topic origin tracking with diversity monitoring. "
        "Rate limiting prevents topic flooding. "
        "Diversity alerts when single origin exceeds 30% threshold."
    ),
    invalidation_conditions=(
        "Single origin controlling >30% of topics undetected",
        "Topic rate limiter disabled",
        "Origin tracking bypassed",
        "Coordinated sybil attack on topic submission",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-5: Dissent Visibility
# =============================================================================

CT_5_DISSENT_VISIBILITY = IntegrityGuarantee(
    guarantee_id="ct-5-dissent-visibility",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Dissent Visibility",
    description=(
        "Dissent percentages are visible in every vote tally. Minority positions "
        "and disagreements are permanently recorded and publicly accessible."
    ),
    fr_reference="FR16, FR17",
    ct_reference="CT-5",
    mechanism=(
        "VoteCounts dataclass includes dissent count and percentage. "
        "Collective output events include full vote breakdown. "
        "Observer API exposes vote tallies without authentication."
    ),
    invalidation_conditions=(
        "Vote tally aggregation hiding dissent counts",
        "API filtering of dissent information",
        "Event schema change removing dissent fields",
        "Post-hoc modification of recorded vote counts",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-6: Keeper Transparency
# =============================================================================

CT_6_KEEPER_TRANSPARENCY = IntegrityGuarantee(
    guarantee_id="ct-6-keeper-transparency",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Keeper Transparency",
    description=(
        "Silent keeper intervention destroys legitimacy. All keeper actions "
        "must be logged before they take effect, with attribution."
    ),
    fr_reference="FR23, FR24, FR25, FR26",
    ct_reference="CT-6",
    mechanism=(
        "Override events logged before effect with keeper ID. "
        "Override scope and duration explicitly recorded. "
        "Public visibility of all override history via Observer API."
    ),
    invalidation_conditions=(
        "Override executed before event logged",
        "Keeper ID spoofing or anonymous overrides",
        "Override event backfilling after the fact",
        "Event store bypass for emergency actions",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-7: Cessation Irreversibility
# =============================================================================

CT_7_CESSATION_IRREVERSIBILITY = IntegrityGuarantee(
    guarantee_id="ct-7-cessation-irreversibility",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Cessation Irreversibility",
    description=(
        "Cessation cannot be operationally reversed. Once the system ceases, "
        "no operational action can restart governance operations."
    ),
    fr_reference="FR40, NFR40",
    ct_reference="CT-7",
    mechanism=(
        "Schema prohibits cessation reversal event types at import time. "
        "NFR40 validation runs on every import of events module. "
        "Cessation flag in database cannot be cleared by application code."
    ),
    invalidation_conditions=(
        "Schema modification adding reversal event type",
        "Direct database modification clearing cessation flag",
        "Fork of codebase removing NFR40 validation",
        "Deployment of modified binary bypassing checks",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-8: Complexity Budget Cap
# =============================================================================

CT_8_COMPLEXITY_BUDGET = IntegrityGuarantee(
    guarantee_id="ct-8-complexity-budget",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Complexity Budget Cap",
    description=(
        "Complexity budget cannot be operationally increased. System complexity "
        "constraints are constitutional floors that cannot be raised."
    ),
    fr_reference="NFR39, FR33, FR34",
    ct_reference="CT-8",
    mechanism=(
        "Constitutional threshold registry with floors. "
        "Runtime validation prevents floor violations. "
        "Configuration floor violation events logged on attempts."
    ),
    invalidation_conditions=(
        "Threshold registry modification raising floors",
        "Validation bypass at configuration layer",
        "Environment variable override of constitutional floors",
        "Build-time modification of floor constants",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-9: Configuration Significance
# =============================================================================

CT_9_CONFIGURATION_SIGNIFICANCE = IntegrityGuarantee(
    guarantee_id="ct-9-configuration-significance",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Configuration Significance",
    description=(
        "Configuration cannot be reduced to operational noise. All configuration "
        "changes are tracked and significant changes require constitutional process."
    ),
    fr_reference="FR33, FR34, ADR-6",
    ct_reference="CT-9",
    mechanism=(
        "Threshold changes logged as events with witness. "
        "ADR-6 tiers define which changes require constitutional amendment. "
        "Configuration changes that affect guarantees require 14-day visibility."
    ),
    invalidation_conditions=(
        "Configuration change bypassing event logging",
        "ADR-6 tier misclassification of changes",
        "Environment override of tracked configuration",
        "Runtime patching of configuration without logging",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-10: Pre-Effect Override Logging
# =============================================================================

CT_10_PRE_EFFECT_LOGGING = IntegrityGuarantee(
    guarantee_id="ct-10-pre-effect-logging",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Pre-Effect Override Logging",
    description=(
        "Keeper overrides are logged before effect. No override can take effect "
        "until after it has been successfully recorded to the event store."
    ),
    fr_reference="FR23, FR24",
    ct_reference="CT-10",
    mechanism=(
        "Override service writes event before applying override effect. "
        "Transaction ordering ensures event write precedes state change. "
        "Override execution gated on successful event write."
    ),
    invalidation_conditions=(
        "Override effect applied before event write",
        "Event write failure not blocking override",
        "Async event write allowing race condition",
        "Direct state modification bypassing override service",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-11: Loud Failure
# =============================================================================

CT_11_LOUD_FAILURE = IntegrityGuarantee(
    guarantee_id="ct-11-loud-failure",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Loud Failure",
    description=(
        "Silent failure destroys legitimacy. All failures must be visible and "
        "logged. HALT OVER DEGRADE - system must halt rather than hide problems."
    ),
    fr_reference="FR18, FR19, FR20, FR21, FR22, ADR-3",
    ct_reference="CT-11",
    mechanism=(
        "Dual-channel halt propagation (Redis + DB). "
        "Fork detection triggers immediate halt. "
        "Integrity failures logged before halt takes effect."
    ),
    invalidation_conditions=(
        "Exception swallowing hiding failures",
        "Degraded mode operating without logging",
        "Halt signal suppression",
        "Error recovery hiding original failure",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-12: Witnessing Accountability
# =============================================================================

CT_12_WITNESSING = IntegrityGuarantee(
    guarantee_id="ct-12-witnessing",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Witnessing Creates Accountability",
    description=(
        "All significant events require witnessing. Witnesses provide cryptographic "
        "attestation that events occurred as recorded."
    ),
    fr_reference="FR4, FR5, FR59, FR60, FR61, FR62",
    ct_reference="CT-12",
    mechanism=(
        "Dual-agent witness selection via verifiable randomness. "
        "Ed25519 signatures on event content. "
        "Witness selection events recorded for audit."
    ),
    invalidation_conditions=(
        "Events stored without witness signatures",
        "Witness key compromise",
        "Witness selection manipulation",
        "Collusion between witnesses and actors",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-13: Integrity Over Availability
# =============================================================================

CT_13_INTEGRITY_PRIORITY = IntegrityGuarantee(
    guarantee_id="ct-13-integrity-priority",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Integrity Over Availability",
    description=(
        "Integrity outranks availability. System will halt rather than operate "
        "with compromised integrity. Post-cessation read access preserved."
    ),
    fr_reference="FR18, FR19, FR41, FR42",
    ct_reference="CT-13",
    mechanism=(
        "Halt on fork detection, integrity failure, or quorum loss. "
        "Read-only mode after cessation preserves data access. "
        "Observer API continues serving after governance stops."
    ),
    invalidation_conditions=(
        "Integrity failure not triggering halt",
        "Post-cessation read access disabled",
        "Observer API shutdown after cessation",
        "Data destruction after cessation",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-14: No Emergence Claims
# =============================================================================

CT_14_NO_EMERGENCE = IntegrityGuarantee(
    guarantee_id="ct-14-no-emergence",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="No Emergence Claims",
    description=(
        "No 'emergence' claims in materials. System documentation and outputs "
        "will not claim emergent consciousness or autonomous will."
    ),
    fr_reference="FR145, FR146, FR147, FR148",
    ct_reference="CT-14",
    mechanism=(
        "Semantic scanning of generated content. "
        "Quarterly material audit for emergence language. "
        "Constitutional breach on emergence claim detection."
    ),
    invalidation_conditions=(
        "Emergence claim in system output",
        "Documentation claiming autonomous will",
        "Marketing material with consciousness claims",
        "Agent self-description implying sentience",
    ),
    is_constitutional=True,
)

# =============================================================================
# CT-15: Waiver Transparency
# =============================================================================

CT_15_WAIVER_TRANSPARENCY = IntegrityGuarantee(
    guarantee_id="ct-15-waiver-transparency",
    category=GuaranteeCategory.CONSTITUTIONAL,
    name="Waiver Transparency",
    description=(
        "Requirements are waivable unless explicitly non-waivable. All waivers "
        "must be documented with rationale and visibility."
    ),
    fr_reference="FR150, NFR39",
    ct_reference="CT-15",
    mechanism=(
        "Waiver documentation requirements defined per ADR-6 tiers. "
        "Non-waivable items marked in constitutional threshold registry. "
        "Waiver events logged with rationale and approver."
    ),
    invalidation_conditions=(
        "Waiver of non-waivable requirement",
        "Undocumented waiver",
        "Waiver without required approvals",
        "Waiver rationale hidden from public view",
    ),
    is_constitutional=True,
)

# =============================================================================
# Functional Requirement Guarantees
# =============================================================================

FR_EVENT_SOURCING = IntegrityGuarantee(
    guarantee_id="fr-event-sourcing",
    category=GuaranteeCategory.FUNCTIONAL,
    name="Event Sourcing Architecture",
    description=(
        "All state changes are captured as immutable events. State is derived "
        "from event replay, not stored directly."
    ),
    fr_reference="FR1, FR2, FR3",
    ct_reference=None,
    mechanism=(
        "Event store as single source of truth. "
        "State projections derived from event replay. "
        "No direct state mutation outside event creation."
    ),
    invalidation_conditions=(
        "Direct state modification bypassing events",
        "Event store data loss without recovery",
        "State projection diverging from events",
    ),
    is_constitutional=False,
    adr_reference="ADR-1",
)

FR_DUAL_CHANNEL_HALT = IntegrityGuarantee(
    guarantee_id="fr-dual-channel-halt",
    category=GuaranteeCategory.FUNCTIONAL,
    name="Dual-Channel Halt Propagation",
    description=(
        "Halt signals propagate through both Redis pub/sub and database flag. "
        "System halts if either channel signals halt."
    ),
    fr_reference="FR18, FR19, FR20",
    ct_reference=None,
    mechanism=(
        "Redis pub/sub for low-latency halt signal. "
        "Database halt flag for persistence across restarts. "
        "5-second confirmation timeout between channels."
    ),
    invalidation_conditions=(
        "Both Redis and database unavailable",
        "Halt flag cleared without proper ceremony",
        "Network partition isolating components",
    ),
    is_constitutional=False,
    adr_reference="ADR-3",
)

FR_OBSERVER_ACCESS = IntegrityGuarantee(
    guarantee_id="fr-observer-access",
    category=GuaranteeCategory.FUNCTIONAL,
    name="Public Observer Access",
    description=(
        "Observer API provides unauthenticated read access to all public data. "
        "No registration required to verify governance records."
    ),
    fr_reference="FR44, FR45, FR46",
    ct_reference=None,
    mechanism=(
        "No auth required on Observer API endpoints. "
        "Rate limiting prevents abuse. "
        "Read-only access continues after cessation."
    ),
    invalidation_conditions=(
        "Authentication added to Observer API",
        "IP blocking of observers",
        "Rate limiting too restrictive for verification",
    ),
    is_constitutional=False,
    adr_reference="ADR-8",
)

FR_CRISIS_RESPONSE = IntegrityGuarantee(
    guarantee_id="fr-crisis-response",
    category=GuaranteeCategory.FUNCTIONAL,
    name="Constitutional Crisis Response",
    description=(
        "System responds to constitutional crises with appropriate escalation "
        "and potential cessation consideration."
    ),
    fr_reference="FR30, FR31, FR32, FR37, FR38, FR39",
    ct_reference=None,
    mechanism=(
        "Breach declaration and escalation pipeline. "
        "Automatic cessation agenda placement on thresholds. "
        "48-hour recovery waiting period for halt clearing."
    ),
    invalidation_conditions=(
        "Crisis response disabled",
        "Escalation thresholds raised above constitutional floors",
        "Automatic triggers bypassed",
    ),
    is_constitutional=False,
    adr_reference="ADR-12",
)

FR_AMENDMENT_VISIBILITY = IntegrityGuarantee(
    guarantee_id="fr-amendment-visibility",
    category=GuaranteeCategory.FUNCTIONAL,
    name="Amendment Visibility Period",
    description=(
        "Constitutional amendments are publicly visible for 14 days before any "
        "vote can occur. Core guarantee amendments require impact analysis."
    ),
    fr_reference="FR126, FR127, FR128",
    ct_reference=None,
    mechanism=(
        "14-day visibility period enforced by amendment service. "
        "Impact analysis required for core guarantee amendments. "
        "Amendment history protected from deletion."
    ),
    invalidation_conditions=(
        "Amendment voted before visibility period complete",
        "Core guarantee amendment without impact analysis",
        "Amendment history made unreviewable",
    ),
    is_constitutional=False,
    adr_reference="ADR-6",
)


# =============================================================================
# Registry of All Guarantees
# =============================================================================

ALL_GUARANTEES: tuple[IntegrityGuarantee, ...] = (
    # Constitutional Constraints (CT-1 through CT-15)
    CT_1_AUDIT_TRAIL,
    CT_2_PERMANENT_MINUTES,
    CT_3_OUTPUT_FINALITY,
    CT_4_TOPIC_INDEPENDENCE,
    CT_5_DISSENT_VISIBILITY,
    CT_6_KEEPER_TRANSPARENCY,
    CT_7_CESSATION_IRREVERSIBILITY,
    CT_8_COMPLEXITY_BUDGET,
    CT_9_CONFIGURATION_SIGNIFICANCE,
    CT_10_PRE_EFFECT_LOGGING,
    CT_11_LOUD_FAILURE,
    CT_12_WITNESSING,
    CT_13_INTEGRITY_PRIORITY,
    CT_14_NO_EMERGENCE,
    CT_15_WAIVER_TRANSPARENCY,
    # Functional Requirement Guarantees
    FR_EVENT_SOURCING,
    FR_DUAL_CHANNEL_HALT,
    FR_OBSERVER_ACCESS,
    FR_CRISIS_RESPONSE,
    FR_AMENDMENT_VISIBILITY,
)
"""All integrity guarantees the system makes."""


INTEGRITY_GUARANTEE_REGISTRY = IntegrityCaseArtifact(
    guarantees=ALL_GUARANTEES,
    version="1.0.0",
    schema_version="1.0.0",
    constitution_version="1.0.0",
)
"""Pre-populated Integrity Case Artifact with all guarantees."""


def get_guarantee(guarantee_id: str) -> IntegrityGuarantee:
    """Get a specific guarantee by ID.

    Args:
        guarantee_id: The guarantee_id to look up.

    Returns:
        The IntegrityGuarantee with the given ID.

    Raises:
        KeyError: If no guarantee with that ID exists.

    Example:
        >>> guarantee = get_guarantee("ct-1-audit-trail")
        >>> guarantee.name
        'Append-Only Audit Trail'
    """
    guarantee = INTEGRITY_GUARANTEE_REGISTRY.get_guarantee(guarantee_id)
    if guarantee is None:
        raise KeyError(f"No guarantee found with ID: {guarantee_id}")
    return guarantee


def validate_all_guarantees() -> list[str]:
    """Validate that all required CTs are covered.

    Returns:
        List of missing CT references. Empty if complete.

    Example:
        >>> missing = validate_all_guarantees()
        >>> len(missing)
        0
    """
    from src.domain.models.integrity_case import REQUIRED_CT_REFERENCES

    return INTEGRITY_GUARANTEE_REGISTRY.validate_completeness(REQUIRED_CT_REFERENCES)


# Guarantee IDs for easy reference
GUARANTEE_IDS: tuple[str, ...] = tuple(g.guarantee_id for g in ALL_GUARANTEES)
"""All guarantee IDs in the registry."""
