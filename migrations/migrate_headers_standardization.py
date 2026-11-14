#!/usr/bin/env python3
"""
Migration script to standardize header storage.
Moves headers from service_config.request_config.headers_template to top-level headers_template field.
"""
import sqlite3
import json
import sys

def migrate_headers(db_path):
    """Migrate headers from nested location to top-level field"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get all services
        cursor.execute("SELECT service_id, service_name, headers_template, service_config FROM application_services")
        services = cursor.fetchall()
        
        updated_count = 0
        
        for service_id, service_name, headers_template, service_config in services:
            try:
                # Parse service_config
                if service_config:
                    config = json.loads(service_config)
                    
                    # Check if headers exist in nested location
                    nested_headers = config.get('request_config', {}).get('headers_template')
                    
                    if nested_headers:
                        # Parse current headers_template
                        current_headers = {}
                        if headers_template:
                            try:
                                current_headers = json.loads(headers_template) if isinstance(headers_template, str) else headers_template
                            except:
                                current_headers = {}
                        
                        # If top-level is empty or {}, use nested headers
                        if not current_headers or current_headers == {}:
                            print(f"Migrating headers for service: {service_name}")
                            
                            # Update top-level headers_template
                            cursor.execute(
                                "UPDATE application_services SET headers_template = ? WHERE service_id = ?",
                                (json.dumps(nested_headers), service_id)
                            )
                            
                            # Remove from nested location
                            if 'request_config' in config and 'headers_template' in config['request_config']:
                                del config['request_config']['headers_template']
                                cursor.execute(
                                    "UPDATE application_services SET service_config = ? WHERE service_id = ?",
                                    (json.dumps(config), service_id)
                                )
                            
                            updated_count += 1
                            print(f"  - Migrated headers: {json.dumps(nested_headers, indent=2)}")
                        else:
                            print(f"Service {service_name} already has top-level headers, removing nested ones")
                            # Just remove from nested location
                            if 'request_config' in config and 'headers_template' in config['request_config']:
                                del config['request_config']['headers_template']
                                cursor.execute(
                                    "UPDATE application_services SET service_config = ? WHERE service_id = ?",
                                    (json.dumps(config), service_id)
                                )
                                updated_count += 1
                
            except Exception as e:
                print(f"Error processing service {service_name}: {e}")
                continue
        
        conn.commit()
        print(f"\nMigration complete. Updated {updated_count} services.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    db_path = "../ioflow.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print(f"Migrating headers in database: {db_path}")
    if migrate_headers(db_path):
        print("Migration successful!")
    else:
        print("Migration failed!")
        sys.exit(1)