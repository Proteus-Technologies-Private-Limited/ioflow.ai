-- Migration for SQLite: Add API key and custom endpoint support

-- Add columns to application_subscriptions table
ALTER TABLE application_subscriptions ADD COLUMN invocation_api_key TEXT UNIQUE;
ALTER TABLE application_subscriptions ADD COLUMN api_key_created_at TIMESTAMP;
ALTER TABLE application_subscriptions ADD COLUMN api_key_last_used_at TIMESTAMP;

-- Add columns to application_events table
ALTER TABLE application_events ADD COLUMN api_endpoint TEXT UNIQUE;
ALTER TABLE application_events ADD COLUMN sync_mode TEXT DEFAULT 'asynchronous';

-- Create index on invocation_api_key for faster lookups
CREATE INDEX IF NOT EXISTS ix_application_subscriptions_invocation_api_key 
ON application_subscriptions(invocation_api_key);

-- Note: SQLite doesn't support adding UNIQUE constraint to existing column
-- The UNIQUE constraint is already added in the ALTER TABLE statement above