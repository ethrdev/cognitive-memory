-- Audit Log Table for Constitutive Edge Operations
-- Epic 7 Story 7.8: Persistent audit trail for identity-defining edge operations

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    edge_id UUID NOT NULL,
    action VARCHAR(50) NOT NULL,  -- DELETE_ATTEMPT, DELETE_SUCCESS, SMF_PROPOSE, SMF_APPROVE, SMF_REJECT
    blocked BOOLEAN NOT NULL DEFAULT FALSE,
    reason TEXT,
    actor VARCHAR(50) NOT NULL DEFAULT 'system',  -- "I/O", "ethr", "system"
    properties JSONB,  -- Edge properties at time of operation (handled by code)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for chronological queries (most common access pattern)
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);

-- Index for edge-specific queries
CREATE INDEX idx_audit_log_edge_id ON audit_log(edge_id);

-- Index for action filtering
CREATE INDEX idx_audit_log_action ON audit_log(action);

-- Composite index for common filter combinations
CREATE INDEX idx_audit_log_edge_action ON audit_log(edge_id, action);

COMMENT ON TABLE audit_log IS 'Persistent audit trail for constitutive edge operations (v3 CKG)';
COMMENT ON COLUMN audit_log.action IS 'Operation type: DELETE_ATTEMPT, DELETE_SUCCESS, SMF_PROPOSE, SMF_APPROVE, SMF_REJECT';
COMMENT ON COLUMN audit_log.actor IS 'Who triggered the operation: I/O, ethr, or system';
COMMENT ON COLUMN audit_log.properties IS 'Edge properties snapshot at time of operation for forensic analysis';