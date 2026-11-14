-- Migration script to create MarketplaceApproval records for existing Micro SaaS apps
-- that have marketplace_enabled=1 but no approval records.

-- This handles apps created before the marketplace approval workflow was fixed.

BEGIN TRANSACTION;

-- Insert approval records for existing marketplace-enabled apps
INSERT INTO marketplace_approvals (
    approval_id,
    app_id,
    status,
    submitted_by,
    submitted_at,
    reviewed_by,
    reviewed_at,
    review_notes,
    version
)
SELECT
    lower(hex(randomblob(16))) as approval_id,  -- Generate UUID
    frontend_app_id as app_id,
    CASE
        -- If already approved or auto-approved, create approved record
        WHEN marketplace_status IN ('approved', 'auto_approved') THEN 'approved'
        -- If rejected, create rejected record
        WHEN marketplace_status = 'rejected' THEN 'rejected'
        -- Otherwise create pending record
        ELSE 'pending'
    END as status,
    created_by as submitted_by,
    COALESCE(created_at, datetime('now')) as submitted_at,
    CASE
        -- Set reviewed_by for approved apps
        WHEN marketplace_status IN ('approved', 'auto_approved') THEN approved_by
        ELSE NULL
    END as reviewed_by,
    CASE
        -- Set reviewed_at for approved/rejected apps
        WHEN marketplace_status IN ('approved', 'auto_approved') THEN COALESCE(approved_at, datetime('now'))
        WHEN marketplace_status = 'rejected' THEN datetime('now')
        ELSE NULL
    END as reviewed_at,
    'Created by migration script for existing marketplace-enabled app' as review_notes,
    1 as version
FROM frontend_flow_applications
WHERE marketplace_enabled = 1
  AND frontend_app_id NOT IN (
      -- Exclude apps that already have approval records
      SELECT app_id FROM marketplace_approvals
  );

-- Update apps with draft/null status to pending if they have marketplace enabled
UPDATE frontend_flow_applications
SET marketplace_status = 'pending'
WHERE marketplace_enabled = 1
  AND (marketplace_status IS NULL OR marketplace_status = 'draft')
  AND frontend_app_id NOT IN (
      SELECT app_id FROM marketplace_approvals WHERE status IN ('approved', 'auto_approved', 'rejected')
  );

COMMIT;

-- Show results
SELECT
    'Created approval records for ' || COUNT(*) || ' app(s)' as message
FROM marketplace_approvals
WHERE review_notes LIKE '%migration script%';

-- Show summary
SELECT
    '----------------------------------------' as separator
UNION ALL
SELECT 'SUMMARY:' as separator
UNION ALL
SELECT '----------------------------------------' as separator
UNION ALL
SELECT
    'Total marketplace-enabled apps: ' || COUNT(*) as info
FROM frontend_flow_applications
WHERE marketplace_enabled = 1
UNION ALL
SELECT
    'Total approval records: ' || COUNT(*) as info
FROM marketplace_approvals
UNION ALL
SELECT
    'Pending approvals: ' || COUNT(*) as info
FROM marketplace_approvals
WHERE status = 'pending'
UNION ALL
SELECT
    'Approved apps: ' || COUNT(*) as info
FROM marketplace_approvals
WHERE status = 'approved';
