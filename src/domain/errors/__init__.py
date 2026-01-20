"""Domain errors for Archon 72.

Provides specific exception classes for different failure scenarios.
All exceptions inherit from ConclaveError.
"""

from src.domain.errors.agent import (
    AgentInvocationError,
    AgentNotFoundError,
    AgentPoolExhaustedError,
)
from src.domain.errors.amendment import (
    AmendmentError,
    AmendmentHistoryProtectionError,
    AmendmentImpactAnalysisMissingError,
    AmendmentNotFoundError,
    AmendmentVisibilityIncompleteError,
)
from src.domain.errors.audit import (
    AuditError,
    AuditFailedError,
    AuditInProgressError,
    AuditNotDueError,
    AuditNotFoundError,
    MaterialViolationError,
)
from src.domain.errors.audit_event import (
    AuditEventNotFoundError,
    AuditEventQueryError,
    AuditQueryTimeoutError,
    AuditTrendCalculationError,
    InsufficientAuditDataError,
)
from src.domain.errors.breach import (
    BreachDeclarationError,
    BreachError,
    BreachQueryError,
    InvalidBreachTypeError,
)
from src.domain.errors.ceased import (
    CeasedWriteAttemptError,
    SystemCeasedError,
)
from src.domain.errors.certification import (
    CertificationError,
    CertificationSignatureError,
    ResultHashMismatchError,
)
from src.domain.errors.cessation import (
    BelowThresholdError,
    CessationAlreadyTriggeredError,
    CessationConsiderationNotFoundError,
    CessationError,
    InvalidCessationDecisionError,
)
from src.domain.errors.co_sign import (
    AlreadySignedError,
    CoSignError,
    CoSignPetitionFatedError,
    CoSignPetitionNotFoundError,
)
from src.domain.errors.co_sign_rate_limit import CoSignRateLimitExceededError
from src.domain.errors.collective import FR11ViolationError
from src.domain.errors.collusion import (
    CollusionDefenseError,
    CollusionInvestigationRequiredError,
    InvestigationAlreadyResolvedError,
    InvestigationNotFoundError,
    WitnessPairPermanentlyBannedError,
    WitnessPairSuspendedError,
)
from src.domain.errors.complexity_budget import (
    ComplexityBudgetApprovalRequiredError,
    ComplexityBudgetBreachedError,
    ComplexityBudgetEscalationError,
)
from src.domain.errors.concurrent_modification import ConcurrentModificationError
from src.domain.errors.configuration_floor import (
    ConfigurationFloorEnforcementError,
    FloorModificationAttemptedError,
    RuntimeFloorViolationError,
    StartupFloorViolationError,
)
from src.domain.errors.constitutional import ConstitutionalViolationError
from src.domain.errors.constitutional_health import (
    CeremonyBlockedByConstitutionalHealthError,
    ConstitutionalHealthCheckFailedError,
    ConstitutionalHealthDegradedError,
    ConstitutionalHealthError,
)
from src.domain.errors.context_bundle import (
    BundleCreationError,
    BundleNotFoundError,
    BundleSchemaValidationError,
    ContextBundleError,
    InvalidBundleSignatureError,
    StaleBundleError,
)
from src.domain.errors.decision_package import (
    DecisionPackageError,
    DecisionPackageNotFoundError,
    ReferralNotAssignedError,
    UnauthorizedPackageAccessError,
)
from src.domain.errors.deliberation import (
    ArchonPoolExhaustedError,
    ConsensusNotReachedError,
    DeliberationError,
    IncompleteWitnessChainError,
    InvalidArchonAssignmentError,
    InvalidPetitionStateError,
    InvalidPhaseTransitionError,
    PetitionSessionMismatchError,
    PhaseExecutionError,
    PipelineRoutingError,
    SessionAlreadyCompleteError,
    SessionAlreadyExistsError,
    SessionNotFoundError,
)
from src.domain.errors.escalation import (
    BreachAlreadyAcknowledgedError,
    BreachAlreadyEscalatedError,
    BreachNotFoundError,
    EscalationError,
    EscalationTimerNotStartedError,
    InvalidAcknowledgmentError,
)
from src.domain.errors.event_emission import FateEventEmissionError
from src.domain.errors.event_store import (
    EventNotFoundError,
    EventStoreConnectionError,
    EventStoreError,
)
from src.domain.errors.failure_prevention import (
    ConstitutionalEventSheddingError,
    EarlyWarningError,
    FailureModeViolationError,
    LoadSheddingDecisionError,
    QueryPerformanceViolationError,
)
from src.domain.errors.fork_signal import (
    ForkSignalRateLimitExceededError,
    InvalidForkSignatureError,
    UnsignedForkSignalError,
)
from src.domain.errors.halt_clear import (
    HaltClearDeniedError,
    InsufficientApproversError,
    InvalidCeremonyError,
)
from src.domain.errors.hash_verification import (
    HashChainBrokenError,
    HashMismatchError,
    HashVerificationError,
    HashVerificationScanInProgressError,
    HashVerificationTimeoutError,
)
from src.domain.errors.heartbeat import AgentUnresponsiveError, HeartbeatSpoofingError
from src.domain.errors.hsm import (
    HSMError,
    HSMKeyNotFoundError,
    HSMModeViolationError,
    HSMNotConfiguredError,
)
from src.domain.errors.identity import (
    IdentityNotFoundError,
    IdentityServiceUnavailableError,
    IdentitySuspendedError,
    IdentityVerificationError,
)
from src.domain.errors.independence_attestation import (
    AttestationDeadlineMissedError,
    CapabilitySuspendedError,
    DuplicateIndependenceAttestationError,
    IndependenceAttestationError,
    InvalidIndependenceSignatureError,
)
from src.domain.errors.keeper_availability import (
    DuplicateAttestationError,
    InvalidAttestationSignatureError,
    KeeperAttestationExpiredError,
    KeeperAvailabilityError,
    KeeperQuorumViolationError,
    KeeperReplacementRequiredError,
)
from src.domain.errors.keeper_signature import (
    InvalidKeeperSignatureError,
    KeeperKeyAlreadyExistsError,
    KeeperKeyExpiredError,
    KeeperKeyNotFoundError,
    KeeperSignatureError,
)
from src.domain.errors.key_generation_ceremony import (
    CeremonyConflictError,
    CeremonyError,
    CeremonyNotFoundError,
    CeremonyTimeoutError,
    DuplicateWitnessError,
    InsufficientWitnessesError,
    InvalidCeremonyStateError,
)
from src.domain.errors.knight_concurrent_limit import (
    KnightAtCapacityError,
    KnightNotFoundError,
    KnightNotInRealmError,
    NoEligibleKnightsError,
    ReferralAlreadyAssignedError,
)
from src.domain.errors.override import (
    DurationValidationError,
    InvalidOverrideReasonError,
    OverrideBlockedError,
    OverrideLoggingFailedError,
    WitnessSuppressionAttemptError,
)
from src.domain.errors.override_abuse import (
    ConstitutionalConstraintViolationError,
    EvidenceDestructionAttemptError,
    HistoryEditAttemptError,
    OverrideAbuseError,
)
from src.domain.errors.petition import (
    DuplicateCosignatureError,
    InvalidSignatureError,
    PetitionAlreadyExistsError,
    PetitionClosedError,
    PetitionError,
    PetitionNotFoundError,
)
from src.domain.errors.pre_operational import (
    BypassNotAllowedError,
    PostHaltVerificationRequiredError,
    PreOperationalVerificationError,
    VerificationCheckError,
)
from src.domain.errors.prohibited_language import (
    ProhibitedLanguageBlockedError,
    ProhibitedLanguageError,
    ProhibitedLanguageScanError,
    ProhibitedTermsConfigurationError,
)
from src.domain.errors.publication import (
    PublicationBlockedError,
    PublicationError,
    PublicationNotFoundError,
    PublicationScanError,
    PublicationValidationError,
)
from src.domain.errors.queue_overflow import QueueOverflowError
from src.domain.errors.rate_limit import RateLimitExceededError
from src.domain.errors.read_only import (
    ProvisionalBlockedDuringHaltError,
    WriteBlockedDuringHaltError,
)
from src.domain.errors.recommendation import (
    InvalidRecommendationError,
    RecommendationAlreadySubmittedError,
    RecommendationError,
    ReferralNotInReviewError,
    UnauthorizedRecommendationError,
)
from src.domain.errors.recommendation import (
    RationaleRequiredError as RecommendationRationaleRequiredError,
)
from src.domain.errors.recovery import (
    RecoveryAlreadyInProgressError,
    RecoveryNotPermittedError,
    RecoveryWaitingPeriodNotElapsedError,
    RecoveryWaitingPeriodNotStartedError,
)
from src.domain.errors.referral import (
    ExtensionReasonRequiredError,
    InvalidRealmError,
    InvalidReferralStateError,
    MaxExtensionsReachedError,
    NotAssignedKnightError,
    PetitionNotReferrableError,
    ReferralAlreadyExistsError,
    ReferralError,
    ReferralJobSchedulingError,
    ReferralNotFoundError,
    ReferralWitnessHashError,
)
from src.domain.errors.rollback import (
    CheckpointNotFoundError,
    InvalidRollbackTargetError,
    RollbackAlreadyInProgressError,
    RollbackNotPermittedError,
)
from src.domain.errors.schema_irreversibility import (
    CessationReversalAttemptError,
    EventTypeProhibitedError,
    SchemaIrreversibilityError,
    TerminalEventViolationError,
)
from src.domain.errors.semantic_violation import (
    SemanticScanError,
    SemanticViolationError,
    SemanticViolationSuspectedError,
)
from src.domain.errors.separation import (
    ConstitutionalToOperationalError,
    OperationalToEventStoreError,
    SeparationViolationError,
)
from src.domain.errors.sequence_gap import (
    SequenceGapDetectedError,
    SequenceGapResolutionRequiredError,
)
from src.domain.errors.silent_edit import FR13ViolationError
from src.domain.errors.state_transition import (
    InvalidStateTransitionError,
    PetitionAlreadyFatedError,
)
from src.domain.errors.threshold import (
    ConstitutionalFloorViolationError,
    CounterResetAttemptedError,
    ThresholdError,
    ThresholdNotFoundError,
)
from src.domain.errors.topic import TopicDiversityViolationError, TopicRateLimitError
from src.domain.errors.topic_manipulation import (
    DailyRateLimitExceededError,
    PredictableSeedError,
    SeedSourceDependenceError,
    TopicManipulationDefenseError,
)
from src.domain.errors.trend import (
    InsufficientDataError,
    TrendAnalysisError,
)
from src.domain.errors.user_content import (
    UserContentCannotBeFeaturedException,
    UserContentFlagClearError,
    UserContentNotFoundError,
    UserContentProhibitionError,
)
from src.domain.errors.witness import (
    NoWitnessAvailableError,
    WitnessNotFoundError,
    WitnessSigningError,
)
from src.domain.errors.witness_anomaly import (
    AnomalyScanError,
    WitnessAnomalyError,
    WitnessCollusionSuspectedError,
    WitnessPairExcludedError,
    WitnessPoolDegradedError,
    WitnessUnavailabilityPatternError,
)
from src.domain.errors.witness_selection import (
    AllWitnessesPairExhaustedError,
    EntropyUnavailableError,
    InsufficientWitnessPoolError,
    WitnessPairRotationViolationError,
    WitnessSelectionError,
    WitnessSelectionVerificationError,
)
from src.domain.errors.writer import (
    SystemHaltedError,
    WriterInconsistencyError,
    WriterLockNotHeldError,
    WriterNotVerifiedError,
)

__all__: list[str] = [
    "AgentInvocationError",
    "AgentNotFoundError",
    "AgentPoolExhaustedError",
    "AgentUnresponsiveError",
    "ConstitutionalViolationError",
    "EventStoreError",
    "EventNotFoundError",
    "EventStoreConnectionError",
    "HeartbeatSpoofingError",
    "HSMError",
    "HSMKeyNotFoundError",
    "HSMModeViolationError",
    "HSMNotConfiguredError",
    "NoWitnessAvailableError",
    "WitnessSigningError",
    "WitnessNotFoundError",
    "SystemHaltedError",
    "WriterInconsistencyError",
    "WriterLockNotHeldError",
    "WriterNotVerifiedError",
    "FR11ViolationError",
    "FR13ViolationError",
    "TopicDiversityViolationError",
    "TopicRateLimitError",
    "CertificationError",
    "CertificationSignatureError",
    "ResultHashMismatchError",
    "BundleCreationError",
    "BundleNotFoundError",
    "BundleSchemaValidationError",
    "ContextBundleError",
    "InvalidBundleSignatureError",
    "StaleBundleError",
    "HaltClearDeniedError",
    "InsufficientApproversError",
    "InvalidCeremonyError",
    "ProvisionalBlockedDuringHaltError",
    "RecoveryAlreadyInProgressError",
    "RecoveryNotPermittedError",
    "RecoveryWaitingPeriodNotElapsedError",
    "RecoveryWaitingPeriodNotStartedError",
    "SequenceGapDetectedError",
    "SequenceGapResolutionRequiredError",
    "ForkSignalRateLimitExceededError",
    "InvalidForkSignatureError",
    "UnsignedForkSignalError",
    "WriteBlockedDuringHaltError",
    "CheckpointNotFoundError",
    "InvalidRollbackTargetError",
    "RollbackAlreadyInProgressError",
    "RollbackNotPermittedError",
    "OverrideBlockedError",
    "OverrideLoggingFailedError",
    "DurationValidationError",
    "InvalidOverrideReasonError",
    "WitnessSuppressionAttemptError",
    "TrendAnalysisError",
    "InsufficientDataError",
    "InvalidKeeperSignatureError",
    "KeeperKeyAlreadyExistsError",
    "KeeperKeyExpiredError",
    "KeeperKeyNotFoundError",
    "KeeperSignatureError",
    "CeremonyError",
    "CeremonyNotFoundError",
    "InvalidCeremonyStateError",
    "InsufficientWitnessesError",
    "CeremonyTimeoutError",
    "CeremonyConflictError",
    "DuplicateWitnessError",
    "DuplicateAttestationError",
    "InvalidAttestationSignatureError",
    "KeeperAttestationExpiredError",
    "KeeperAvailabilityError",
    "KeeperQuorumViolationError",
    "KeeperReplacementRequiredError",
    "OverrideAbuseError",
    "HistoryEditAttemptError",
    "EvidenceDestructionAttemptError",
    "ConstitutionalConstraintViolationError",
    "IndependenceAttestationError",
    "AttestationDeadlineMissedError",
    "DuplicateIndependenceAttestationError",
    "InvalidIndependenceSignatureError",
    "CapabilitySuspendedError",
    "BreachError",
    "BreachDeclarationError",
    "InvalidBreachTypeError",
    "BreachQueryError",
    "EscalationError",
    "BreachNotFoundError",
    "BreachAlreadyAcknowledgedError",
    "BreachAlreadyEscalatedError",
    "InvalidAcknowledgmentError",
    "EscalationTimerNotStartedError",
    "CessationError",
    "CessationAlreadyTriggeredError",
    "CessationConsiderationNotFoundError",
    "InvalidCessationDecisionError",
    "BelowThresholdError",
    "ThresholdError",
    "ConstitutionalFloorViolationError",
    "ThresholdNotFoundError",
    "CounterResetAttemptedError",
    "WitnessSelectionError",
    "EntropyUnavailableError",
    "WitnessPairRotationViolationError",
    "WitnessSelectionVerificationError",
    "InsufficientWitnessPoolError",
    "AllWitnessesPairExhaustedError",
    "WitnessAnomalyError",
    "WitnessCollusionSuspectedError",
    "WitnessPairExcludedError",
    "WitnessUnavailabilityPatternError",
    "WitnessPoolDegradedError",
    "AnomalyScanError",
    "AmendmentError",
    "AmendmentHistoryProtectionError",
    "AmendmentImpactAnalysisMissingError",
    "AmendmentNotFoundError",
    "AmendmentVisibilityIncompleteError",
    # Collusion errors (Story 6.8, FR124)
    "CollusionDefenseError",
    "CollusionInvestigationRequiredError",
    "InvestigationAlreadyResolvedError",
    "InvestigationNotFoundError",
    "WitnessPairPermanentlyBannedError",
    "WitnessPairSuspendedError",
    # Hash verification errors (Story 6.8, FR125)
    "HashChainBrokenError",
    "HashMismatchError",
    "HashVerificationError",
    "HashVerificationScanInProgressError",
    "HashVerificationTimeoutError",
    # Topic manipulation errors (Story 6.9, FR118, FR124)
    "DailyRateLimitExceededError",
    "PredictableSeedError",
    "SeedSourceDependenceError",
    "TopicManipulationDefenseError",
    # Configuration floor errors (Story 6.10, NFR39)
    "ConfigurationFloorEnforcementError",
    "FloorModificationAttemptedError",
    "RuntimeFloorViolationError",
    "StartupFloorViolationError",
    # Petition errors (Story 7.2, FR39)
    "PetitionError",
    "InvalidSignatureError",
    "DuplicateCosignatureError",
    "PetitionNotFoundError",
    "PetitionClosedError",
    "PetitionAlreadyExistsError",
    # Schema irreversibility errors (Story 7.3, FR40, NFR40)
    "SchemaIrreversibilityError",
    "EventTypeProhibitedError",
    "TerminalEventViolationError",
    "CessationReversalAttemptError",
    # Cessation freeze errors (Story 7.4, FR41)
    "SystemCeasedError",
    "CeasedWriteAttemptError",
    # Separation errors (Story 8.2, FR52)
    "SeparationViolationError",
    "OperationalToEventStoreError",
    "ConstitutionalToOperationalError",
    # Pre-operational verification errors (Story 8.5, FR146, NFR35)
    "BypassNotAllowedError",
    "PostHaltVerificationRequiredError",
    "PreOperationalVerificationError",
    "VerificationCheckError",
    # Complexity budget errors (Story 8.6, SC-3, RT-6)
    "ComplexityBudgetApprovalRequiredError",
    "ComplexityBudgetBreachedError",
    "ComplexityBudgetEscalationError",
    # Failure prevention errors (Story 8.8, FR106-FR107)
    "ConstitutionalEventSheddingError",
    "EarlyWarningError",
    "FailureModeViolationError",
    "LoadSheddingDecisionError",
    "QueryPerformanceViolationError",
    # Constitutional health errors (Story 8.10, ADR-10)
    "CeremonyBlockedByConstitutionalHealthError",
    "ConstitutionalHealthCheckFailedError",
    "ConstitutionalHealthDegradedError",
    "ConstitutionalHealthError",
    # Prohibited language errors (Story 9.1, FR55)
    "ProhibitedLanguageBlockedError",
    "ProhibitedLanguageError",
    "ProhibitedLanguageScanError",
    "ProhibitedTermsConfigurationError",
    # Publication errors (Story 9.2, FR56)
    "PublicationBlockedError",
    "PublicationError",
    "PublicationNotFoundError",
    "PublicationScanError",
    "PublicationValidationError",
    # Audit errors (Story 9.3, FR57)
    "AuditError",
    "AuditFailedError",
    "AuditInProgressError",
    "AuditNotDueError",
    "AuditNotFoundError",
    "MaterialViolationError",
    # User content prohibition errors (Story 9.4, FR58)
    "UserContentCannotBeFeaturedException",
    "UserContentFlagClearError",
    "UserContentNotFoundError",
    "UserContentProhibitionError",
    # Audit event query errors (Story 9.5, FR108)
    "AuditEventNotFoundError",
    "AuditEventQueryError",
    "AuditQueryTimeoutError",
    "AuditTrendCalculationError",
    "InsufficientAuditDataError",
    # Semantic violation errors (Story 9.7, FR110)
    "SemanticScanError",
    "SemanticViolationError",
    "SemanticViolationSuspectedError",
    # Queue overflow errors (Story 1.3, FR-1.4)
    "QueueOverflowError",
    # Rate limit errors (Story 1.4, FR-1.5, HC-4)
    "RateLimitExceededError",
    # State transition errors (Story 1.5, FR-2.1, FR-2.3, FR-2.6)
    "InvalidStateTransitionError",
    "PetitionAlreadyFatedError",
    # Concurrent modification error (Story 1.6, FR-2.4, NFR-3.2)
    "ConcurrentModificationError",
    # Event emission error (Story 1.7, FR-2.5, HC-1)
    "FateEventEmissionError",
    # Deliberation errors (Story 2A.1, FR-11.1, FR-11.4, Story 2A.5, Story 2A.8, Story 2B.2)
    "ArchonPoolExhaustedError",
    "ConsensusNotReachedError",
    "DeliberationError",
    "IncompleteWitnessChainError",
    "InvalidArchonAssignmentError",
    "InvalidPetitionStateError",
    "InvalidPhaseTransitionError",
    "PetitionSessionMismatchError",
    "PhaseExecutionError",
    "PipelineRoutingError",
    "SessionAlreadyCompleteError",
    "SessionAlreadyExistsError",
    "SessionNotFoundError",
    # Referral errors (Story 4.2, FR-4.1, FR-4.2)
    "InvalidRealmError",
    "PetitionNotReferrableError",
    "ReferralAlreadyExistsError",
    "ReferralError",
    "ReferralJobSchedulingError",
    "ReferralNotFoundError",
    "ReferralWitnessHashError",
    # Extension errors (Story 4.5, FR-4.4)
    "ExtensionReasonRequiredError",
    "InvalidReferralStateError",
    "MaxExtensionsReachedError",
    "NotAssignedKnightError",
    # Decision package errors (Story 4.3, FR-4.3, NFR-5.2)
    "DecisionPackageError",
    "DecisionPackageNotFoundError",
    "ReferralNotAssignedError",
    "UnauthorizedPackageAccessError",
    # Recommendation errors (Story 4.4, FR-4.6, NFR-5.2)
    "InvalidRecommendationError",
    "RecommendationAlreadySubmittedError",
    "RecommendationError",
    "RecommendationRationaleRequiredError",
    "ReferralNotInReviewError",
    "UnauthorizedRecommendationError",
    # Knight concurrent limit errors (Story 4.7, FR-4.7, NFR-7.3)
    "KnightAtCapacityError",
    "KnightNotFoundError",
    "KnightNotInRealmError",
    "NoEligibleKnightsError",
    "ReferralAlreadyAssignedError",
    # Co-sign errors (Story 5.2, FR-6.1, FR-6.2, FR-6.3, NFR-3.5)
    "AlreadySignedError",
    "CoSignError",
    "CoSignPetitionFatedError",
    "CoSignPetitionNotFoundError",
    # Identity verification errors (Story 5.3, NFR-5.2, LEGIT-1)
    "IdentityNotFoundError",
    "IdentityServiceUnavailableError",
    "IdentitySuspendedError",
    "IdentityVerificationError",
    # Co-sign rate limit errors (Story 5.4, FR-6.6, SYBIL-1)
    "CoSignRateLimitExceededError",
]
