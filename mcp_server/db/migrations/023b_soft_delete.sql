-- Migration 023b: Add Soft-Delete Fields to l2_insights Table
-- Story 26.3: DELETE Operation (parallel implementation with Story 26.2)
--
-- Purpose: Soft-Delete Support für Insights (kein echtes DELETE)
-- Dependencies: Migration 001 (l2_insights table must exist)
-- Breaking Changes: KEINE - Neue Spalten mit DEFAULT FALSE
--
-- Soft-Delete Pattern:
--   - is_deleted=TRUE markiert gelöschte Insights
--   - DELETE Operation setzt nur Flags, löscht keine Daten
--   - Alle Queries müssen WHERE is_deleted = FALSE verwenden
--   - Audit Trail bleibt vollständig erhalten
--
-- Soft-Delete Use Cases:
--   1. GDPR "Right to be Forgotten" mit Audit Trail
--   2. Undo/Delete Story 26.3 kann Soft-Delete rückgängig machen
--   3. Compliance: Gelöschte Daten bleiben für Audits sichtbar
--   4. Analytics: "Deleted Insights" Queries möglich
--
-- ============================================================================
-- PHASE 1: ADD SOFT-DELETE COLUMNS
-- ============================================================================

-- Add soft-delete flags to l2_insights table
ALTER TABLE l2_insights
ADD COLUMN IF NOT EXISTS is_deleted BOOL DEFAULT FALSE,

ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ,

ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(10),

ADD COLUMN IF NOT EXISTS deleted_reason TEXT;

-- ============================================================================
-- PHASE 2: CREATE INDEX FOR PERFORMANCE
-- ============================================================================

-- Index: Schnelle Lookups für "aktive Insights" (is_deleted = FALSE)
CREATE INDEX IF NOT EXISTS idx_l2_insights_is_deleted
ON l2_insights(is_deleted) WHERE is_deleted = FALSE;

-- ============================================================================
-- PHASE 3: VERIFICATION QUERIES
-- ============================================================================

-- Verify columns exist:
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'l2_insights'
--   AND column_name IN ('is_deleted', 'deleted_at', 'deleted_by', 'deleted_reason')
-- ORDER BY column_name;

-- Verify index exists:
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'l2_insights'
--   AND indexname = 'idx_l2_insights_is_deleted';

-- ============================================================================
-- PHASE 4: ROLLBACK - DOWN Migration (für Rollback Szenario)
-- ============================================================================

-- Für Rollback: Spalten entfernen (ACHTUNG: Daten verloren!)
-- ALTER TABLE l2_insights DROP COLUMN IF EXISTS is_deleted;
-- ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_at;
-- ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_by;
-- ALTER TABLE l2_insights DROP COLUMN IF EXISTS deleted_reason;

-- ============================================================================
-- PHASE 5: MIGRATION NOTES
-- ============================================================================

-- Migration Pattern:
--   - IF NOT EXISTS ensures idempotency (safe to re-run)
--   - DEFAULT FALSE ensures backward compatibility
--   - Existing rows automatically have is_deleted=FALSE
--
-- Query Updates Required:
--   - Alle SELECT queries müssen WHERE is_deleted = FALSE hinzufügen
--   - Story 26.2 UPDATE: Already using is_deleted = FALSE
--   - Story 26.3 DELETE: Will set is_deleted=TRUE
--
-- Performance Notes:
--   - Partial Index (WHERE is_deleted = FALSE) ist sehr effizient
--   - Index Size = Nur aktive Insights (kleiner als Full Table)
--   - Lookup Speed < 5ms für aktive Insights
