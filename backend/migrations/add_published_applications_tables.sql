-- Migration: Add Published Applications Tables
-- Date: 2025-01-17
-- Description: Add tables for flow-to-application publishing system

-- Published Applications table
CREATE TABLE published_applications (
    published_app_id VARCHAR(36) PRIMARY KEY,
    flow_id VARCHAR(36) NOT NULL,
    app_id VARCHAR(36) NOT NULL REFERENCES applications(app_id),
    created_by VARCHAR(36) NOT NULL REFERENCES users(user_id),
    tenant_id VARCHAR(36) REFERENCES tenants(tenant_id),
    app_key VARCHAR(255) UNIQUE NOT NULL,
    flow_name VARCHAR(255) NOT NULL,
    published_version VARCHAR(20) DEFAULT '1.0.0',
    flow_analysis TEXT, -- JSON stored as text for SQLite
    generation_config TEXT, -- JSON stored as text for SQLite
    parameter_mappings TEXT, -- JSON stored as text for SQLite
    status VARCHAR(20) DEFAULT 'active',
    auto_update BOOLEAN DEFAULT FALSE,
    last_sync_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Published Application Versions table
CREATE TABLE published_application_versions (
    version_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL REFERENCES published_applications(published_app_id),
    version_number VARCHAR(20) NOT NULL,
    flow_definition TEXT, -- JSON stored as text for SQLite
    generated_application TEXT, -- JSON stored as text for SQLite
    changes_summary TEXT, -- JSON stored as text for SQLite
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flow Application Dependencies table
CREATE TABLE flow_application_dependencies (
    dependency_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL REFERENCES published_applications(published_app_id),
    depends_on_app_id VARCHAR(36) NOT NULL REFERENCES applications(app_id),
    dependency_type VARCHAR(50) NOT NULL,
    dependency_name VARCHAR(255) NOT NULL,
    is_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parameter Mappings table
CREATE TABLE parameter_mappings (
    mapping_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL REFERENCES published_applications(published_app_id),
    service_id VARCHAR(36) REFERENCES application_services(service_id),
    parameter_name VARCHAR(255) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL,
    flow_variable_path VARCHAR(500) NOT NULL,
    service_parameter_name VARCHAR(255) NOT NULL,
    transformation_rule TEXT, -- JSON stored as text for SQLite
    is_required BOOLEAN DEFAULT FALSE,
    default_value TEXT, -- JSON stored as text for SQLite
    validation_schema TEXT, -- JSON stored as text for SQLite
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flow Execution Bridges table
CREATE TABLE flow_execution_bridges (
    bridge_id VARCHAR(36) PRIMARY KEY,
    published_app_id VARCHAR(36) NOT NULL REFERENCES published_applications(published_app_id),
    execution_id VARCHAR(36),
    service_call_id VARCHAR(255) NOT NULL,
    input_parameters TEXT, -- JSON stored as text for SQLite
    mapped_parameters TEXT, -- JSON stored as text for SQLite
    execution_status VARCHAR(50) DEFAULT 'pending',
    execution_result TEXT, -- JSON stored as text for SQLite
    error_details TEXT, -- JSON stored as text for SQLite
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time_ms INTEGER
);

-- Create indexes for better performance
CREATE INDEX idx_published_apps_flow_id ON published_applications(flow_id);
CREATE INDEX idx_published_apps_app_key ON published_applications(app_key);
CREATE INDEX idx_published_apps_status ON published_applications(status);
CREATE INDEX idx_published_apps_created_by ON published_applications(created_by);

CREATE INDEX idx_published_versions_app_id ON published_application_versions(published_app_id);
CREATE INDEX idx_published_versions_version ON published_application_versions(version_number);

CREATE INDEX idx_flow_dependencies_published_app ON flow_application_dependencies(published_app_id);
CREATE INDEX idx_flow_dependencies_depends_on ON flow_application_dependencies(depends_on_app_id);

CREATE INDEX idx_parameter_mappings_published_app ON parameter_mappings(published_app_id);
CREATE INDEX idx_parameter_mappings_service ON parameter_mappings(service_id);
CREATE INDEX idx_parameter_mappings_type ON parameter_mappings(parameter_type);

CREATE INDEX idx_execution_bridges_published_app ON flow_execution_bridges(published_app_id);
CREATE INDEX idx_execution_bridges_status ON flow_execution_bridges(execution_status);
CREATE INDEX idx_execution_bridges_call_id ON flow_execution_bridges(service_call_id);

-- Add some helpful comments
PRAGMA table_info(published_applications);
PRAGMA table_info(published_application_versions);
PRAGMA table_info(flow_application_dependencies);
PRAGMA table_info(parameter_mappings);
PRAGMA table_info(flow_execution_bridges);