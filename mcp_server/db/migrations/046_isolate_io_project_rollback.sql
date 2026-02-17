-- Rollback Migration 046: Revert I/O to 'super' access level
UPDATE project_registry
SET access_level = 'super'
WHERE project_id = 'io';

DO $$
DECLARE
    v_level TEXT;
BEGIN
    SELECT access_level::TEXT INTO v_level
    FROM project_registry WHERE project_id = 'io';

    RAISE NOTICE 'Rollback 046 complete: io access_level reverted to %', v_level;
END $$;
