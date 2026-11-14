#!/usr/bin/env python3
"""
Script to migrate endpoint_url to endpoint_template in existing application services
"""
import json
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from sqlalchemy import text
from db.database import engine, get_db
from core.config import settings
import logging

# Import models based on database type
if settings.database_url.startswith("sqlite"):
    from db.models import Flow
from db.application_models import ApplicationService, Application
else:
    from db.application_models import ApplicationService, Application
    from db.models import Flow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_service_config(service_config):
    """Migrate endpoint_url to endpoint_template in service config"""
    if isinstance(service_config, str):
        try:
            config = json.loads(service_config)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse service_config: {service_config}")
            return service_config
    else:
        config = service_config
    
    # Check if endpoint_url exists and endpoint_template doesn't
    if 'endpoint_url' in config and 'endpoint_template' not in config:
        config['endpoint_template'] = config.pop('endpoint_url')
        logger.info(f"  - Migrated endpoint_url to endpoint_template")
        return json.dumps(config) if isinstance(service_config, str) else config
    
    return service_config


def main():
    """Migrate all application services"""
    logger.info("Starting migration of endpoint_url to endpoint_template...")
    
    updated_count = 0
    total_count = 0
    
    with next(get_db()) as db:
        # Get all application services
        services = db.query(ApplicationService).all()
        total_count = len(services)
        
        logger.info(f"Found {total_count} application services to check")
        
        for service in services:
            if service.service_config:
                original_config = service.service_config
                new_config = migrate_service_config(original_config)
                
                if original_config != new_config:
                    service.service_config = new_config
                    updated_count += 1
                    
                    # Get application name for logging
                    app = db.query(Application).filter(
                        Application.app_id == service.app_id
                    ).first()
                    app_name = app.app_name if app else "Unknown"
                    
                    logger.info(f"Updated service '{service.service_name}' in app '{app_name}'")
        
        if updated_count > 0:
            db.commit()
            logger.info(f"\nSuccessfully migrated {updated_count} services")
        else:
            logger.info("\nNo services needed migration")
    
    # Also check for any flows that might have inline service configurations
    logger.info("\nChecking flows for inline service configurations...")
    
    with next(get_db()) as db:
        flows = db.query(Flow).all()
        flow_update_count = 0
        
        for flow in flows:
            if flow.flow_data:
                try:
                    flow_json = json.loads(flow.flow_data) if isinstance(flow.flow_data, str) else flow.flow_data
                    updated = False
                    
                    # Check nodes for service configurations
                    if 'nodes' in flow_json:
                        for node in flow_json['nodes']:
                            if 'data' in node and 'service_config' in node['data']:
                                service_config = node['data']['service_config']
                                if isinstance(service_config, dict) and 'endpoint_url' in service_config:
                                    service_config['endpoint_template'] = service_config.pop('endpoint_url')
                                    updated = True
                                    logger.info(f"  - Updated node '{node.get('id')}' in flow '{flow.flow_name}'")
                    
                    if updated:
                        flow.flow_data = json.dumps(flow_json)
                        flow_update_count += 1
                
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse flow_data for flow {flow.flow_id}")
        
        if flow_update_count > 0:
            db.commit()
            logger.info(f"Updated {flow_update_count} flows")
        else:
            logger.info("No flows needed updates")
    
    logger.info("\nMigration completed!")


if __name__ == "__main__":
    main()