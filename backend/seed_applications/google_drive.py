import json
import os

class GoogleDriveSeedApplication:
    def __init__(self):
        self.app_key = 'google_drive'
    
    def get_config(self):
        """Load the Google Drive seed application configuration"""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'seed-applications', 
            'google_drive.json'
        )
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return config