-- Create user_settings table and migrate AI settings
-- This migration creates the new user_settings table and migrates existing AI settings

-- Step 1: Create the user_settings table

-- For PostgreSQL
DO $$
BEGIN
  -- Create user_settings table
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'ioflow' 
    AND table_name = 'user_settings'
  ) THEN
    CREATE TABLE ioflow.user_settings (
      id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
      user_id VARCHAR(36) NOT NULL REFERENCES ioflow.users(user_id) ON DELETE CASCADE,
      setting_type VARCHAR(50) NOT NULL,
      setting_data JSONB NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT unique_user_setting_type UNIQUE (user_id, setting_type)
    );
    
    -- Create index on user_id and setting_type for performance
    CREATE INDEX idx_user_settings_user_id ON ioflow.user_settings(user_id);
    CREATE INDEX idx_user_settings_type ON ioflow.user_settings(setting_type);
  END IF;
  
  -- Migrate existing AI settings from users table (if they exist)
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_schema = 'ioflow' 
    AND table_name = 'users' 
    AND column_name = 'ai_model_provider'
  ) THEN
    -- Insert AI configurations for users who have them
    INSERT INTO ioflow.user_settings (user_id, setting_type, setting_data)
    SELECT 
      user_id,
      'ai_config',
      jsonb_build_object(
        'provider', ai_model_provider,
        'model_name', ai_model_name,
        'api_key_hash', ai_api_key_hash,
        'api_endpoint', ai_api_endpoint,
        'model_config', COALESCE(ai_settings, '{}')::jsonb,
        'extra_settings', '{}'::jsonb
      )
    FROM ioflow.users
    WHERE ai_model_provider IS NOT NULL
    ON CONFLICT (user_id, setting_type) DO NOTHING;
    
    -- Drop the old AI columns from users table
    ALTER TABLE ioflow.users 
    DROP COLUMN IF EXISTS ai_model_provider,
    DROP COLUMN IF EXISTS ai_model_name,
    DROP COLUMN IF EXISTS ai_api_key_hash,
    DROP COLUMN IF EXISTS ai_api_endpoint,
    DROP COLUMN IF EXISTS ai_settings;
  END IF;
END
$$;

-- For SQLite (run these commands separately)
-- Note: SQLite doesn't support DROP COLUMN, so we need to recreate the table

/*
-- SQLite migration steps:

-- 1. Create user_settings table
CREATE TABLE user_settings (
  id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  setting_type TEXT NOT NULL,
  setting_data TEXT NOT NULL, -- JSON stored as TEXT
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, setting_type)
);

-- 2. Create indexes
CREATE INDEX idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX idx_user_settings_type ON user_settings(setting_type);

-- 3. Migrate existing AI data (if columns exist)
INSERT INTO user_settings (user_id, setting_type, setting_data)
SELECT 
  user_id,
  'ai_config',
  json_object(
    'provider', ai_model_provider,
    'model_name', ai_model_name,
    'api_key_hash', ai_api_key_hash,
    'api_endpoint', ai_api_endpoint,
    'model_config', COALESCE(ai_settings, '{}'),
    'extra_settings', '{}'
  )
FROM users
WHERE ai_model_provider IS NOT NULL;

-- 4. To remove AI columns from users table in SQLite, we need to:
-- a) Create new users table without AI columns
-- b) Copy data from old table
-- c) Drop old table and rename new one
-- This is complex and risky, so we'll leave the columns for now
-- They will simply be ignored by the new code

*/