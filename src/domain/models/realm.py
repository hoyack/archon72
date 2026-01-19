"""Realm domain model for petition routing (Story 0.6, HP-3, HP-4).

This module defines the Realm domain entity for routing petitions to
appropriate Knights by realm in the Three Fates petition system.

Constitutional Constraints:
- HP-3: Realm Registry required for petition routing
- HP-4: Sentinel-to-realm mapping for triage
- NFR-7.3: Realm-based Knight capacity limits

Developer Golden Rules:
1. IMMUTABILITY - Realm is a frozen dataclass
2. VALIDATION - Knight capacity must be positive
3. CANONICAL - Realm names are canonical identifiers from archons-base.json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class RealmStatus(Enum):
    """Status of a realm in the registry.

    Statuses:
        ACTIVE: Realm accepts petitions and referrals
        INACTIVE: Realm temporarily not accepting referrals
        DEPRECATED: Realm being phased out
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEPRECATED = "DEPRECATED"


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, eq=True)
class Realm:
    """A governance realm for petition routing (Story 0.6, HP-3).

    Realms represent the 9 governance domains from the Archon 72 system.
    Each realm has Knights responsible for reviewing referred petitions.

    Constitutional Constraints:
    - HP-3: Realm registry for valid routing targets
    - HP-4: Maps sentinels to realms for petition triage
    - NFR-7.3: Knight capacity limits concurrent referrals

    Attributes:
        id: UUIDv7 unique identifier.
        name: Canonical realm identifier (e.g., "realm_privacy_discretion_services").
        display_name: Human-readable realm name.
        knight_capacity: Max concurrent referrals to this realm's Knights.
        status: Current realm status (ACTIVE, INACTIVE, DEPRECATED).
        description: Optional realm description.
        created_at: Creation timestamp (UTC).
        updated_at: Last modification timestamp (UTC).
    """

    id: UUID
    name: str
    display_name: str
    knight_capacity: int
    status: RealmStatus = field(default=RealmStatus.ACTIVE)
    description: str | None = field(default=None)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    # Validation constants
    MIN_KNIGHT_CAPACITY: int = 1
    MAX_KNIGHT_CAPACITY: int = 100
    MAX_NAME_LENGTH: int = 100
    MAX_DISPLAY_NAME_LENGTH: int = 200

    def __post_init__(self) -> None:
        """Validate realm fields."""
        if not self.name:
            raise ValueError("Realm name cannot be empty")
        if len(self.name) > self.MAX_NAME_LENGTH:
            raise ValueError(
                f"Realm name exceeds maximum length of {self.MAX_NAME_LENGTH} characters"
            )
        if not self.display_name:
            raise ValueError("Realm display_name cannot be empty")
        if len(self.display_name) > self.MAX_DISPLAY_NAME_LENGTH:
            raise ValueError(
                f"Realm display_name exceeds maximum length of {self.MAX_DISPLAY_NAME_LENGTH}"
            )
        if self.knight_capacity < self.MIN_KNIGHT_CAPACITY:
            raise ValueError(
                f"Knight capacity must be at least {self.MIN_KNIGHT_CAPACITY}"
            )
        if self.knight_capacity > self.MAX_KNIGHT_CAPACITY:
            raise ValueError(
                f"Knight capacity cannot exceed {self.MAX_KNIGHT_CAPACITY}"
            )

    @property
    def is_active(self) -> bool:
        """Check if realm is active and accepting referrals."""
        return self.status == RealmStatus.ACTIVE

    def with_status(self, new_status: RealmStatus) -> Realm:
        """Create new realm with updated status.

        Since Realm is frozen, returns new instance.

        Args:
            new_status: The new status to set.

        Returns:
            New Realm with updated status and timestamp.
        """
        return Realm(
            id=self.id,
            name=self.name,
            display_name=self.display_name,
            knight_capacity=self.knight_capacity,
            status=new_status,
            description=self.description,
            created_at=self.created_at,
            updated_at=_utc_now(),
        )

    def with_knight_capacity(self, new_capacity: int) -> Realm:
        """Create new realm with updated knight capacity.

        Since Realm is frozen, returns new instance.

        Args:
            new_capacity: The new knight capacity.

        Returns:
            New Realm with updated capacity and timestamp.
        """
        return Realm(
            id=self.id,
            name=self.name,
            display_name=self.display_name,
            knight_capacity=new_capacity,
            status=self.status,
            description=self.description,
            created_at=self.created_at,
            updated_at=_utc_now(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL REALM IDS (from archons-base.json)
# ═══════════════════════════════════════════════════════════════════════════════

CANONICAL_REALM_IDS: tuple[str, ...] = (
    "realm_privacy_discretion_services",
    "realm_relationship_facilitation",
    "realm_knowledge_skill_development",
    "realm_predictive_analytics_forecasting",
    "realm_character_virtue_development",
    "realm_accurate_guidance_counsel",
    "realm_threat_anomaly_detection",
    "realm_personality_charisma_enhancement",
    "realm_talent_acquisition_team_building",
)

# Display name mapping for canonical realms
REALM_DISPLAY_NAMES: dict[str, str] = {
    "realm_privacy_discretion_services": "Privacy & Discretion Services",
    "realm_relationship_facilitation": "Relationship Facilitation",
    "realm_knowledge_skill_development": "Knowledge & Skill Development",
    "realm_predictive_analytics_forecasting": "Predictive Analytics & Forecasting",
    "realm_character_virtue_development": "Character & Virtue Development",
    "realm_accurate_guidance_counsel": "Accurate Guidance & Counsel",
    "realm_threat_anomaly_detection": "Threat & Anomaly Detection",
    "realm_personality_charisma_enhancement": "Personality & Charisma Enhancement",
    "realm_talent_acquisition_team_building": "Talent Acquisition & Team Building",
}


def is_canonical_realm(realm_name: str) -> bool:
    """Check if a realm name is a canonical realm from archons-base.json.

    Args:
        realm_name: The realm name to check.

    Returns:
        True if realm_name is in CANONICAL_REALM_IDS, False otherwise.
    """
    return realm_name in CANONICAL_REALM_IDS
