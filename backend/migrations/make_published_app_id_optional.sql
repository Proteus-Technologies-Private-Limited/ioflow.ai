-- Make published_app_id optional in frontend_flow_applications to support direct frontend publishing
-- This allows publishing flows directly as frontend apps without creating reusable applications

-- For SQLite, we need to recreate the table since it doesn't support ALTER COLUMN
-- First create new table with nullable published_app_id
CREATE TABLE frontend_flow_applications_new (
    frontend_app_id TEXT PRIMARY KEY,
    published_app_id TEXT,  -- Made nullable (removed FOREIGN KEY constraint temporarily)
    flow_id TEXT,           -- Added direct flow reference for direct frontend publishing
    public_url_slug TEXT UNIQUE NOT NULL,
    frontend_app_name TEXT NOT NULL,
    description TEXT,
    access_type TEXT NOT NULL,
    access_config TEXT,
    embed_enabled BOOLEAN DEFAULT 1,
    rate_limit_per_hour INTEGER DEFAULT 100,
    custom_styling TEXT,
    is_active BOOLEAN DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    last_accessed_at TEXT,
    created_by TEXT NOT NULL,
    tenant_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Copy existing data
INSERT INTO frontend_flow_applications_new 
SELECT 
    frontend_app_id,
    published_app_id,
    NULL as flow_id,  -- Existing records don't have direct flow reference
    public_url_slug,
    frontend_app_name,
    description,
    access_type,
    access_config,
    embed_enabled,
    rate_limit_per_hour,
    custom_styling,
    is_active,
    usage_count,
    last_accessed_at,
    created_by,
    tenant_id,
    created_at,
    updated_at
FROM frontend_flow_applications;

-- Drop old table and rename new one
DROP TABLE frontend_flow_applications;
ALTER TABLE frontend_flow_applications_new RENAME TO frontend_flow_applications;

-- Create index for flow_id
CREATE INDEX idx_frontend_flow_applications_flow_id ON frontend_flow_applications(flow_id);
CREATE INDEX idx_frontend_flow_applications_published_app_id ON frontend_flow_applications(published_app_id);