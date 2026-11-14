#!/usr/bin/env python3
"""
Activate the test user account
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def activate_test_user():
    """Activate the test@ioflow.com user"""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Update the user to be activated (status = 'A' for active)
        result = conn.execute(
            text("UPDATE users SET status = 'A' WHERE email = :email"),
            {"email": "test@ioflow.com"}
        )
        conn.commit()
        
        if result.rowcount > 0:
            logger.info(f"✅ Activated test user: test@ioflow.com")
        else:
            logger.warning("⚠️ Test user not found: test@ioflow.com")
        
        # Verify activation
        result = conn.execute(
            text("SELECT status FROM users WHERE email = :email"),
            {"email": "test@ioflow.com"}
        )
        row = result.fetchone()
        if row and row[0] == 'A':
            logger.info("✅ User is now activated")
        else:
            logger.error("❌ Failed to activate user")

if __name__ == "__main__":
    activate_test_user()