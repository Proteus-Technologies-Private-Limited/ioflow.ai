"""
API Key Handler for MCP Server

Manages API key generation, validation, and storage for MCP access.
"""

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

class APIKeyHandler:
    """Manages API keys for MCP server access"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".ioflow" / "mcp_keys.json")
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        self.keys = self._load_keys()
    
    def _load_keys(self) -> Dict[str, Dict[str, Any]]:
        """Load API keys from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def _save_keys(self):
        """Save API keys to storage"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.keys, f, indent=2)
    
    def generate_api_key(
        self, 
        name: str, 
        permissions: List[str],
        expires_in_days: Optional[int] = None
    ) -> str:
        """
        Generate a new API key for MCP access.
        
        Args:
            name: Name/description for the API key
            permissions: List of permissions granted to this key
            expires_in_days: Number of days until key expires (None = no expiry)
            
        Returns:
            Generated API key
        """
        # Generate a secure random key
        raw_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Calculate expiry
        expiry = None
        if expires_in_days:
            expiry = (datetime.utcnow() + timedelta(days=expires_in_days)).isoformat()
        
        # Store key info (hash only, not the actual key)
        self.keys[key_hash] = {
            "name": name,
            "permissions": permissions,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expiry,
            "last_used": None,
            "usage_count": 0
        }
        
        self._save_keys()
        
        # Return the actual key (only shown once)
        return f"mcp_{raw_key}"
    
    def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return its info.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            Key info if valid, None otherwise
        """
        if not api_key.startswith("mcp_"):
            return None
        
        # Extract and hash the key
        raw_key = api_key[4:]  # Remove 'mcp_' prefix
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Check if key exists
        if key_hash not in self.keys:
            return None
        
        key_info = self.keys[key_hash]
        
        # Check expiry
        if key_info.get("expires_at"):
            expiry = datetime.fromisoformat(key_info["expires_at"])
            if datetime.utcnow() > expiry:
                return None
        
        # Update usage stats
        key_info["last_used"] = datetime.utcnow().isoformat()
        key_info["usage_count"] += 1
        self._save_keys()
        
        return key_info
    
    def revoke_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: The API key to revoke
            
        Returns:
            True if revoked, False if key not found
        """
        if not api_key.startswith("mcp_"):
            return False
        
        raw_key = api_key[4:]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        if key_hash in self.keys:
            del self.keys[key_hash]
            self._save_keys()
            return True
        
        return False
    
    def list_keys(self) -> List[Dict[str, Any]]:
        """
        List all API keys (without revealing the actual keys).
        
        Returns:
            List of key information
        """
        keys_list = []
        for key_hash, info in self.keys.items():
            keys_list.append({
                "name": info["name"],
                "permissions": info["permissions"],
                "created_at": info["created_at"],
                "expires_at": info.get("expires_at"),
                "last_used": info.get("last_used"),
                "usage_count": info.get("usage_count", 0),
                "key_prefix": key_hash[:8]  # Show first 8 chars of hash for identification
            })
        
        return sorted(keys_list, key=lambda x: x["created_at"], reverse=True)