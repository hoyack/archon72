"""Intent-Only Validator.

This service validates that motion text contains only WHAT (intent),
not HOW (execution details).

Per Government PRD FR-GOV-6: Kings may NOT define tasks, timelines, tools,
execution methods, supervise execution, or judge outcomes.
"""

import re
from dataclasses import dataclass

from structlog import get_logger

from src.application.ports.king_service import (
    IntentValidationResult,
    IntentViolation,
    IntentViolationType,
)

logger = get_logger(__name__)


@dataclass
class ExecutionPattern:
    """Pattern for detecting execution details in motion text."""

    pattern: re.Pattern[str]
    violation_type: IntentViolationType
    description: str


# Pattern definitions for detecting execution details
EXECUTION_PATTERNS: list[ExecutionPattern] = [
    # Task list patterns
    ExecutionPattern(
        pattern=re.compile(r"\b(?:step\s*(?:\d+|one|two|three|four|five))\b", re.I),
        violation_type=IntentViolationType.TASK_LIST,
        description="Contains numbered steps indicating task breakdown",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:first|second|third|fourth|fifth),?\s+(?:we|they|it|the)\b", re.I
        ),
        violation_type=IntentViolationType.TASK_LIST,
        description="Contains sequential ordering indicating task list",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"(?:^|\n)\s*[-*•]\s*(?:implement|create|build|develop|design)\b",
            re.I | re.M,
        ),
        violation_type=IntentViolationType.TASK_LIST,
        description="Contains bullet-point task list",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:task\s*\d+|subtask|work\s*item)\b", re.I),
        violation_type=IntentViolationType.TASK_LIST,
        description="Contains explicit task enumeration",
    ),
    # Timeline patterns
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:timeline|schedule|deadline|due\s*date)\s*[:\-]", re.I
        ),
        violation_type=IntentViolationType.TIMELINE,
        description="Contains timeline specification",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:by|within|before)\s+(?:\d+\s*(?:days?|weeks?|months?|hours?))", re.I
        ),
        violation_type=IntentViolationType.TIMELINE,
        description="Contains deadline specification",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:phase\s*\d+|sprint\s*\d+|iteration\s*\d+)\b", re.I),
        violation_type=IntentViolationType.TIMELINE,
        description="Contains phased timeline",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:start|begin|finish|complete)\s+(?:by|on|before)\b", re.I
        ),
        violation_type=IntentViolationType.TIMELINE,
        description="Contains start/end date specification",
    ),
    # Tool specification patterns
    ExecutionPattern(
        pattern=re.compile(
            r"\busing\s+(?:python|java|javascript|rust|go|nodejs|react|django)\b", re.I
        ),
        violation_type=IntentViolationType.TOOL_SPECIFICATION,
        description="Specifies programming language/framework",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:implement|build|develop)\s+(?:with|using|in)\b", re.I
        ),
        violation_type=IntentViolationType.TOOL_SPECIFICATION,
        description="Specifies implementation tools",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:use|utilize|leverage)\s+(?:the\s+)?(?:api|sdk|library|framework|tool)\b",
            re.I,
        ),
        violation_type=IntentViolationType.TOOL_SPECIFICATION,
        description="Specifies tooling requirements",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:deploy\s+(?:to|on)|host\s+(?:on|with))\b", re.I),
        violation_type=IntentViolationType.TOOL_SPECIFICATION,
        description="Specifies deployment target",
    ),
    # Resource allocation patterns
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:allocate|assign|dedicate)\s+(?:\d+|a|the)\s*(?:team|developer|engineer|resource)",
            re.I,
        ),
        violation_type=IntentViolationType.RESOURCE_ALLOCATION,
        description="Specifies resource allocation",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:budget|cost|spend)\s*[:\-]?\s*\$?\d+", re.I),
        violation_type=IntentViolationType.RESOURCE_ALLOCATION,
        description="Specifies budget allocation",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:requires?\s+\d+\s*(?:developers?|engineers?|hours?|days?))\b", re.I
        ),
        violation_type=IntentViolationType.RESOURCE_ALLOCATION,
        description="Specifies resource requirements",
    ),
    # Execution method patterns
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:the\s+method|approach|process)\s+(?:is|will\s+be|should\s+be)\b",
            re.I,
        ),
        violation_type=IntentViolationType.EXECUTION_METHOD,
        description="Defines execution method",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:algorithm|procedure|workflow)\s+(?:to|for)\b", re.I),
        violation_type=IntentViolationType.EXECUTION_METHOD,
        description="Defines procedural execution",
    ),
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:call|invoke|execute)\s+(?:the\s+)?(?:function|method|api)\b", re.I
        ),
        violation_type=IntentViolationType.EXECUTION_METHOD,
        description="Specifies execution calls",
    ),
    # Supervision direction patterns
    ExecutionPattern(
        pattern=re.compile(
            r"\b(?:supervise|oversee|manage|direct)\s+(?:the\s+)?(?:execution|implementation|work)\b",
            re.I,
        ),
        violation_type=IntentViolationType.SUPERVISION_DIRECTION,
        description="Contains supervision direction",
    ),
    ExecutionPattern(
        pattern=re.compile(r"\b(?:report\s+to|monitored\s+by|managed\s+by)\b", re.I),
        violation_type=IntentViolationType.SUPERVISION_DIRECTION,
        description="Specifies reporting structure",
    ),
]

# Warning patterns (less severe, advisory)
WARNING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(?:specific(?:ally)?|exact(?:ly)?)\b", re.I),
        "Contains specificity language that may cross into execution details",
    ),
    (
        re.compile(r"\b(?:must|shall|will)\s+(?:be|have|use)\b", re.I),
        "Contains prescriptive language that may constrain execution",
    ),
    (
        re.compile(r"\b(?:no\s+later\s+than|at\s+least|minimum\s+of)\b", re.I),
        "Contains constraint language that may imply timeline",
    ),
]


class IntentValidator:
    """Validator that ensures motion text contains only WHAT, not HOW.

    Per Government PRD FR-GOV-6:
    - Kings may NOT define tasks
    - Kings may NOT define timelines
    - Kings may NOT define tools
    - Kings may NOT define execution methods
    - Kings may NOT supervise execution
    - Kings may NOT judge outcomes

    This validator detects and rejects motions that contain these
    execution details, ensuring separation of powers.
    """

    def __init__(
        self,
        patterns: list[ExecutionPattern] | None = None,
        warning_patterns: list[tuple[re.Pattern[str], str]] | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the intent validator.

        Args:
            patterns: Custom execution patterns (defaults to EXECUTION_PATTERNS)
            warning_patterns: Custom warning patterns (defaults to WARNING_PATTERNS)
            verbose: Enable verbose logging
        """
        self._patterns = patterns or EXECUTION_PATTERNS
        self._warning_patterns = warning_patterns or WARNING_PATTERNS
        self._verbose = verbose

    def validate(self, motion_text: str) -> IntentValidationResult:
        """Validate that motion text contains only WHAT, not HOW.

        Args:
            motion_text: The motion intent text to validate

        Returns:
            IntentValidationResult with any violations found
        """
        violations: list[IntentViolation] = []
        warnings: list[str] = []

        # Check for execution detail patterns
        for exec_pattern in self._patterns:
            match = exec_pattern.pattern.search(motion_text)
            if match:
                violation = IntentViolation(
                    violation_type=exec_pattern.violation_type,
                    description=exec_pattern.description,
                    matched_text=match.group(0),
                    prd_reference="FR-GOV-6",
                )
                violations.append(violation)

                if self._verbose:
                    logger.debug(
                        "intent_violation_detected",
                        violation_type=exec_pattern.violation_type.value,
                        matched_text=match.group(0),
                    )

        # Check for warning patterns
        for warn_pattern, warn_msg in self._warning_patterns:
            if warn_pattern.search(motion_text):
                warnings.append(warn_msg)

        is_valid = len(violations) == 0

        result = IntentValidationResult(
            is_valid=is_valid,
            violations=tuple(violations),
            warnings=tuple(warnings),
        )

        if self._verbose:
            logger.debug(
                "intent_validation_complete",
                is_valid=is_valid,
                violation_count=len(violations),
                warning_count=len(warnings),
            )

        return result

    def get_violation_summary(self, result: IntentValidationResult) -> str:
        """Generate a human-readable summary of violations.

        Args:
            result: The validation result

        Returns:
            Summary string describing violations
        """
        if result.is_valid:
            return "Motion contains valid intent-only content (WHAT, not HOW)"

        summary_parts = [
            f"Motion contains {result.violation_count} execution detail violation(s):"
        ]

        for violation in result.violations:
            summary_parts.append(
                f"  - {violation.violation_type.value}: {violation.description}"
            )
            summary_parts.append(f"    Matched: '{violation.matched_text}'")

        summary_parts.append(
            "\nPer FR-GOV-6: Kings may NOT define tasks, timelines, tools, "
            "execution methods, supervise execution, or judge outcomes."
        )

        return "\n".join(summary_parts)


def create_intent_validator(verbose: bool = False) -> IntentValidator:
    """Factory function to create an IntentValidator.

    Args:
        verbose: Enable verbose logging

    Returns:
        Configured IntentValidator
    """
    return IntentValidator(verbose=verbose)


def is_intent_only(motion_text: str) -> bool:
    """Quick check if motion text is intent-only (no HOW).

    Convenience function for simple validation checks.

    Args:
        motion_text: The motion text to check

    Returns:
        True if text contains only WHAT, False if HOW detected
    """
    validator = IntentValidator()
    result = validator.validate(motion_text)
    return result.is_valid
