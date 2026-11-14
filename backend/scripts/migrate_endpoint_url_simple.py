#!/usr/bin/env python3
"""
Simple script to migrate endpoint_url to endpoint_template in existing services
"""
import json
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_service_config(service_config):
    """Migrate endpoint_url to endpoint_template in service config"""
    if not service_config:
        return service_config
        
    try:
        config = json.loads(service_config) if isinstance(service_config, str) else service_config
    except json.JSONDecodeError:
        logger.error(f"Failed to parse service_config: {service_config}")
        return service_config
    
    # Check if endpoint_url exists and endpoint_template doesn't
    if isinstance(config, dict) and 'endpoint_url' in config and 'endpoint_template' not in config:
        config['endpoint_template'] = config.pop('endpoint_url')
        logger.info(f"  - Migrated endpoint_url to endpoint_template")
        return json.dumps(config)
    
    return service_config


def main():
    """Migrate all application services using direct SQLite connection"""
    logger.info("Starting migration of endpoint_url to endpoint_template...")
    
    # Connect to SQLite database
    conn = sqlite3.connect('ioflow.db')
    cursor = conn.cursor()
    
    # Update application services
    logger.info("\nChecking application services...")
    cursor.execute("SELECT service_id, service_name, service_config FROM application_services WHERE service_config IS NOT NULL")
    services = cursor.fetchall()
    
    updated_count = 0
    for service_id, service_name, service_config in services:
        new_config = migrate_service_config(service_config)
        if new_config != service_config:
            cursor.execute("UPDATE application_services SET service_config = ? WHERE service_id = ?", 
                         (new_config, service_id))
            updated_count += 1
            logger.info(f"Updated service '{service_name}'")
    
    if updated_count > 0:
        conn.commit()
        logger.info(f"\nSuccessfully migrated {updated_count} services")
    else:
        logger.info("\nNo services needed migration")
    
    # Update flows
    logger.info("\nChecking flows for inline service configurations...")
    cursor.execute("SELECT flow_id, flow_name, flow_definition FROM flows WHERE flow_definition IS NOT NULL")
    flows = cursor.fetchall()
    
    flow_update_count = 0
    for flow_id, flow_name, flow_definition in flows:
        try:
            flow_json = json.loads(flow_definition)
            updated = False
            
            # Check nodes for service configurations
            if 'nodes' in flow_json:
                for node in flow_json['nodes']:
                    if 'data' in node and 'service_config' in node['data']:
                        service_config = node['data']['service_config']
                        if isinstance(service_config, dict) and 'endpoint_url' in service_config:
                            service_config['endpoint_template'] = service_config.pop('endpoint_url')
                            updated = True
                            logger.info(f"  - Updated node in flow '{flow_name}'")
            
            if updated:
                cursor.execute("UPDATE flows SET flow_definition = ? WHERE flow_id = ?", 
                             (json.dumps(flow_json), flow_id))
                flow_update_count += 1
        
        except json.JSONDecodeError:
            logger.error(f"Failed to parse flow_definition for flow {flow_id}")
    
    if flow_update_count > 0:
        conn.commit()
        logger.info(f"Updated {flow_update_count} flows")
    else:
        logger.info("No flows needed updates")
    
    conn.close()
    logger.info("\nMigration completed!")


if __name__ == "__main__":
    main()