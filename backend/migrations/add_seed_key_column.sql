-- Migration to add seed_key column to applications table

-- Add seed_key column to applications table
ALTER TABLE applications ADD COLUMN seed_key VARCHAR(100);

-- Create index for faster lookups
CREATE INDEX idx_applications_seed_key ON applications(seed_key);