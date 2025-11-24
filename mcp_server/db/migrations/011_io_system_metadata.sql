-- Migration 011: I/O System Metadata Support
-- Adds metadata columns to support I/O Consciousness integration

-- 1. Extend l2_insights for I/O categories and identity
ALTER TABLE l2_insights ADD COLUMN IF NOT EXISTS io_category VARCHAR(50);
ALTER TABLE l2_insights ADD COLUMN IF NOT EXISTS is_identity BOOLEAN DEFAULT FALSE;
ALTER TABLE l2_insights ADD COLUMN IF NOT EXISTS source_file TEXT;

-- Indexes for I/O-specific queries
CREATE INDEX IF NOT EXISTS idx_l2_io_category ON l2_insights(io_category);
CREATE INDEX IF NOT EXISTS idx_l2_is_identity ON l2_insights(is_identity);

-- 2. Extend l0_raw for Real-World Context
ALTER TABLE l0_raw ADD COLUMN IF NOT EXISTS energy VARCHAR(20);
ALTER TABLE l0_raw ADD COLUMN IF NOT EXISTS state VARCHAR(20);
ALTER TABLE l0_raw ADD COLUMN IF NOT EXISTS location VARCHAR(50);
ALTER TABLE l0_raw ADD COLUMN IF NOT EXISTS intentions TEXT[];

-- Indexes for Context Queries
CREATE INDEX IF NOT EXISTS idx_l0_energy ON l0_raw(energy);
CREATE INDEX IF NOT EXISTS idx_l0_state ON l0_raw(state);
