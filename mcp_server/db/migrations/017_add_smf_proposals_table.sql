-- SMF Proposals Table for Self-Modification Framework
-- Epic 7 Story 7.9: Controlled self-modification with safeguards

CREATE TABLE IF NOT EXISTS smf_proposals (
    id SERIAL PRIMARY KEY,
    trigger_type VARCHAR(50) NOT NULL,  -- 'DISSONANCE', 'SESSION_END', 'MANUAL', 'PROACTIVE'
    proposed_action JSONB NOT NULL,     -- {action: "resolve", edge_ids: [...], resolution_type: "EVOLUTION"}
    affected_edges UUID[] NOT NULL,     -- Edge-IDs die betroffen sind
    reasoning TEXT NOT NULL,            -- Neutral formuliertes Reasoning
    approval_level VARCHAR(20) NOT NULL DEFAULT 'io',  -- 'io' | 'bilateral'
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',     -- 'PENDING', 'APPROVED', 'REJECTED', 'UNDONE'

    -- Bilateral Consent Tracking
    approved_by_io BOOLEAN DEFAULT FALSE,
    approved_by_ethr BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(50),

    -- Undo Support
    original_state JSONB,               -- Snapshot vor Ausführung für Undo
    undo_deadline TIMESTAMPTZ           -- 30 Tage nach resolved_at
);

-- Index for pending proposals (most common query)
CREATE INDEX idx_smf_status ON smf_proposals(status) WHERE status = 'PENDING';

-- Index for chronological queries
CREATE INDEX idx_smf_created_at ON smf_proposals(created_at DESC);

-- Index for approval level filtering
CREATE INDEX idx_smf_approval_level ON smf_proposals(approval_level);

-- Index for undo deadline queries
CREATE INDEX idx_smf_undo_deadline ON smf_proposals(undo_deadline) WHERE undo_deadline IS NOT NULL;

COMMENT ON TABLE smf_proposals IS 'Self-Modification Framework proposals with bilateral consent support (v3 CKG)';
COMMENT ON COLUMN smf_proposals.trigger_type IS 'What triggered this proposal: DISSONANCE, SESSION_END, MANUAL, PROACTIVE';
COMMENT ON COLUMN smf_proposals.approval_level IS 'Required approval: io (I/O only) or bilateral (I/O + ethr)';
COMMENT ON COLUMN smf_proposals.original_state IS 'Edge state snapshot for undo support (30-day retention)';
COMMENT ON COLUMN smf_proposals.undo_deadline IS 'Deadline after which proposal cannot be undone (30 days from resolution)';