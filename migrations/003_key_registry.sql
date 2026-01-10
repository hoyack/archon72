-- Migration: 003_key_registry
-- Description: Agent key registry for cryptographic signing (FR75, FR76, FR74)
-- Dependencies: 001_create_events_table.sql
--
-- Constitutional Requirements:
-- - FR74: Invalid agent signatures must be rejected
-- - FR75: Key registry must track active keys
-- - FR76: Historical keys must be preserved (no deletion)
--
-- ADR-4 (Key Custody) Requirements:
-- - Signature algorithm: Ed25519
-- - Key rotation supported with temporal validity
-- - Historical keys preserved for verifying old events

-- ============================================================================
-- Key Registry Schema (FR75, FR76)
-- ============================================================================

-- Agent key registry table
-- Stores Ed25519 public keys for all agents that can sign events
CREATE TABLE IF NOT EXISTS agent_keys (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Agent identifier (FR3)
    -- Format: "agent-{uuid}" for user agents, "SYSTEM:{service}" for system agents
    agent_id TEXT NOT NULL,

    -- Key identifier (matches HSM key_id)
    -- Format: "dev-{hex}" for dev mode, "{hsm-key-id}" for production
    key_id TEXT NOT NULL UNIQUE,

    -- Ed25519 public key bytes (32 bytes for Ed25519)
    public_key BYTEA NOT NULL,

    -- Temporal validity for key rotation
    active_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    active_until TIMESTAMPTZ,  -- NULL means currently active

    -- Audit timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Validity constraint: active_until must be after active_from if set
    CONSTRAINT agent_keys_active_check CHECK (
        active_until IS NULL OR active_until > active_from
    )
);

-- Comment on table
COMMENT ON TABLE agent_keys IS 'FR75/FR76: Agent signing key registry with historical preservation';

-- ============================================================================
-- Indexes for Key Registry
-- ============================================================================

-- Index for agent key lookup
CREATE INDEX IF NOT EXISTS idx_agent_keys_agent_id ON agent_keys(agent_id);

-- Index for key_id lookup (used during signature verification)
CREATE INDEX IF NOT EXISTS idx_agent_keys_key_id ON agent_keys(key_id);

-- Index for temporal key lookup (find active key at specific time)
CREATE INDEX IF NOT EXISTS idx_agent_keys_active ON agent_keys(
    agent_id,
    active_from,
    active_until
);

-- ============================================================================
-- FR76: Prevent Key Deletion (Historical Preservation)
-- ============================================================================

-- Keys cannot be deleted - they must be preserved for historical verification
CREATE OR REPLACE FUNCTION prevent_key_deletion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'FR76: Key deletion prohibited - historical keys must be preserved for signature verification';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_agent_key_deletion
    BEFORE DELETE ON agent_keys
    FOR EACH ROW
    EXECUTE FUNCTION prevent_key_deletion();

COMMENT ON FUNCTION prevent_key_deletion() IS 'FR76: Ensures historical keys cannot be deleted';

-- ============================================================================
-- FR74: Signature Format Validation Trigger
-- ============================================================================

-- Note: Full cryptographic verification happens in application layer.
-- This trigger validates:
-- 1. Signature is present and non-empty
-- 2. Signature length is consistent with Ed25519 (64 bytes = ~88 base64 chars)
-- 3. signing_key_id references a valid key in the registry

CREATE OR REPLACE FUNCTION validate_signature_format()
RETURNS TRIGGER AS $$
BEGIN
    -- Validate signature is present and non-empty
    IF NEW.signature IS NULL OR NEW.signature = '' THEN
        RAISE EXCEPTION 'FR74: Invalid agent signature - signature is required';
    END IF;

    -- Validate signature length is consistent with Ed25519
    -- Ed25519 signatures are 64 bytes = 88 base64 chars (with padding)
    -- Allow some variance for different encoding formats
    IF length(NEW.signature) < 80 OR length(NEW.signature) > 100 THEN
        RAISE EXCEPTION 'FR74: Invalid agent signature - unexpected signature length (expected ~88 chars for Ed25519)';
    END IF;

    -- Validate signing_key_id references a valid key
    IF NEW.signing_key_id IS NULL OR NEW.signing_key_id = '' THEN
        RAISE EXCEPTION 'FR74: Invalid agent signature - signing_key_id is required';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM agent_keys
        WHERE key_id = NEW.signing_key_id
    ) THEN
        RAISE EXCEPTION 'FR74: Invalid agent signature - unknown signing key: %', NEW.signing_key_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to events table
CREATE TRIGGER validate_signature_format_on_insert
    BEFORE INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION validate_signature_format();

COMMENT ON FUNCTION validate_signature_format() IS 'FR74: Validates signature format and key reference (crypto verification in app layer)';

-- ============================================================================
-- Add signing_key_id column to events table
-- ============================================================================

-- Add the signing_key_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'events' AND column_name = 'signing_key_id'
    ) THEN
        ALTER TABLE events ADD COLUMN signing_key_id TEXT NOT NULL DEFAULT '';
        COMMENT ON COLUMN events.signing_key_id IS 'FR74: Reference to signing key in agent_keys table';
    END IF;
END $$;

-- ============================================================================
-- Verification: Check migration applied correctly
-- ============================================================================

DO $$
DECLARE
    table_exists BOOLEAN;
    trigger_exists BOOLEAN;
    column_exists BOOLEAN;
BEGIN
    -- Check agent_keys table exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'agent_keys'
    ) INTO table_exists;

    IF NOT table_exists THEN
        RAISE EXCEPTION 'Migration failed: agent_keys table not created';
    END IF;

    -- Check delete prevention trigger exists
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'prevent_agent_key_deletion'
    ) INTO trigger_exists;

    IF NOT trigger_exists THEN
        RAISE EXCEPTION 'Migration failed: prevent_agent_key_deletion trigger not created';
    END IF;

    -- Check signature validation trigger exists
    SELECT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'validate_signature_format_on_insert'
    ) INTO trigger_exists;

    IF NOT trigger_exists THEN
        RAISE EXCEPTION 'Migration failed: validate_signature_format_on_insert trigger not created';
    END IF;

    -- Check signing_key_id column exists on events
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'events' AND column_name = 'signing_key_id'
    ) INTO column_exists;

    IF NOT column_exists THEN
        RAISE EXCEPTION 'Migration failed: signing_key_id column not added to events';
    END IF;

    RAISE NOTICE 'Migration 003_key_registry completed successfully';
END $$;
