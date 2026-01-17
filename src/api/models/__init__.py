"""
API models (Pydantic DTOs) for Archon 72.

This module contains all Pydantic request/response models
used by API endpoints.
"""

from src.api.models.health import HealthResponse
from src.api.models.observer import (
    ChainVerificationResult,
    EventFilterParams,
    HashVerificationSpec,
    ObserverEventResponse,
    ObserverEventsListResponse,
    PaginationMetadata,
    SchemaDocumentation,
)
from src.api.models.override import (
    OverrideEventResponse,
    OverrideEventsListResponse,
)
from src.api.models.petition import (
    CosignPetitionRequest,
    CosignPetitionResponse,
    CoSignerResponse,
    ListPetitionsResponse,
    PetitionDetailResponse,
    PetitionErrorResponse,
    PetitionSummaryResponse,
    SubmitPetitionRequest,
    SubmitPetitionResponse,
)
from src.api.models.incident import (
    IncidentDetailResponse,
    IncidentErrorResponse,
    IncidentQueryParams,
    IncidentSummaryResponse,
    ListIncidentsResponse,
    PendingPublicationResponse,
    PublishedIncidentsResponse,
    TimelineEntryResponse,
)
from src.api.models.complexity_budget import (
    ComplexityBreachListResponse,
    ComplexityBreachResponse,
    ComplexityDashboardResponse,
    ComplexityEscalationResponse,
    ComplexityMetricResponse,
    ComplexityTrendDataPoint,
    ComplexityTrendResponse,
)
from src.api.models.failure_prevention import (
    AcknowledgeWarningRequest,
    AcknowledgeWarningResponse,
    DashboardResponse,
    EarlyWarningResponse,
    FailureModeResponse,
    HealthSummaryResponse,
    LoadSheddingResponse,
    MetricUpdateRequest,
    MetricUpdateResponse,
    PatternViolationResponse,
    PatternViolationScanResponse,
    QueryPerformanceResponse,
    ThresholdResponse,
)
from src.api.models.constitutional_health import (
    ConstitutionalHealthAlertResponse,
    ConstitutionalHealthResponse,
    ConstitutionalHealthStatusResponse,
    ConstitutionalMetricResponse,
)
from src.api.models.waiver import (
    WaiverErrorResponse,
    WaiverResponse,
    WaiversListResponse,
)
from src.api.models.compliance import (
    ComplianceAssessmentResponse,
    ComplianceErrorResponse,
    ComplianceFrameworksListResponse,
    ComplianceGapsResponse,
    CompliancePostureResponse,
    ComplianceRequirementResponse,
)
from src.api.models.halt import (
    HaltErrorResponse,
    HaltRequest,
    HaltResponse,
    HaltStatusResponse,
)
from src.api.models.legitimacy import (
    LegitimacyErrorResponse,
    LegitimacyStatusResponse,
    RestorationHistoryItem,
    RestorationHistoryResponse,
    RestorationRequest,
    RestorationResponse,
)

__all__: list[str] = [
    "ChainVerificationResult",
    "EventFilterParams",
    "HashVerificationSpec",
    "HealthResponse",
    "ObserverEventResponse",
    "ObserverEventsListResponse",
    "OverrideEventResponse",
    "OverrideEventsListResponse",
    "PaginationMetadata",
    "SchemaDocumentation",
    # Petition models (Story 7.2, FR39)
    "CosignPetitionRequest",
    "CosignPetitionResponse",
    "CoSignerResponse",
    "ListPetitionsResponse",
    "PetitionDetailResponse",
    "PetitionErrorResponse",
    "PetitionSummaryResponse",
    "SubmitPetitionRequest",
    "SubmitPetitionResponse",
    # Incident models (Story 8.4, FR54, FR145, FR147)
    "IncidentDetailResponse",
    "IncidentErrorResponse",
    "IncidentQueryParams",
    "IncidentSummaryResponse",
    "ListIncidentsResponse",
    "PendingPublicationResponse",
    "PublishedIncidentsResponse",
    "TimelineEntryResponse",
    # Complexity budget models (Story 8.6, CT-14, RT-6, SC-3)
    "ComplexityBreachListResponse",
    "ComplexityBreachResponse",
    "ComplexityDashboardResponse",
    "ComplexityEscalationResponse",
    "ComplexityMetricResponse",
    "ComplexityTrendDataPoint",
    "ComplexityTrendResponse",
    # Failure prevention models (Story 8.8, FR106-FR107)
    "AcknowledgeWarningRequest",
    "AcknowledgeWarningResponse",
    "DashboardResponse",
    "EarlyWarningResponse",
    "FailureModeResponse",
    "HealthSummaryResponse",
    "LoadSheddingResponse",
    "MetricUpdateRequest",
    "MetricUpdateResponse",
    "PatternViolationResponse",
    "PatternViolationScanResponse",
    "QueryPerformanceResponse",
    "ThresholdResponse",
    # Constitutional health models (Story 8.10, ADR-10)
    "ConstitutionalHealthAlertResponse",
    "ConstitutionalHealthResponse",
    "ConstitutionalHealthStatusResponse",
    "ConstitutionalMetricResponse",
    # Waiver models (Story 9.8, SC-4, SR-10)
    "WaiverErrorResponse",
    "WaiverResponse",
    "WaiversListResponse",
    # Compliance models (Story 9.9, NFR31-34)
    "ComplianceAssessmentResponse",
    "ComplianceErrorResponse",
    "ComplianceFrameworksListResponse",
    "ComplianceGapsResponse",
    "CompliancePostureResponse",
    "ComplianceRequirementResponse",
    # Halt models (Story 4-2, FR22-23)
    "HaltErrorResponse",
    "HaltRequest",
    "HaltResponse",
    "HaltStatusResponse",
    # Legitimacy models (Story 5-3, FR30-32)
    "LegitimacyErrorResponse",
    "LegitimacyStatusResponse",
    "RestorationHistoryItem",
    "RestorationHistoryResponse",
    "RestorationRequest",
    "RestorationResponse",
]
