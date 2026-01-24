-- Migration 035: Create realm health aggregate table
-- Story 8.7: Realm Health Aggregate (HP-7)
--
-- Constitutional Constraints:
-- - HP-7: Read model projections for realm health
-- - CT-11: Track petition flow (speech vs agenda)
-- - CT-12: Witnessing creates accountability
-- - FR-8.1: Realm health metrics tracked per governance cycle
--
-- This table stores computed health metrics for each realm per governance cycle.
-- Health metrics include petition counts, referral status, escalation status,
-- and derived health indicators.

-- ════════════════════════════════════════════════════════════════════════════════
-- REALM HEALTH TABLE
-- ════════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS realm_health (
    -- Primary key
    health_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Realm and cycle identification
    realm_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,  -- Format: YYYY-Wnn (e.g., "2026-W04")

    -- Petition metrics
    petitions_received INTEGER NOT NULL DEFAULT 0,
    petitions_fated INTEGER NOT NULL DEFAULT 0,

    -- Referral metrics
    referrals_pending INTEGER NOT NULL DEFAULT 0,
    referrals_expired INTEGER NOT NULL DEFAULT 0,

    -- Escalation metrics
    escalations_pending INTEGER NOT NULL DEFAULT 0,

    -- Adoption rate (from Story 8.6)
    -- NULL if no escalations in the cycle
    adoption_rate DECIMAL(5, 4),

    -- Average referral duration in seconds
    -- NULL if no referrals completed in the cycle
    average_referral_duration_seconds INTEGER,

    -- Timestamps
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique constraint: one health record per realm per cycle
    CONSTRAINT unique_realm_health_cycle UNIQUE (realm_id, cycle_id),

    -- Validation constraints
    CONSTRAINT positive_petitions_received CHECK (petitions_received >= 0),
    CONSTRAINT positive_petitions_fated CHECK (petitions_fated >= 0),
    CONSTRAINT positive_referrals_pending CHECK (referrals_pending >= 0),
    CONSTRAINT positive_referrals_expired CHECK (referrals_expired >= 0),
    CONSTRAINT positive_escalations_pending CHECK (escalations_pending >= 0),
    CONSTRAINT valid_adoption_rate CHECK (
        adoption_rate IS NULL OR (adoption_rate >= 0 AND adoption_rate <= 1)
    ),
    CONSTRAINT positive_referral_duration CHECK (
        average_referral_duration_seconds IS NULL OR average_referral_duration_seconds >= 0
    )
);

-- ════════════════════════════════════════════════════════════════════════════════
-- INDEXES
-- ════════════════════════════════════════════════════════════════════════════════

-- Index for cycle queries (dashboard - get all realms for a cycle)
CREATE INDEX idx_realm_health_cycle ON realm_health(cycle_id);

-- Index for realm queries (per-realm history)
CREATE INDEX idx_realm_health_realm ON realm_health(realm_id);

-- Index for computed_at (for time-based queries)
CREATE INDEX idx_realm_health_computed_at ON realm_health(computed_at DESC);

-- Composite index for realm + cycle lookups (covered by unique constraint but explicit)
CREATE INDEX idx_realm_health_realm_cycle ON realm_health(realm_id, cycle_id);

-- ════════════════════════════════════════════════════════════════════════════════
-- COMMENTS
-- ════════════════════════════════════════════════════════════════════════════════

COMMENT ON TABLE realm_health IS 'Realm health aggregate (Story 8.7, HP-7). Tracks per-realm petition metrics per governance cycle.';
COMMENT ON COLUMN realm_health.health_id IS 'Unique identifier for this health record';
COMMENT ON COLUMN realm_health.realm_id IS 'Canonical realm identifier from CANONICAL_REALM_IDS';
COMMENT ON COLUMN realm_health.cycle_id IS 'Governance cycle identifier in YYYY-Wnn format';
COMMENT ON COLUMN realm_health.petitions_received IS 'Petitions received in this realm this cycle';
COMMENT ON COLUMN realm_health.petitions_fated IS 'Petitions that completed Three Fates deliberation';
COMMENT ON COLUMN realm_health.referrals_pending IS 'Current pending Knight referrals';
COMMENT ON COLUMN realm_health.referrals_expired IS 'Referrals that expired without recommendation';
COMMENT ON COLUMN realm_health.escalations_pending IS 'Petitions awaiting King decision';
COMMENT ON COLUMN realm_health.adoption_rate IS 'Adoption ratio from Story 8.6 (NULL if no escalations)';
COMMENT ON COLUMN realm_health.average_referral_duration_seconds IS 'Mean referral processing time in seconds';
COMMENT ON COLUMN realm_health.computed_at IS 'When health metrics were computed (UTC)';
