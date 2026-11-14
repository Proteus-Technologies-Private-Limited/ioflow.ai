#!/usr/bin/env python3
"""
Fix OAuth states that have invalid or missing app_id references
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from db.database import get_db
from db.application_models import OAuthState, Application
from core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_oauth_states():
    """Remove OAuth states that reference non-existent applications"""
    # Create database session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Find all OAuth states
        oauth_states = db.query(OAuthState).all()
        logger.info(f"Found {len(oauth_states)} OAuth states")
        
        removed_count = 0
        for oauth_state in oauth_states:
            # Check if the referenced app exists
            app = db.query(Application).filter(
                Application.app_id == oauth_state.app_id
            ).first()
            
            if not app:
                logger.warning(f"OAuth state {oauth_state.state_id} references non-existent app {oauth_state.app_id}")
                db.delete(oauth_state)
                removed_count += 1
        
        if removed_count > 0:
            db.commit()
            logger.info(f"Removed {removed_count} orphaned OAuth states")
        else:
            logger.info("No orphaned OAuth states found")
        
        # Also check for any OAuth states with NULL app_id
        if settings.database_url.startswith("sqlite"):
            result = db.execute(text("SELECT COUNT(*) FROM oauth_states WHERE app_id IS NULL"))
        else:
            result = db.execute(text("SELECT COUNT(*) FROM oauth_states WHERE app_id IS NULL"))
        
        null_count = result.scalar()
        if null_count > 0:
            logger.warning(f"Found {null_count} OAuth states with NULL app_id")
            # Delete them
            db.execute(text("DELETE FROM oauth_states WHERE app_id IS NULL"))
            db.commit()
            logger.info(f"Deleted {null_count} OAuth states with NULL app_id")
            
    except Exception as e:
        logger.error(f"Error fixing OAuth states: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_oauth_states()