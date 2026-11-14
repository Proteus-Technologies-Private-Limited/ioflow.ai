#!/usr/bin/env python3
"""
Scheduled job: emit due monthly subscription charges for Micro SaaS apps.

For every active per-user-per-month subscriber whose billing cycle has ended,
this records a `subscription_payment` transaction in the immutable billing
ledger (snapshotting the monthly price + currency in effect) and advances the
subscriber's billing cycle.

Run this on a daily schedule (cron / systemd timer / scheduler), e.g.:

    cd /opt/ioflow && ./venv/bin/python migrations/run_subscription_billing.py

It is safe to run repeatedly — only subscribers whose cycle has actually ended
are charged, and each run advances their cycle so they are not double-charged.
"""

import os
import sys

# Make backend importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))


def run():
    # Ensure all ledger/subscriber tables are registered before any session use
    import db.application_models  # noqa: F401
    import db.marketplace_models  # noqa: F401
    from db.database import SessionLocal
    from services.micro_saas_service import MicroSaasService

    db = SessionLocal()
    try:
        service = MicroSaasService()
        charged = service.generate_due_subscription_charges(db)
        print(f"Subscription billing run complete. Charges recorded: {charged}")
        return charged
    finally:
        db.close()


if __name__ == "__main__":
    run()
