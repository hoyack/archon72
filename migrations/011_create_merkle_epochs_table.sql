-- Migration: Create merkle_epochs table for Merkle tree proof-of-inclusion
-- Story: consent-gov-1.7: Merkle Tree Proof-of-Inclusion
-- Date: 2026-01-16
--
-- Constitutional Constraints:
--   AD-7: Merkle tree proof-of-inclusion
--   NFR-CONST-02: Proof-of-inclusion for any entry
--   NFR-AUDIT-06: External verification possible
--   FR57: Cryptographic proof of completeness
--
-- Architectural Notes:
--   - Stored in 'ledger' schema (not 'projections') because Merkle roots
--     are part of cryptographic integrity infrastructure
--   - Epoch roots enable proof generation for historical events
--   - Each epoch corresponds to a batch of events

-- ============================================================================
-- TASK 1: Create merkle_epochs table
-- ============================================================================

CREATE TABLE IF NOT EXISTS ledger.merkle_epochs (
    -- Epoch identifier (0-indexed, sequential)
    epoch_id BIGINT PRIMARY KEY,

    -- Merkle root hash for this epoch (algorithm-prefixed)
    root_hash TEXT NOT NULL,

    -- Hash algorithm used (blake3 or sha256)
    algorithm TEXT NOT NULL DEFAULT 'blake3',

    -- Sequence range covered by this epoch (inclusive)
    start_sequence BIGINT NOT NULL,
    end_sequence BIGINT NOT NULL,

    -- Number of events in this epoch
    event_count INT NOT NULL,

    -- When the epoch root was computed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Reference to the ledger event that published this root
    -- (ledger.merkle.root_published event)
    root_event_id UUID REFERENCES ledger.governance_events(event_id),

    -- Constraints
    CONSTRAINT chk_sequence_range CHECK (start_sequence <= end_sequence),
    CONSTRAINT chk_event_count_positive CHECK (event_count > 0),
    CONSTRAINT chk_algorithm_valid CHECK (algorithm IN ('blake3', 'sha256')),
    CONSTRAINT chk_root_hash_format CHECK (
        root_hash ~ '^(blake3|sha256):[a-f0-9]{64}$'
        OR root_hash = 'blake3:empty'
        OR root_hash = 'sha256:empty'
    )
);

-- ============================================================================
-- TASK 2: Create indexes for efficient queries
-- ============================================================================

-- Index for looking up epoch by sequence range
CREATE INDEX IF NOT EXISTS idx_merkle_epochs_sequence
    ON ledger.merkle_epochs (start_sequence, end_sequence);

-- Index for looking up epoch by root_event_id
CREATE INDEX IF NOT EXISTS idx_merkle_epochs_root_event_id
    ON ledger.merkle_epochs (root_event_id);

-- ============================================================================
-- TASK 3: Create helper function to find epoch for sequence
-- ============================================================================

CREATE OR REPLACE FUNCTION ledger.get_epoch_for_sequence(p_sequence BIGINT)
RETURNS BIGINT AS $$
    SELECT epoch_id
    FROM ledger.merkle_epochs
    WHERE p_sequence >= start_sequence
      AND p_sequence <= end_sequence
    LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- TASK 4: Comments for documentation
-- ============================================================================

COMMENT ON TABLE ledger.merkle_epochs IS
    'Merkle tree epoch roots for proof-of-inclusion (AD-7, NFR-CONST-02). Each epoch covers a batch of events.';

COMMENT ON COLUMN ledger.merkle_epochs.epoch_id IS
    'Epoch identifier (0-indexed, sequential). Epochs are built incrementally.';

COMMENT ON COLUMN ledger.merkle_epochs.root_hash IS
    'Merkle root hash for this epoch. Algorithm-prefixed (e.g., blake3:abc123...).';

COMMENT ON COLUMN ledger.merkle_epochs.algorithm IS
    'Hash algorithm used for tree construction. Must be blake3 or sha256.';

COMMENT ON COLUMN ledger.merkle_epochs.start_sequence IS
    'First event sequence number in this epoch (inclusive).';

COMMENT ON COLUMN ledger.merkle_epochs.end_sequence IS
    'Last event sequence number in this epoch (inclusive).';

COMMENT ON COLUMN ledger.merkle_epochs.event_count IS
    'Number of events included in this epoch.';

COMMENT ON COLUMN ledger.merkle_epochs.created_at IS
    'When the epoch Merkle tree was built and root computed.';

COMMENT ON COLUMN ledger.merkle_epochs.root_event_id IS
    'Reference to ledger.merkle.root_published event that recorded this root.';

COMMENT ON FUNCTION ledger.get_epoch_for_sequence(BIGINT) IS
    'Find epoch containing a given sequence number. Returns NULL if no epoch covers it.';
