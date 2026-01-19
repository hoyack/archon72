-- Migration 015: Create realms table (Story 0.6, HP-3, HP-4)
--
-- Constitutional Constraints:
-- - HP-3: Realm registry for valid petition routing targets
-- - HP-4: Sentinel-to-realm mapping for petition triage
-- - NFR-7.3: Knight capacity limits per realm
--
-- This migration creates the realm registry table and seeds it with
-- the 9 canonical realms from archons-base.json.

-- ═══════════════════════════════════════════════════════════════════════════════
-- REALMS TABLE
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS realms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    knight_capacity INTEGER NOT NULL DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT realms_name_length CHECK (char_length(name) <= 100),
    CONSTRAINT realms_display_name_length CHECK (char_length(display_name) <= 200),
    CONSTRAINT realms_knight_capacity_range CHECK (knight_capacity >= 1 AND knight_capacity <= 100),
    CONSTRAINT realms_status_valid CHECK (status IN ('ACTIVE', 'INACTIVE', 'DEPRECATED'))
);

-- Index for status queries (find active realms)
CREATE INDEX IF NOT EXISTS idx_realms_status ON realms(status);

-- Index for name lookups (routing)
CREATE INDEX IF NOT EXISTS idx_realms_name ON realms(name);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_realms_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_realms_updated_at
    BEFORE UPDATE ON realms
    FOR EACH ROW
    EXECUTE FUNCTION update_realms_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- SENTINEL-TO-REALM MAPPING TABLE (HP-4)
-- Maps sentinel types/categories to realms for petition triage
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sentinel_realm_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sentinel_type TEXT NOT NULL,
    realm_id UUID NOT NULL REFERENCES realms(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT sentinel_realm_unique UNIQUE (sentinel_type, realm_id),
    CONSTRAINT sentinel_type_length CHECK (char_length(sentinel_type) <= 100),
    CONSTRAINT sentinel_priority_valid CHECK (priority >= 0)
);

-- Index for sentinel type lookups
CREATE INDEX IF NOT EXISTS idx_sentinel_realm_mappings_type ON sentinel_realm_mappings(sentinel_type);

-- Index for realm lookups
CREATE INDEX IF NOT EXISTS idx_sentinel_realm_mappings_realm ON sentinel_realm_mappings(realm_id);

-- Trigger for updated_at
CREATE TRIGGER trigger_sentinel_realm_mappings_updated_at
    BEFORE UPDATE ON sentinel_realm_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_realms_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- SEED DATA: 9 Canonical Realms from archons-base.json
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO realms (name, display_name, knight_capacity, status, description)
VALUES
    (
        'realm_privacy_discretion_services',
        'Privacy & Discretion Services',
        5,
        'ACTIVE',
        'Domain of privacy protection, confidential operations, and discrete service handling'
    ),
    (
        'realm_relationship_facilitation',
        'Relationship Facilitation',
        5,
        'ACTIVE',
        'Domain of relationship building, mediation, and interpersonal connections'
    ),
    (
        'realm_knowledge_skill_development',
        'Knowledge & Skill Development',
        5,
        'ACTIVE',
        'Domain of learning, education, skill acquisition, and knowledge transfer'
    ),
    (
        'realm_predictive_analytics_forecasting',
        'Predictive Analytics & Forecasting',
        5,
        'ACTIVE',
        'Domain of prediction, forecasting, trend analysis, and future planning'
    ),
    (
        'realm_character_virtue_development',
        'Character & Virtue Development',
        5,
        'ACTIVE',
        'Domain of moral development, virtue cultivation, and ethical growth'
    ),
    (
        'realm_accurate_guidance_counsel',
        'Accurate Guidance & Counsel',
        5,
        'ACTIVE',
        'Domain of advisory services, accurate guidance, and wise counsel'
    ),
    (
        'realm_threat_anomaly_detection',
        'Threat & Anomaly Detection',
        5,
        'ACTIVE',
        'Domain of security, threat identification, anomaly detection, and protection'
    ),
    (
        'realm_personality_charisma_enhancement',
        'Personality & Charisma Enhancement',
        5,
        'ACTIVE',
        'Domain of personal development, charisma building, and social enhancement'
    ),
    (
        'realm_talent_acquisition_team_building',
        'Talent Acquisition & Team Building',
        5,
        'ACTIVE',
        'Domain of recruitment, talent discovery, and team formation'
    )
ON CONFLICT (name) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SEED DATA: Default Sentinel-to-Realm Mappings
-- Maps petition types/sentinel categories to their primary realm
-- ═══════════════════════════════════════════════════════════════════════════════

-- Privacy-related petitions route to Privacy realm
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'privacy', id, 0 FROM realms WHERE name = 'realm_privacy_discretion_services'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- Security-related petitions route to Threat Detection realm
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'security', id, 0 FROM realms WHERE name = 'realm_threat_anomaly_detection'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- Learning-related petitions route to Knowledge realm
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'learning', id, 0 FROM realms WHERE name = 'realm_knowledge_skill_development'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- Guidance-related petitions route to Counsel realm
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'guidance', id, 0 FROM realms WHERE name = 'realm_accurate_guidance_counsel'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- Team-related petitions route to Talent realm
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'team', id, 0 FROM realms WHERE name = 'realm_talent_acquisition_team_building'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- General petitions can route to any realm (lowest priority)
INSERT INTO sentinel_realm_mappings (sentinel_type, realm_id, priority)
SELECT 'general', id, 100 FROM realms WHERE status = 'ACTIVE'
ON CONFLICT (sentinel_type, realm_id) DO NOTHING;

-- Comment for verification
COMMENT ON TABLE realms IS 'Story 0.6: Realm registry for petition routing (HP-3, HP-4, NFR-7.3)';
COMMENT ON TABLE sentinel_realm_mappings IS 'Story 0.6: Sentinel-to-realm mapping for petition triage (HP-4)';
