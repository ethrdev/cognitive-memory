-- Migration 024: Add l2_insight_history Table for Audit Trail
-- Story 26.2: UPDATE Operation - History-on-Mutation Pattern (EP-3)
--
-- Purpose: Audit Trail für alle Mutationen (UPDATE/DELETE) auf L2 Insights
-- Dependencies: Migration 001 (l2_insights table must exist)
-- Breaking Changes: KEINE - Neue Tabelle, bestehende Schema unverändert
--
-- EP-3 Pattern: History-on-Mutation
--   - Jede Mutation (UPDATE/DELETE) schreibt History-Eintrag
--   - History wird in GLEICHER Transaction wie Mutation geschrieben
--   - Speichert old_content für Rollback-Fähigkeit
--   - Atomic Rollback: Wenn Transaction fehl schlägt, wird auch History rolled back
--
-- History Use Cases:
--   1. Audit Trail: Wer hat was wann geändert (Accountability)
--   2. Rollback: Old_content ermöglicht Revert auf vorherige Version
--   3. Archäologie: Volle Historie eines Insights sichtbar
--   4. Compliance: GDPR "Right to Explanation" für memory changes
--
-- ============================================================================
-- PHASE 1: SCHEMA MIGRATION - Create l2_insight_history Table
-- ============================================================================

-- Table: l2_insight_history - Audit Trail für Insight Mutationen
CREATE TABLE IF NOT EXISTS l2_insight_history (
    id SERIAL PRIMARY KEY,
    insight_id INTEGER NOT NULL REFERENCES l2_insights(id) ON DELETE CASCADE,
    action VARCHAR(10) NOT NULL CHECK (action IN ('UPDATE', 'DELETE')),
    actor VARCHAR(10) NOT NULL CHECK (actor IN ('I/O', 'ethr')),
    old_content TEXT,
    new_content TEXT,
    old_memory_strength FLOAT,
    new_memory_strength FLOAT,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index: Schnelle Lookups für "Show History for Insight X"
-- Kombinierter Index für insight_id + created_at DESC optimiert
-- häufige Queries: "Show history for insight X ordered by time"
CREATE INDEX IF NOT EXISTS idx_l2_insight_history_insight_id
    ON l2_insight_history(insight_id, created_at DESC);

-- ============================================================================
-- PHASE 2: VERIFICATION QUERIES
-- ============================================================================

-- Verify table exists:
-- SELECT table_name, column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'l2_insight_history'
-- ORDER BY ordinal_position;

-- Verify index exists:
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'l2_insight_history';

-- Verify foreign key constraint:
-- SELECT
--     tc.constraint_name,
--     tc.constraint_type,
--     kcu.column_name,
--     ccu.table_name AS foreign_table_name
-- FROM information_schema.table_constraints AS tc
-- JOIN information_schema.key_column_usage AS kcu
--     ON tc.constraint_name = kcu.constraint_name
-- JOIN information_schema.constraint_column_usage AS ccu
--     ON ccu.constraint_name = tc.constraint_name
-- WHERE tc.table_name = 'l2_insight_history';

-- ============================================================================
-- PHASE 3: ROLLBACK - DOWN Migration (für Rollback Szenario)
-- ============================================================================

-- Für Rollback: Table und Index entfernen (IF EXISTS für Safety)
-- DROP TABLE IF EXISTS l2_insight_history;

-- ============================================================================
-- PHASE 4: PERFORMANCE OPTIMIZATION (NFR-P1: <100ms P95)
-- ============================================================================

-- Index Analysis:
--   - idx_l2_insight_history_insight_id ist ein COMPOSITE Index
--   - (insight_id, created_at DESC) ermöglicht "Index-Only Scan" für History Queries
--   - DESC ordering vermeidet explicit SORT Operation
--
-- Performance Notes:
--   - INSERT Latency: < 5ms (Single row insert mit Index ist schnell)
--   - SELECT Latency: < 20ms (Index scan für insight_id + created_at)
--   - Foreign Key Check: < 2ms (l2_insights.id ist Primary Key)
--   - Overall UPDATE Operation Target: < 100ms P95 (NFR-P1)

-- ============================================================================
-- PHASE 5: UP-DOWN-UP CYCLE TEST (für Migration 024 Test Suite)
-- ============================================================================
-- Test Sequence:
--   1. UP: Migration ausführen (späterer Test)
--   2. VERIFY: Table existiert, Index existiert, FK constraint aktiv
--   3. DOWN: Rollback ausführen
--   4. VERIFY: Table entfernt
--   5. UP: Migration erneut ausführen
--   6. VERIFY: Table wieder da, idempotent

-- Sample Test Data (für manuelle Tests):
-- INSERT INTO l2_insight_history (insight_id, action, actor, old_content, new_content, reason)
-- VALUES (42, 'UPDATE', 'I/O', 'Old content', 'New content', 'Test update');

-- Sample Query: Show History for Insight 42
-- SELECT * FROM l2_insight_history
-- WHERE insight_id = 42
-- ORDER BY created_at DESC
-- LIMIT 10;
