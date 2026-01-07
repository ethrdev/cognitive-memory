-- Migration 021: Add last_engaged Field for Semantic Decay Tracking
-- Issue: Decay wird durch Query-Access zurückgesetzt (2026-01-07)
--
-- Problem: graph_query_neighbors aktualisiert last_accessed für alle
-- zurückgegebenen Edges. Dadurch wird der Ebbinghaus-Decay bei jeder
-- Abfrage zurückgesetzt - was den Decay bedeutungslos macht.
--
-- Solution: Zwei Felder mit unterschiedlicher Semantik:
--   - last_accessed: Technischer Timestamp (bei jeder Lesung)
--   - last_engaged:  Semantischer Timestamp (nur bei aktiver Nutzung)
--
-- Was "Engaged" triggert:
--   ✅ Neue Edge erstellen
--   ✅ Edge-Properties aktualisieren
--   ✅ Resolution erstellen (SMF approve)
--   ✅ Explizite Referenz in io-save
--
-- Was NICHT "Engaged" triggert:
--   ❌ graph_query_neighbors (Query)
--   ❌ graph_find_path (Pathfinding)
--   ❌ get_edge Lookups
--
-- Dependencies: Migration 015 (TGN temporal fields must exist)
-- Breaking Changes: KEINE - calculate_relevance_score() wird umgestellt

-- ============================================================================
-- ALTER TABLE: Add last_engaged Field
-- ============================================================================

-- Field: last_engaged - Wann Edge zuletzt AKTIV genutzt wurde (für Decay)
-- Default: NOW() für neue Edges, Migration setzt auf last_accessed
ALTER TABLE edges
ADD COLUMN IF NOT EXISTS last_engaged TIMESTAMPTZ;

-- ============================================================================
-- DATA MIGRATION: Populate last_engaged from existing data
-- ============================================================================

-- Für existierende Edges: Setze last_engaged auf den besseren Wert von
-- last_accessed oder modified_at (was auch immer vorhanden ist)
UPDATE edges
SET last_engaged = COALESCE(
    -- Prefer modified_at if it's different from created_at (indicates real update)
    CASE
        WHEN modified_at IS NOT NULL AND modified_at != created_at
        THEN modified_at
        ELSE NULL
    END,
    -- Fall back to last_accessed
    last_accessed,
    -- Last resort: created_at
    created_at
)
WHERE last_engaged IS NULL;

-- Set default for future inserts
ALTER TABLE edges
ALTER COLUMN last_engaged SET DEFAULT NOW();

-- ============================================================================
-- INDEX: For Decay-based Queries
-- ============================================================================

-- Index für effiziente Decay-Queries (calculate_relevance_score nutzt last_engaged)
CREATE INDEX IF NOT EXISTS idx_edges_last_engaged ON edges(last_engaged);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify column exists:
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'edges' AND column_name = 'last_engaged';

-- Verify data migration:
-- SELECT id, last_accessed, last_engaged,
--        EXTRACT(days FROM (last_accessed - last_engaged)) as diff_days
-- FROM edges
-- ORDER BY created_at DESC
-- LIMIT 10;

-- Verify no NULL values:
-- SELECT COUNT(*) as null_count FROM edges WHERE last_engaged IS NULL;
