#!/usr/bin/env python3
"""
Script to update all seed application JSON files from endpoint_url to endpoint_template
for consistency with other *_template fields
"""
import json
import os
from pathlib import Path

def update_json_file(file_path):
    """Update a single JSON file to use endpoint_template instead of endpoint_url"""
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    updated = False
    
    # Update services if they exist
    if 'services' in data:
        for service in data['services']:
            if 'endpoint_url' in service:
                service['endpoint_template'] = service.pop('endpoint_url')
                updated = True
                print(f"  - Updated service '{service.get('service_name', 'unnamed')}' to use endpoint_template")
    
    # Save if updated
    if updated:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Updated {file_path.name}")
    else:
        print(f"  No changes needed for {file_path.name}")
    
    return updated

def main():
    """Update all seed application JSON files"""
    
    # Get the seed-applications directory
    backend_dir = Path(__file__).parent.parent
    seed_apps_dir = backend_dir / 'seed-applications'
    
    if not seed_apps_dir.exists():
        print(f"Error: seed-applications directory not found at {seed_apps_dir}")
        return
    
    print("Updating seed application files to use endpoint_template...\n")
    
    updated_count = 0
    total_count = 0
    
    # Process all JSON files in the directory
    for json_file in seed_apps_dir.glob('*.json'):
        total_count += 1
        if update_json_file(json_file):
            updated_count += 1
        print()  # Add blank line between files
    
    print(f"\nSummary: Updated {updated_count} out of {total_count} files")

if __name__ == "__main__":
    main()