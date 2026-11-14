-- Migration: Add Frontend Flow Application Tables
-- Description: Add tables for frontend/public flow applications with access control

-- Create frontend_flow_applications table
CREATE TABLE IF NOT EXISTS frontend_flow_applications (
    frontend_app_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(6)))),
    published_app_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    tenant_id TEXT,
    public_url_slug TEXT UNIQUE NOT NULL,
    frontend_app_name TEXT NOT NULL,
    description TEXT,
    access_type TEXT NOT NULL,
    access_config TEXT, -- JSON
    embed_enabled BOOLEAN DEFAULT 1,
    rate_limit_per_hour INTEGER DEFAULT 100,
    custom_styling TEXT, -- JSON
    is_active BOOLEAN DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (published_app_id) REFERENCES published_applications(published_app_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE SET NULL
);

-- Create frontend_app_access_logs table
CREATE TABLE IF NOT EXISTS frontend_app_access_logs (
    log_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(6)))),
    frontend_app_id TEXT NOT NULL,
    ip_address TEXT NOT NULL,
    user_agent TEXT,
    access_type TEXT NOT NULL, -- 'view', 'execute'
    execution_success BOOLEAN,
    execution_time_ms INTEGER,
    error_message TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE
);

-- Create frontend_app_embed_configs table  
CREATE TABLE IF NOT EXISTS frontend_app_embed_configs (
    config_id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(6)))),
    frontend_app_id TEXT NOT NULL,
    embed_type TEXT NOT NULL, -- 'iframe', 'widget', 'sdk'
    config_name TEXT NOT NULL,
    embed_settings TEXT, -- JSON
    custom_css TEXT,
    callback_urls TEXT, -- JSON
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (frontend_app_id) REFERENCES frontend_flow_applications(frontend_app_id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_frontend_apps_slug ON frontend_flow_applications(public_url_slug);
CREATE INDEX IF NOT EXISTS idx_frontend_apps_published_app ON frontend_flow_applications(published_app_id);
CREATE INDEX IF NOT EXISTS idx_frontend_apps_created_by ON frontend_flow_applications(created_by);
CREATE INDEX IF NOT EXISTS idx_frontend_apps_tenant ON frontend_flow_applications(tenant_id);
CREATE INDEX IF NOT EXISTS idx_frontend_apps_active ON frontend_flow_applications(is_active);

CREATE INDEX IF NOT EXISTS idx_access_logs_frontend_app ON frontend_app_access_logs(frontend_app_id);
CREATE INDEX IF NOT EXISTS idx_access_logs_ip ON frontend_app_access_logs(ip_address);
CREATE INDEX IF NOT EXISTS idx_access_logs_accessed_at ON frontend_app_access_logs(accessed_at);

CREATE INDEX IF NOT EXISTS idx_embed_configs_frontend_app ON frontend_app_embed_configs(frontend_app_id);
CREATE INDEX IF NOT EXISTS idx_embed_configs_active ON frontend_app_embed_configs(is_active);

-- Create trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_frontend_apps_timestamp
    AFTER UPDATE ON frontend_flow_applications
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE frontend_flow_applications SET updated_at = CURRENT_TIMESTAMP WHERE frontend_app_id = NEW.frontend_app_id;
END;

CREATE TRIGGER IF NOT EXISTS update_embed_configs_timestamp
    AFTER UPDATE ON frontend_app_embed_configs
    FOR EACH ROW
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE frontend_app_embed_configs SET updated_at = CURRENT_TIMESTAMP WHERE config_id = NEW.config_id;
END;