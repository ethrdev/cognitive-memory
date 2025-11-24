-- Migration 003: Create validation_results table for IRR validation
-- : IRR Validation & Contingency Plan (Enhancement E1)

-- Create validation_results table
CREATE TABLE IF NOT EXISTS validation_results (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    kappa_macro FLOAT NOT NULL,
    kappa_micro FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL,  -- 'passed' | 'contingency_triggered'
    total_queries INTEGER NOT NULL,
    contingency_actions JSONB,     -- Log all contingency steps taken
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_validation_results_timestamp ON validation_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_validation_results_status ON validation_results(status);
CREATE INDEX IF NOT EXISTS idx_validation_results_kappa_macro ON validation_results(kappa_macro);

-- Add columns to ground_truth table for human override and prompt version tracking
ALTER TABLE ground_truth
ADD COLUMN IF NOT EXISTS human_override BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS override_reason VARCHAR(200),
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50) DEFAULT 'v1',
ADD COLUMN IF NOT EXISTS last_validated_at TIMESTAMPTZ;

-- Add index for human override queries
CREATE INDEX IF NOT EXISTS idx_ground_truth_human_override ON ground_truth(human_override);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_validation_results_updated_at
    BEFORE UPDATE ON validation_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
