-- Add AI configuration fields to users table
-- This migration adds support for user-specific AI model configuration

-- For PostgreSQL
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'ioflow' 
    AND table_name = 'users' 
    AND column_name = 'ai_model_provider'
  ) THEN
    ALTER TABLE ioflow.users 
    ADD COLUMN ai_model_provider VARCHAR(50),
    ADD COLUMN ai_model_name VARCHAR(100),
    ADD COLUMN ai_api_key_hash VARCHAR(255),
    ADD COLUMN ai_api_endpoint VARCHAR(500),
    ADD COLUMN ai_settings JSONB;
  END IF;
END
$$;

-- For SQLite (alternative syntax)
-- ALTER TABLE users ADD COLUMN ai_model_provider TEXT;
-- ALTER TABLE users ADD COLUMN ai_model_name TEXT;
-- ALTER TABLE users ADD COLUMN ai_api_key_hash TEXT;
-- ALTER TABLE users ADD COLUMN ai_api_endpoint TEXT;
-- ALTER TABLE users ADD COLUMN ai_settings TEXT; -- JSON stored as TEXT in SQLite