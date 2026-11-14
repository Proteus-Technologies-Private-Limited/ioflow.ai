#!/usr/bin/env python3
import os
os.environ['DATABASE_URL'] = 'sqlite:///ioflow.db'

"""
Database migration script to move http_method to service_config.request_config.method
Also migrates other legacy fields to the new structure.
"""

import sys
sys.path.append('..')

# Set up the database path properly
import os
if not os.path.exists('../ioflow.db'):
    print("Database file not found at ../ioflow.db")
    exit(1)

from db.database import get_db
from db.application_models import ApplicationService
from sqlalchemy import select
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_service(service):
    """Migrate a single service to the new structure"""
    
    # Parse existing service_config
    service_config = {}
    if service.service_config:
        if isinstance(service.service_config, str):
            try:
                service_config = json.loads(service.service_config)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse service_config for service {service.service_id}")
                service_config = {}
        else:
            service_config = service.service_config or {}
    
    # Initialize request_config if not present
    if 'request_config' not in service_config:
        service_config['request_config'] = {}
    
    modified = False
    
    # Migrate http_method to request_config.method
    if service.http_method and 'method' not in service_config['request_config']:
        service_config['request_config']['method'] = service.http_method
        logger.info(f"  - Migrated http_method: {service.http_method}")
        modified = True
    
    # Migrate endpoint_template to service_config level (not request_config)
    if service.endpoint_template and 'endpoint_template' not in service_config:
        service_config['endpoint_template'] = service.endpoint_template
        logger.info(f"  - Migrated endpoint_template: {service.endpoint_template}")
        modified = True
    
    # Migrate headers_template to service_config level
    if service.headers_template and 'headers_template' not in service_config:
        service_config['headers_template'] = service.headers_template
        logger.info(f"  - Migrated headers_template")
        modified = True
    
    # Migrate body_template to request_config
    if service.body_template and 'body_template' not in service_config['request_config']:
        service_config['request_config']['body_template'] = service.body_template
        logger.info(f"  - Migrated body_template")
        modified = True
    
    # Check for query_params_template at top level and move to request_config
    if 'query_params_template' in service_config and 'query_params_template' not in service_config['request_config']:
        service_config['request_config']['query_params_template'] = service_config['query_params_template']
        del service_config['query_params_template']
        logger.info(f"  - Moved query_params_template to request_config")
        modified = True
    
    # Check for parameter_method at top level and move to request_config
    if 'parameter_method' in service_config and 'parameter_method' not in service_config['request_config']:
        service_config['request_config']['parameter_method'] = service_config['parameter_method']
        del service_config['parameter_method']
        logger.info(f"  - Moved parameter_method to request_config")
        modified = True
    
    return service_config if modified else None

def main():
    """Run the migration"""
    logger.info("Starting migration of http_method to request_config.method...")
    
    db = next(get_db())
    
    try:
        # Get all services
        services = db.execute(select(ApplicationService)).scalars().all()
        logger.info(f"Found {len(services)} services to check")
        
        migrated_count = 0
        
        for service in services:
            logger.info(f"\nProcessing service: {service.service_name} (ID: {service.service_id})")
            
            # Migrate the service
            new_service_config = migrate_service(service)
            
            if new_service_config:
                # Update the service
                service.service_config = new_service_config
                migrated_count += 1
                logger.info(f"  ✓ Service migrated successfully")
            else:
                logger.info(f"  - No migration needed")
        
        # Commit changes
        if migrated_count > 0:
            db.commit()
            logger.info(f"\n✅ Migration completed. Migrated {migrated_count} services.")
        else:
            logger.info(f"\n✅ No services needed migration.")
        
        # Verify migration
        logger.info("\nVerifying migration...")
        verification_count = 0
        for service in services:
            if service.service_config:
                service_config = json.loads(service.service_config) if isinstance(service.service_config, str) else service.service_config
                request_config = service_config.get('request_config', {})
                if request_config.get('method'):
                    verification_count += 1
        
        logger.info(f"Found {verification_count} services with method in request_config")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()