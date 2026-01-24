"""Worker processes for async vote validation.

ADR-004: Single process per worker type
ADR-005: Category-specific error handling

Workers:
- ValidatorWorker: Consumes pending votes and invokes validator LLMs
- ConsensusAggregator: Tracks validator responses and determines consensus
- ValidationDispatcher: Routes validation requests to specific validators
"""

from src.workers.consensus_aggregator import (
    TOPIC_DEAD_LETTER,
    TOPIC_VALIDATED,
    ConsensusAggregator,
    ConsensusStatus,
    ValidationSource,
    ValidatorResponse,
    VoteAggregation,
    run_consensus_aggregator,
)
from src.workers.error_handler import (
    DuplicateVoteError,
    ErrorAction,
    ErrorCategory,
    ErrorDecision,
    ErrorHandler,
    IntegrityViolationError,
    InvalidMessageError,
    SchemaValidationError,
    ValidationTimeoutError,
    ValidatorRateLimitError,
    WitnessWriteError,
    categorize_error,
    register_error_category,
)
from src.workers.validation_dispatcher import (
    TOPIC_VALIDATION_REQUESTS,
    DispatchResult,
    ValidationDispatcher,
    ValidationRequest,
)
from src.workers.validator_worker import (
    TOPIC_VALIDATION_RESULTS,
    ValidationResult,
    ValidatorProtocol,
    ValidatorWorker,
    WitnessProtocol,
    run_validator_worker,
)

__all__ = [
    # Error handling
    "ErrorAction",
    "ErrorCategory",
    "ErrorDecision",
    "ErrorHandler",
    "categorize_error",
    "register_error_category",
    # Error types
    "DuplicateVoteError",
    "IntegrityViolationError",
    "InvalidMessageError",
    "SchemaValidationError",
    "ValidationTimeoutError",
    "ValidatorRateLimitError",
    "WitnessWriteError",
    # Validation Dispatcher
    "DispatchResult",
    "ValidationDispatcher",
    "ValidationRequest",
    "TOPIC_VALIDATION_REQUESTS",
    # Validator Worker
    "ValidationResult",
    "ValidatorProtocol",
    "ValidatorWorker",
    "WitnessProtocol",
    "run_validator_worker",
    "TOPIC_VALIDATION_RESULTS",
    # Consensus Aggregator
    "ConsensusAggregator",
    "ConsensusStatus",
    "ValidationSource",
    "ValidatorResponse",
    "VoteAggregation",
    "run_consensus_aggregator",
    "TOPIC_DEAD_LETTER",
    "TOPIC_VALIDATED",
]
