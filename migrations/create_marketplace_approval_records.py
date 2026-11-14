#!/usr/bin/env python3
"""
Migration script to create MarketplaceApproval records for existing Micro SaaS apps
that have marketplace_enabled=True but no approval records.

This handles apps created before the marketplace approval workflow was fixed.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from db.database import SessionLocal
from db.application_models import FrontendFlowApplicationSQLite as FrontendFlowApplication
from db.marketplace_models import MarketplaceApproval

def create_approval_records():
    """Create MarketplaceApproval records for existing marketplace-enabled apps"""
    db = SessionLocal()

    try:
        print("="*80)
        print("CREATING MARKETPLACE APPROVAL RECORDS FOR EXISTING APPS")
        print("="*80)

        # Find all apps with marketplace_enabled but no approval records
        apps = db.query(FrontendFlowApplication).filter(
            FrontendFlowApplication.marketplace_enabled == True
        ).all()

        print(f"\nFound {len(apps)} apps with marketplace_enabled=True")

        if not apps:
            print("\n✓ No apps need approval records created")
            return

        created_count = 0
        skipped_count = 0

        for app in apps:
            # Check if approval record already exists
            existing_approval = db.query(MarketplaceApproval).filter(
                MarketplaceApproval.app_id == app.frontend_app_id
            ).first()

            if existing_approval:
                print(f"\n  ⏭️  Skipping: {app.frontend_app_name}")
                print(f"     Already has approval record (ID: {existing_approval.approval_id})")
                skipped_count += 1
                continue

            # Determine the approval status based on current marketplace_status
            if app.marketplace_status in ['approved', 'auto_approved']:
                # Already approved - create approved record
                approval_status = 'approved'
                reviewed_at = app.approved_at or datetime.utcnow()
                reviewed_by = app.approved_by
            elif app.marketplace_status == 'rejected':
                # Rejected - create rejected record
                approval_status = 'rejected'
                reviewed_at = datetime.utcnow()
                reviewed_by = None
            elif app.marketplace_status == 'pending':
                # Pending - create pending record
                approval_status = 'pending'
                reviewed_at = None
                reviewed_by = None
            else:
                # Draft or unknown - create pending record
                approval_status = 'pending'
                reviewed_at = None
                reviewed_by = None
                # Update app status to pending if it was something else
                if app.marketplace_status != 'pending':
                    app.marketplace_status = 'pending'

            # Create approval record
            approval = MarketplaceApproval(
                approval_id=str(uuid.uuid4()),
                app_id=app.frontend_app_id,
                status=approval_status,
                submitted_by=app.created_by,
                submitted_at=app.created_at or datetime.utcnow(),
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at,
                review_notes=f"Created by migration script for existing app",
                version=1
            )

            db.add(approval)
            created_count += 1

            print(f"\n  ✓ Created approval record for: {app.frontend_app_name}")
            print(f"     App ID: {app.frontend_app_id}")
            print(f"     Status: {approval_status}")
            print(f"     Submitted By: {app.created_by}")
            print(f"     Submitted At: {approval.submitted_at}")
            if reviewed_at:
                print(f"     Reviewed At: {reviewed_at}")

        # Commit all changes
        db.commit()

        print("\n" + "="*80)
        print("MIGRATION COMPLETE")
        print("="*80)
        print(f"✓ Created: {created_count} approval record(s)")
        print(f"⏭️  Skipped: {skipped_count} app(s) (already have approval records)")
        print(f"📊 Total: {len(apps)} marketplace-enabled app(s)")

        if created_count > 0:
            print("\n✅ Success! Approval records created.")
            print("   Apps should now appear in admin approval queue if status is 'pending'.")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("\n⚠️  WARNING: This migration will create MarketplaceApproval records")
    print("   for all existing apps with marketplace_enabled=True\n")

    response = input("Do you want to continue? (yes/no): ").strip().lower()

    if response == 'yes':
        create_approval_records()
    else:
        print("\n❌ Migration cancelled")
        sys.exit(0)
