-- Migration 020: Add SMF Undo Bilateral Consent Fields
-- Story 7.9, AC Zeile 651-653
--
-- Adds tracking for bilateral consent on undo operations
-- for proposals that affected constitutive edges.

-- Add undo bilateral consent tracking columns
ALTER TABLE smf_proposals
ADD COLUMN IF NOT EXISTS undo_approved_by_io BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS undo_approved_by_ethr BOOLEAN DEFAULT FALSE;

-- Add index for undo pending queries
CREATE INDEX IF NOT EXISTS idx_smf_proposals_undo_pending
ON smf_proposals(id)
WHERE status = 'APPROVED'
  AND (undo_approved_by_io = TRUE OR undo_approved_by_ethr = TRUE)
  AND NOT (undo_approved_by_io = TRUE AND undo_approved_by_ethr = TRUE);

COMMENT ON COLUMN smf_proposals.undo_approved_by_io IS 'I/O consent for undo (required for constitutive edge proposals)';
COMMENT ON COLUMN smf_proposals.undo_approved_by_ethr IS 'ethr consent for undo (required for constitutive edge proposals)';
