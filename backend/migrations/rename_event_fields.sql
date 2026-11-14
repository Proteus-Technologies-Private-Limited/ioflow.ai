-- Migration to rename trigger_type to event_type and trigger_config to event_configuration

-- For SQLite
ALTER TABLE application_events RENAME COLUMN trigger_type TO event_type;
ALTER TABLE application_events RENAME COLUMN trigger_config TO event_configuration;