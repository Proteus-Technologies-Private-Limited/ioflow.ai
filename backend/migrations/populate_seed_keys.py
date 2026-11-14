#!/usr/bin/env python3
"""
Migration script to populate seed_key field for existing applications
that were installed from seed applications.
"""

import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import get_db
from db.application_models import Application
from services.json_seed_manager import json_seed_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def populate_seed_keys():
    """Populate seed_key field for existing applications."""
    
    # Get database session
    db = next(get_db())
    
    try:
        # Discover all seed applications
        seed_applications = json_seed_manager.discover_applications()
        logger.info(f"Found {len(seed_applications)} seed applications")
        
        # Build mapping of app_name to seed_key
        name_to_seed_key = {}
        for seed_key, seed_data in seed_applications.items():
            app_name = seed_data['application']['app_name']
            name_to_seed_key[app_name] = seed_key
            logger.info(f"  - {app_name} -> {seed_key}")
        
        # Get all applications without seed_key
        applications = db.query(Application).filter(
            Application.seed_key == None
        ).all()
        
        logger.info(f"\nFound {len(applications)} applications without seed_key")
        
        updated_count = 0
        for app in applications:
            if app.app_name in name_to_seed_key:
                seed_key = name_to_seed_key[app.app_name]
                app.seed_key = seed_key
                logger.info(f"Updated {app.app_name} with seed_key: {seed_key}")
                updated_count += 1
            else:
                logger.warning(f"No seed found for application: {app.app_name}")
        
        # Commit changes
        db.commit()
        logger.info(f"\n✅ Migration complete! Updated {updated_count} applications")
        
        # Verify the update
        apps_with_keys = db.query(Application).filter(
            Application.seed_key != None
        ).count()
        logger.info(f"Total applications with seed_keys: {apps_with_keys}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting seed_key population migration...")
    populate_seed_keys()