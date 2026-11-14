#!/usr/bin/env python3
"""
Script to update seed data files to use 'method' instead of 'http_method'
and move it inside request_config for consistency.
"""

import json
import os
import glob
from typing import Dict, Any

def update_service_method(service: Dict[str, Any]) -> Dict[str, Any]:
    """Update a single service to use 'method' in request_config."""
    # Only process api_call services
    if service.get('service_type') != 'api_call':
        return service
    
    # Get the HTTP method
    method = service.get('http_method', 'GET')
    
    # Ensure request_config exists
    if 'request_config' not in service:
        service['request_config'] = {}
    
    # Move method to request_config
    service['request_config']['method'] = method
    
    # Remove http_method from top level
    if 'http_method' in service:
        del service['http_method']
    
    return service

def update_seed_file(filepath: str) -> None:
    """Update a single seed file."""
    print(f"Processing: {filepath}")
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Check if file has services
    if 'services' not in data:
        print(f"  No services found, skipping")
        return
    
    # Update each service
    updated = False
    for i, service in enumerate(data['services']):
        if 'http_method' in service:
            data['services'][i] = update_service_method(service)
            updated = True
            print(f"  Updated service: {service.get('service_name', 'unnamed')}")
    
    if updated:
        # Write back with proper formatting
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  File updated successfully")
    else:
        print(f"  No updates needed")

def main():
    """Main function to update all seed files."""
    seed_dir = os.path.join(os.path.dirname(__file__), '..', 'seed-applications')
    pattern = os.path.join(seed_dir, '*.json')
    
    files = glob.glob(pattern)
    print(f"Found {len(files)} seed files to process\n")
    
    for filepath in sorted(files):
        update_seed_file(filepath)
        print()

if __name__ == '__main__':
    main()