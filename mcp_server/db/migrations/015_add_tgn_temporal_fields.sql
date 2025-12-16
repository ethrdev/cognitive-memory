-- Migration 015: Add TGN Temporal Fields for Edges
-- Story 7.1: TGN Minimal - Schema-Migration
--
-- Purpose: Temporale Metadaten für Edges zur Dissonance Engine Unterstützung
-- Dependencies: Migration 012 (edges table must exist)
-- Breaking Changes: KEINE - alle Felder haben Defaults

-- ============================================================================
-- ALTER TABLE: Add TGN Temporal Fields
-- ============================================================================

-- Field 1: modified_at - Wann Edge zuletzt geändert (für Dissonance "alt vs. neu")
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS modified_at TIMESTAMPTZ DEFAULT NOW();

-- Field 2: last_accessed - Wann Edge zuletzt gelesen (für Decay-Berechnung)
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMPTZ DEFAULT NOW();

-- Field 3: access_count - Wie oft gelesen (für Memory Strength in Story 7.3)
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;

-- CHECK Constraint für non-negative access_count (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_edges_access_count_non_negative') THEN
        ALTER TABLE edges ADD CONSTRAINT chk_edges_access_count_non_negative CHECK (access_count >= 0);
    END IF;
END $$;

-- ============================================================================
-- INDEX: For Decay-based Queries
-- ============================================================================

-- Index für effiziente Decay-Queries (Story 7.3 wird nach last_accessed filtern)
CREATE INDEX IF NOT EXISTS idx_edges_last_accessed ON edges(last_accessed);

-- Optional: Composite Index für relevance_score Berechnung
CREATE INDEX IF NOT EXISTS idx_edges_access_stats ON edges(last_accessed, access_count);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify columns exist:
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'edges'
-- AND column_name IN ('modified_at', 'last_accessed', 'access_count');

-- Verify index exists:
-- SELECT indexname FROM pg_indexes
-- WHERE tablename = 'edges' AND indexname = 'idx_edges_last_accessed';

-- Verify existing edges have defaults:
-- SELECT id, modified_at, last_accessed, access_count
-- FROM edges LIMIT 5;