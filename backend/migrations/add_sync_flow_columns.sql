-- Migration to add synchronous flow support columns

-- Add columns to flows table
ALTER TABLE flows ADD COLUMN is_synchronous BOOLEAN DEFAULT 0;
ALTER TABLE flows ADD COLUMN sync_timeout INTEGER DEFAULT 30;

-- Add columns to flow_executions table
ALTER TABLE flow_executions ADD COLUMN result_data TEXT;
ALTER TABLE flow_executions ADD COLUMN response_status INTEGER;
ALTER TABLE flow_executions ADD COLUMN response_headers TEXT;

-- Create indexes for better query performance
CREATE INDEX idx_flows_is_synchronous ON flows(is_synchronous);
CREATE INDEX idx_flow_executions_response_status ON flow_executions(response_status);