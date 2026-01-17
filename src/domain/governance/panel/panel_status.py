"""Panel status enumeration.

Story: consent-gov-6-4: Prince Panel Domain Model

Defines the lifecycle states of a Prince Panel.
"""

from enum import Enum


class PanelStatus(Enum):
    """Status of a Prince Panel.

    Lifecycle:
        CONVENED → REVIEWING → DELIBERATING → FINDING_ISSUED
                                            → DISBANDED

    Attributes:
        CONVENED: Panel has been formed by Human Operator
        REVIEWING: Panel is reviewing witness artifacts
        DELIBERATING: Panel members are deliberating
        FINDING_ISSUED: Panel has issued a formal finding
        DISBANDED: Panel has concluded without issuing a finding
    """

    CONVENED = "convened"
    """Panel formed by Human Operator."""

    REVIEWING = "reviewing"
    """Panel reviewing witness artifacts."""

    DELIBERATING = "deliberating"
    """Panel members deliberating."""

    FINDING_ISSUED = "finding_issued"
    """Panel has issued formal finding."""

    DISBANDED = "disbanded"
    """Panel ended without finding."""
