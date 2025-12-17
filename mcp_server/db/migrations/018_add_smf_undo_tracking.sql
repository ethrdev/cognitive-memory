-- Add undo tracking columns to smf_proposals table
-- Required for AC #11: MCP Tool smf_undo (30-Tage Fenster)

ALTER TABLE smf_proposals
ADD COLUMN IF NOT EXISTS undone_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS undone_by VARCHAR(50);

-- Add index for undone proposals
CREATE INDEX IF NOT EXISTS idx_smf_undone_at ON smf_proposals(undone_at) WHERE undone_at IS NOT NULL;

COMMENT ON COLUMN smf_proposals.undone_at IS 'When the proposal was undone (via smf_undo)';
COMMENT ON COLUMN smf_proposals.undone_by IS 'Who performed the undo (I/O or ethr)';