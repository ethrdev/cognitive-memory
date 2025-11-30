-- Migration 012: Add Graph Tables (Nodes + Edges) for GraphRAG Integration
-- Story 4.1: Graph Schema Migration (Nodes + Edges Tabellen)
--
-- Tables: nodes, edges
-- Purpose: Graph-basierte Speicherung von Entitäten und Beziehungen
-- Integration: Optionaler FK zu l2_insights via vector_id (UUID compatibility)

-- ============================================================================
-- TABLE: nodes - Entitäten im Graph
-- ============================================================================
-- Description: Speichert Entitäten wie Personen, Konzepte, Dokumente etc.
-- UUID PRIMARY KEY für verteilte Systeme und Graph Traversal Performance
CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label VARCHAR(255) NOT NULL,           -- Entitäts-Typ (z.B. 'Person', 'Konzept', 'Dokument')
    name VARCHAR(255) NOT NULL,            -- Eindeutiger Name der Entität
    properties JSONB DEFAULT '{}',        -- Flexible Metadaten
    vector_id INTEGER,                     -- Optional: FK zu l2_insights.id (SERIAL)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique Constraint für Idempotenz (verhindert doppelte Entitäten)
CREATE UNIQUE INDEX idx_nodes_unique ON nodes(label, name);

-- Performance Indexes
CREATE INDEX idx_nodes_label ON nodes(label);
CREATE INDEX idx_nodes_name ON nodes(name);
CREATE INDEX idx_nodes_vector_id ON nodes(vector_id);  -- Für optionalen FK-Join
CREATE INDEX idx_nodes_properties ON nodes USING gin(properties);  -- GIN für JSONB Queries

-- Optionaler Foreign Key zu l2_insights (nullable für Flexibilität)
-- Note: l2_insights.id ist SERIAL, vector_id ist INTEGER für Kompatibilität
ALTER TABLE nodes
ADD CONSTRAINT fk_nodes_vector_id
FOREIGN KEY (vector_id) REFERENCES l2_insights(id) ON DELETE SET NULL;

-- ============================================================================
-- TABLE: edges - Beziehungen zwischen Entitäten
-- ============================================================================
-- Description: Speichert gerichtete Beziehungen zwischen Nodes mit gewichteter Bewertung
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,               -- Ausgangs-Node (von)
    target_id UUID NOT NULL,               -- Ziel-Node (zu)
    relation VARCHAR(255) NOT NULL,        -- Beziehungs-Typ (z.B. 'kennt', 'enthält', 'zitiert')
    weight FLOAT DEFAULT 1.0,             -- Beziehungs-Stärke (0.0-1.0)
    properties JSONB DEFAULT '{}',        -- Flexible Metadaten
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique Constraint für Idempotenz (verhindert doppelte Kanten)
CREATE UNIQUE INDEX idx_edges_unique ON edges(source_id, target_id, relation);

-- Foreign Key Constraints mit CASCADE (lösche Kanten wenn Nodes gelöscht werden)
ALTER TABLE edges
ADD CONSTRAINT fk_edges_source_id
FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE;

ALTER TABLE edges
ADD CONSTRAINT fk_edges_target_id
FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE;

-- Performance Indexes für Graph Traversal
CREATE INDEX idx_edges_source_id ON edges(source_id);     -- Outbound-Queries
CREATE INDEX idx_edges_target_id ON edges(target_id);     -- Inbound-Queries
CREATE INDEX idx_edges_relation ON edges(relation);       -- Gefilterte Traversals
CREATE INDEX idx_edges_weight ON edges(weight);           -- Gewicht-Filtering
CREATE INDEX idx_edges_properties ON edges USING gin(properties);  -- GIN für JSONB

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify tables exist (should return 2 rows)
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('nodes', 'edges');

-- Verify indexes exist (should return all created indexes)
-- SELECT indexname FROM pg_indexes WHERE schemaname='public' AND
--   indexname LIKE 'idx_%nodes%' OR indexname LIKE 'idx_%edges%';

-- Verify foreign keys exist
-- SELECT
--   tc.table_name,
--   kcu.column_name,
--   ccu.table_name AS foreign_table_name,
--   ccu.column_name AS foreign_column_name
-- FROM information_schema.table_constraints AS tc
-- JOIN information_schema.key_column_usage AS kcu
--   ON tc.constraint_name = kcu.constraint_name
--   AND tc.table_schema = kcu.table_schema
-- JOIN information_schema.constraint_column_usage AS ccu
--   ON ccu.constraint_name = tc.constraint_name
--   AND ccu.table_schema = tc.table_schema
-- WHERE tc.constraint_type = 'FOREIGN KEY'
--   AND tc.table_name IN ('nodes', 'edges');

-- Test INSERT für Validierung
-- INSERT INTO nodes (label, name, properties) VALUES
--   ('Test', 'TestNode', '{"type": "validation"}')
-- RETURNING id;
--
-- INSERT INTO edges (source_id, target_id, relation, weight) VALUES
--   ((SELECT id FROM nodes WHERE name = 'TestNode' LIMIT 1),
--    (SELECT id FROM nodes WHERE name = 'TestNode' LIMIT 1),
--    'test_relation', 1.0);