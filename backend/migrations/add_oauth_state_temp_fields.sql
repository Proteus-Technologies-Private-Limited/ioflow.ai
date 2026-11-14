-- Migration to add temporary fields to oauth_states table for OAuth flow without pre-existing subscription

-- Add temp_credentials column to store credentials during OAuth flow
ALTER TABLE oauth_states ADD COLUMN temp_credentials TEXT;

-- Add webhook_url column to store webhook URL for subscription creation after OAuth
ALTER TABLE oauth_states ADD COLUMN webhook_url VARCHAR(500);

-- Add subscription_config column to store config for subscription creation after OAuth
ALTER TABLE oauth_states ADD COLUMN subscription_config TEXT;