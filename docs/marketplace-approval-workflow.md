# Marketplace Approval Workflow

## Overview

When a Micro SaaS app is published with `marketplace_enabled=True`, it goes through an approval workflow before appearing in the public marketplace.

## Workflow Steps

### 1. App Creation/Publishing

When creating or updating a Micro SaaS app with marketplace enabled:

```python
{
  "marketplace_enabled": True,
  "visibility": "public"  # or "private" or "granted_access"
}
```

**What happens:**
- App is created in `frontend_flow_applications` table
- `marketplace_status` is set to `'pending'`
- A `MarketplaceApproval` record is created with `status='pending'`
- App is **NOT** visible in marketplace yet

### 2. Admin Approval Queue

Admins can view pending approvals at:
- **API Endpoint**: `GET /api/v1/marketplace/admin/pending-approvals`
- **UI**: Admin Marketplace Approval page

**Requirements:**
- User must have `role = UserRole.INSTANCE_ADMIN`

**Response includes:**
- App details (name, description, creator)
- Submission date
- Current status

### 3. Admin Review & Approval

Admin can approve or reject the app:

**Approve:**
```
POST /api/v1/marketplace/admin/apps/{app_id}/approve
{
  "notes": "Looks good!",
  "featured": false
}
```

**Reject:**
```
POST /api/v1/marketplace/admin/apps/{app_id}/reject
{
  "reason": "Needs better description"
}
```

**What happens on approval:**
- `marketplace_status` changed to `'approved'`
- `approved_at` timestamp set
- `approved_by` set to admin user ID
- App becomes visible in marketplace

**What happens on rejection:**
- `marketplace_status` changed to `'rejected'`
- App owner can update and resubmit

### 4. Marketplace Visibility

For an app to appear in the public marketplace, it must meet **ALL** criteria:

```sql
WHERE is_active = TRUE
  AND visibility = 'public'
  AND marketplace_status IN ('approved', 'auto_approved')
```

## Status Values

### `marketplace_status` field values:

| Status | Description | Visible in Marketplace? |
|--------|-------------|-------------------------|
| `draft` | Not submitted for marketplace | ❌ No |
| `pending` | Submitted, awaiting admin review | ❌ No |
| `approved` | Approved by admin | ✅ Yes (if public) |
| `rejected` | Rejected by admin | ❌ No |
| `auto_approved` | Auto-approved (legacy, not used anymore) | ✅ Yes (if public) |

## Re-submission After Rejection

If an app is rejected, the owner can:
1. Make updates to the app
2. Re-enable marketplace: `marketplace_enabled = True`
3. This creates a new `MarketplaceApproval` record with incremented version number
4. Status returns to `'pending'` for admin review

## Database Tables

### `frontend_flow_applications`
- Stores the Micro SaaS app details
- `marketplace_enabled`: Boolean
- `marketplace_status`: String (draft/pending/approved/rejected/auto_approved)
- `visibility`: String (public/private/granted_access)
- `approved_at`: Timestamp
- `approved_by`: User ID of approving admin

### `marketplace_approvals`
- Tracks approval history and workflow
- `approval_id`: Primary key
- `app_id`: Foreign key to frontend_flow_applications
- `status`: String (pending/approved/rejected)
- `submitted_by`: User ID of submitter
- `submitted_at`: Submission timestamp
- `reviewed_by`: User ID of admin reviewer
- `reviewed_at`: Review timestamp
- `review_notes`: Admin notes
- `rejection_reason`: Reason for rejection
- `version`: Version number (for re-submissions)
- `previous_approval_id`: Link to previous approval (if resubmission)

## Code Flow

### Creating a Micro SaaS App

```
MicroSaasService.create_micro_saas_app()
  ↓
Create FrontendFlowApplication
  ↓
If marketplace_enabled = True:
  ↓
  Set marketplace_status = 'pending'
  ↓
  Create MarketplaceApproval record (status='pending')
  ↓
  App appears in admin approval queue
```

### Admin Approval

```
Admin reviews app
  ↓
POST /api/v1/marketplace/admin/apps/{app_id}/approve
  ↓
Update FrontendFlowApplication:
  - marketplace_status = 'approved'
  - approved_at = now()
  - approved_by = admin_id
  ↓
Update MarketplaceApproval:
  - status = 'approved'
  - reviewed_by = admin_id
  - reviewed_at = now()
  ↓
App appears in public marketplace
```

## Important Notes

1. **Marketplace Enabled ≠ Marketplace Visible**
   - Just enabling marketplace doesn't make app visible
   - It creates a pending approval request
   - Admin must approve it first

2. **Visibility Setting**
   - `public` - Anyone can see (after approval)
   - `private` - Only creator can see
   - `granted_access` - Specific users/tenants can see

3. **Auto-Approval Removed**
   - Previous versions had auto-approval logic
   - This has been removed to ensure quality control
   - All apps now require admin review

4. **Version Tracking**
   - Each submission/resubmission creates new approval record
   - Version number increments
   - Previous approval linked via `previous_approval_id`

## Troubleshooting

### App not appearing in marketplace

Check:
1. ✅ `is_active = TRUE`
2. ✅ `visibility = 'public'`
3. ✅ `marketplace_enabled = TRUE`
4. ✅ `marketplace_status = 'approved'` or `'auto_approved'`

### App not appearing in admin approval queue

Check:
1. ✅ `marketplace_enabled = TRUE`
2. ✅ `MarketplaceApproval` record exists with `status='pending'`
3. ✅ Admin user has `role = UserRole.INSTANCE_ADMIN`

### App shows in "My Apps" but not marketplace

This is expected behavior:
- "My Apps" shows all apps you created
- Marketplace shows only approved public apps
- Submit for approval if you want it in marketplace
