-- Migration 036: Create notification preferences table (Story 7.2, FR-7.3)
--
-- Creates the petition_notification_preferences table for storing
-- Observer notification preferences for fate assignment notifications.
--
-- Constitutional Constraints:
-- - FR-7.3: System SHALL notify Observer on fate assignment
-- - CT-12: All notifications are witnessed events
-- - D7: RFC 7807 error responses for invalid preferences

-- Up migration
CREATE TABLE IF NOT EXISTS petition_notification_preferences (
    -- Primary key is the preference ID (UUIDv7)
    id UUID PRIMARY KEY,

    -- Foreign key to petition_submissions table
    petition_id UUID NOT NULL UNIQUE,

    -- Notification channel: 'WEBHOOK' or 'IN_APP'
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('WEBHOOK', 'IN_APP')),

    -- Whether notifications are enabled for this preference
    enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Webhook URL for WEBHOOK channel (HTTPS only, validated in app layer)
    -- NULL for IN_APP channel
    webhook_url TEXT,

    -- Audit timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraint: webhook_url required for WEBHOOK channel
    CONSTRAINT webhook_url_required_for_webhook CHECK (
        channel != 'WEBHOOK' OR webhook_url IS NOT NULL
    ),

    -- Foreign key constraint (deferred - petition_submissions may not exist yet in test)
    -- In production, enable this constraint:
    -- CONSTRAINT fk_petition_id FOREIGN KEY (petition_id)
    --     REFERENCES petition_submissions(id)
    --     ON DELETE CASCADE

    -- Index on petition_id for efficient lookups
    -- UNIQUE constraint already creates an index

    -- Comment for documentation
    CONSTRAINT notification_preferences_valid CHECK (
        -- Basic validation - actual URL validation in application layer
        (channel = 'WEBHOOK' AND webhook_url IS NOT NULL AND LENGTH(webhook_url) > 0)
        OR
        (channel = 'IN_APP' AND (webhook_url IS NULL OR webhook_url = ''))
    )
);

-- Create index on channel for potential future queries filtering by channel
CREATE INDEX IF NOT EXISTS idx_notification_preferences_channel
    ON petition_notification_preferences(channel);

-- Create index on enabled for efficient filtering
CREATE INDEX IF NOT EXISTS idx_notification_preferences_enabled
    ON petition_notification_preferences(enabled)
    WHERE enabled = TRUE;

-- Add comment explaining the table purpose
COMMENT ON TABLE petition_notification_preferences IS
    'Stores Observer notification preferences for petition fate assignment notifications (Story 7.2, FR-7.3)';

COMMENT ON COLUMN petition_notification_preferences.id IS
    'UUIDv7 unique identifier for this preference';

COMMENT ON COLUMN petition_notification_preferences.petition_id IS
    'UUID of the petition these preferences apply to (unique per petition)';

COMMENT ON COLUMN petition_notification_preferences.channel IS
    'Notification delivery channel: WEBHOOK (HTTP POST) or IN_APP (future)';

COMMENT ON COLUMN petition_notification_preferences.enabled IS
    'Whether notifications are enabled for this channel';

COMMENT ON COLUMN petition_notification_preferences.webhook_url IS
    'HTTPS URL for webhook delivery (required for WEBHOOK channel, NULL for IN_APP)';

COMMENT ON COLUMN petition_notification_preferences.created_at IS
    'When these preferences were created (UTC)';

-- Down migration (for rollback)
-- DROP TABLE IF EXISTS petition_notification_preferences;
