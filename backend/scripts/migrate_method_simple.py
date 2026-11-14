#!/usr/bin/env python3
"""
Simple migration script to move http_method to service_config.request_config.method
Uses direct SQL queries to avoid ORM issues.
"""

import sqlite3
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_service(service_config_str, http_method, body_template_str, headers_template_str):
    """Migrate a single service to the new structure"""
    
    # Parse existing service_config
    service_config = {}
    if service_config_str:
        try:
            service_config = json.loads(service_config_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse service_config")
            service_config = {}
    
    # Initialize request_config if not present
    if 'request_config' not in service_config:
        service_config['request_config'] = {}
    
    modified = False
    
    # Migrate http_method to request_config.method
    if http_method and 'method' not in service_config['request_config']:
        service_config['request_config']['method'] = http_method
        logger.info(f"  - Migrated http_method: {http_method}")
        modified = True
    
    # Migrate body_template to request_config
    if body_template_str and 'body_template' not in service_config['request_config']:
        try:
            body_template = json.loads(body_template_str)
            service_config['request_config']['body_template'] = body_template
            logger.info(f"  - Migrated body_template")
            modified = True
        except json.JSONDecodeError:
            pass
    
    # Migrate headers_template to service_config level
    if headers_template_str and 'headers_template' not in service_config:
        try:
            headers_template = json.loads(headers_template_str)
            service_config['headers_template'] = headers_template
            logger.info(f"  - Migrated headers_template")
            modified = True
        except json.JSONDecodeError:
            pass
    
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
    
    return json.dumps(service_config) if modified else None

def main():
    """Run the migration"""
    logger.info("Starting migration of http_method to request_config.method...")
    
    # Connect to SQLite database
    conn = sqlite3.connect('../ioflow.db')
    cursor = conn.cursor()
    
    try:
        # Get all services
        cursor.execute("""
            SELECT service_id, service_name, service_config, http_method, body_template, headers_template 
            FROM application_services
        """)
        services = cursor.fetchall()
        logger.info(f"Found {len(services)} services to check")
        
        migrated_count = 0
        
        for service in services:
            service_id, service_name, service_config, http_method, body_template, headers_template = service
            logger.info(f"\nProcessing service: {service_name} (ID: {service_id})")
            
            # Migrate the service
            new_service_config = migrate_service(service_config, http_method, body_template, headers_template)
            
            if new_service_config:
                # Update the service
                cursor.execute("""
                    UPDATE application_services 
                    SET service_config = ? 
                    WHERE service_id = ?
                """, (new_service_config, service_id))
                migrated_count += 1
                logger.info(f"  ✓ Service migrated successfully")
            else:
                logger.info(f"  - No migration needed")
        
        # Commit changes
        if migrated_count > 0:
            conn.commit()
            logger.info(f"\n✅ Migration completed. Migrated {migrated_count} services.")
        else:
            logger.info(f"\n✅ No services needed migration.")
        
        # Verify migration
        logger.info("\nVerifying migration...")
        cursor.execute("""
            SELECT COUNT(*) FROM application_services 
            WHERE service_config LIKE '%"request_config"%' 
            AND service_config LIKE '%"method"%'
        """)
        verification_count = cursor.fetchone()[0]
        
        logger.info(f"Found {verification_count} services with method in request_config")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()