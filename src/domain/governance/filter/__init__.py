"""Coercion Filter domain models.

This module contains the domain models for the Coercion Filter system,
which ensures all participant-facing content is filtered for coercive
language patterns per FR16-FR18 and NFR-CONST-05.

Key Types:
    - FilterDecision: Enum of filter outcomes (ACCEPTED, REJECTED, BLOCKED)
    - FilteredContent: Type-safe container for filtered content
    - FilterResult: Complete result of content filtering
    - RejectionReason: Reasons for content rejection
    - ViolationType: Types of hard violations (blocked content)
    - TransformationRule: Rules for content transformation
    - Transformation: Record of applied transformation
    - FilterVersion: Version of filter rules used
    - CoercionPattern: Pattern for detecting coercive language
    - PatternCategory: Categories of coercive patterns
    - PatternSeverity: Severity levels for patterns
    - PatternLibraryVersion: Version info for pattern library
"""

from src.domain.governance.filter.coercion_pattern import (
    CoercionPattern,
    PatternCategory,
    PatternLibraryVersion,
    PatternSeverity,
)
from src.domain.governance.filter.filter_decision import FilterDecision
from src.domain.governance.filter.filter_decision_log import (
    FilterDecisionLog,
    TransformationLog,
)
from src.domain.governance.filter.filter_result import FilterResult
from src.domain.governance.filter.filter_version import FilterVersion
from src.domain.governance.filter.filtered_content import FilteredContent
from src.domain.governance.filter.message_type import MessageType
from src.domain.governance.filter.rejection_reason import RejectionReason
from src.domain.governance.filter.transformation import (
    Transformation,
    TransformationRule,
)
from src.domain.governance.filter.violation_type import ViolationType

__all__ = [
    "CoercionPattern",
    "FilterDecision",
    "FilterDecisionLog",
    "FilterResult",
    "FilterVersion",
    "FilteredContent",
    "MessageType",
    "PatternCategory",
    "PatternLibraryVersion",
    "PatternSeverity",
    "RejectionReason",
    "Transformation",
    "TransformationLog",
    "TransformationRule",
    "ViolationType",
]
