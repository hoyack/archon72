"""Application DTOs (Data Transfer Objects).

These DTOs are used for data transfer within the application layer
and across layer boundaries. They are distinct from:
- Domain models (immutable business objects)
- API models (Pydantic models for serialization)
- Infrastructure models (database schemas, etc.)

Architecture Note:
The application layer defines its own DTOs to maintain independence
from the API layer. This module exports both:
1. Dataclass-based DTOs (with DTO suffix) - for internal use
2. Pydantic models (no suffix) - shared with API layer

API routes import Pydantic models from here, ensuring dependencies
flow inward (API -> Application), not outward.
"""

from src.application.dtos.export import AttestationMetadataDTO, ExportFormatDTO
from src.application.dtos.health import (
    DependencyCheckDTO,
    HealthResponseDTO,
    ReadyResponseDTO,
)
from src.application.dtos.observer import (
    # Dataclass DTOs (internal use)
    CheckpointAnchorDTO,
    HashChainProofDTO,
    HashChainProofEntryDTO,
    MerkleProofDTO,
    MerkleProofEntryDTO,
    NotificationEventTypeDTO,
    NotificationPayloadDTO,
    WebhookSubscriptionDTO,
    WebhookSubscriptionResponseDTO,
    # Pydantic models (shared with API)
    CheckpointAnchor,
    HashChainProof,
    HashChainProofEntry,
    MerkleProof,
    MerkleProofEntry,
    NotificationEventType,
    NotificationPayload,
    WebhookSubscription,
    WebhookSubscriptionResponse,
)

__all__ = [
    # Dataclass DTOs
    "AttestationMetadataDTO",
    "CheckpointAnchorDTO",
    "DependencyCheckDTO",
    "ExportFormatDTO",
    "HashChainProofDTO",
    "HashChainProofEntryDTO",
    "HealthResponseDTO",
    "MerkleProofDTO",
    "MerkleProofEntryDTO",
    "NotificationEventTypeDTO",
    "NotificationPayloadDTO",
    "ReadyResponseDTO",
    "WebhookSubscriptionDTO",
    "WebhookSubscriptionResponseDTO",
    # Pydantic models (shared with API)
    "CheckpointAnchor",
    "HashChainProof",
    "HashChainProofEntry",
    "MerkleProof",
    "MerkleProofEntry",
    "NotificationEventType",
    "NotificationPayload",
    "WebhookSubscription",
    "WebhookSubscriptionResponse",
]
