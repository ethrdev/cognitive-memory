-- Migration 022: Add memory_sector Column for Memory Sector Foundation (Epic 8)
-- Story 8.1: Schema Migration & Data Classification
--
-- Purpose: Klassifiziert alle Edges in Memory Sektoren für OpenMemory Integration
-- Dependencies: Migration 021 (edges table with last_engaged must exist)
-- Breaking Changes: KEINE - alle Felder haben Defaults, Migration ist idempotent
--
-- Memory Sectors (OpenMemory Specification):
--   - semantic:      Faktenwissen, Konzepte, abstrakte Informationen (DEFAULT)
--   - emotional:     Emotionsgeladene Erinnerungen mit valence metadata
--   - episodic:      Episode Memories mit shared_experience context
--   - procedural:    Skills, "can-do", learned capabilities
--   - reflective:   Reflexionen, Realizationen, self-awareness

-- ============================================================================
-- PHASE 1: SCHEMA MIGRATION - Add memory_sector Column
-- ============================================================================

-- Column: memory_sector - Memory Sektor-Klassifizierung für Edge-Typisierung
-- Type: VARCHAR(20) (not ENUM to avoid migration complexity)
-- Default: 'semantic' (safe default for unmigrated edges)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'memory_sector'
    ) THEN
        ALTER TABLE edges ADD COLUMN memory_sector VARCHAR(20) DEFAULT 'semantic';
    END IF;
END $$;

-- ============================================================================
-- PHASE 2: DATA MIGRATION - Classify Existing Edges
-- ============================================================================
-- Classification Rules (Priority Order - first match wins):
--   1. Emotional: edges with emotional_valence property
--   2. Episodic:  edges with context_type = "shared_experience"
--   3. Procedural: edges with relation IN (LEARNED, CAN_DO)
--   4. Reflective: edges with relation IN (REFLECTS, REALIZED)
--   5. Semantic:   all other edges (default)

-- Rule 1: Emotional - edges with emotional_valence property
UPDATE edges
SET memory_sector = 'emotional'
WHERE properties->>'emotional_valence' IS NOT NULL
  AND memory_sector = 'semantic';

-- Rule 2: Episodic - shared experiences
UPDATE edges
SET memory_sector = 'episodic'
WHERE properties->>'context_type' = 'shared_experience'
  AND memory_sector = 'semantic';

-- Rule 3: Procedural - learning-related relations
UPDATE edges
SET memory_sector = 'procedural'
WHERE relation IN ('LEARNED', 'CAN_DO')
  AND memory_sector = 'semantic';

-- Rule 4: Reflective - reflection-related relations
UPDATE edges
SET memory_sector = 'reflective'
WHERE relation IN ('REFLECTS', 'REFLECTS_ON', 'REALIZED')
  AND memory_sector = 'semantic';

-- Rule 5: Semantic - all remaining edges (already set as default)

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify column exists:
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'edges' AND column_name = 'memory_sector';

-- Verify data migration - sector distribution:
-- SELECT memory_sector, COUNT(*) as edge_count
-- FROM edges
-- GROUP BY memory_sector
-- ORDER BY edge_count DESC;

-- Verify classification rules - emotional edges:
-- SELECT id, relation, properties->>'emotional_valence' as valence, memory_sector
-- FROM edges
-- WHERE properties->>'emotional_valence' IS NOT NULL
-- LIMIT 10;

-- Verify classification rules - episodic edges:
-- SELECT id, relation, properties->>'context_type' as context, memory_sector
-- FROM edges
-- WHERE properties->>'context_type' = 'shared_experience'
-- LIMIT 10;

-- Verify classification rules - procedural edges:
-- SELECT id, relation, memory_sector
-- FROM edges
-- WHERE relation IN ('LEARNED', 'CAN_DO')
-- LIMIT 10;

-- Verify classification rules - reflective edges:
-- SELECT id, relation, memory_sector
-- FROM edges
-- WHERE relation IN ('REFLECTS', 'REALIZED')
-- LIMIT 10;

-- Verify no NULL values:
-- SELECT COUNT(*) as null_count FROM edges WHERE memory_sector IS NULL;

-- Verify original properties are preserved (sample check):
-- SELECT id, relation, properties, memory_sector
-- FROM edges
-- ORDER BY created_at DESC
-- LIMIT 5;
