"""
Flow Design Management Tools for MCP Server

Provides tools for creating and managing flow design files for users.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class FlowDesignManagement:
    """Tools for managing user flow design files"""
    
    @staticmethod
    def ensure_user_directory(user_email: str) -> Path:
        """
        Ensure user's flow design directory exists.
        
        Args:
            user_email: User's email address
            
        Returns:
            Path to user's flow design directory
        """
        # Create base directory in project root
        base_dir = Path(os.getcwd()) / "user_flow_design_files"
        
        # Sanitize email for directory name
        safe_email = user_email.replace("@", "_at_").replace(".", "_")
        user_dir = base_dir / safe_email
        
        # Create directories if they don't exist
        user_dir.mkdir(parents=True, exist_ok=True)
        
        return user_dir
    
    @staticmethod
    async def create_flow_design(
        user_email: str,
        flow_name: str,
        flow_json: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new flow design file for a user.
        
        Args:
            user_email: User's email address
            flow_name: Name for the flow design
            flow_json: Flow design JSON data
            
        Returns:
            Result with file path and status
        """
        try:
            # Ensure user directory exists
            user_dir = FlowDesignManagement.ensure_user_directory(user_email)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = flow_name.replace(" ", "_").replace("/", "_")
            filename = f"{safe_name}_{timestamp}.json"
            file_path = user_dir / filename
            
            # Check if file already exists (shouldn't with timestamp, but safety check)
            if file_path.exists():
                return {
                    "success": False,
                    "error": f"File already exists: {filename}"
                }
            
            # Write the flow JSON to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(flow_json, f, indent=2, ensure_ascii=False)
            
            # Log the action
            logger.info(f"Created flow design file: {file_path}")
            
            return {
                "success": True,
                "message": f"Flow design created successfully",
                "file_path": str(file_path),
                "filename": filename,
                "user_directory": str(user_dir),
                "flow_name": flow_name,
                "timestamp": timestamp,
                "size": file_path.stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Error creating flow design: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def replace_flow_design(
        user_email: str,
        flow_name: str,
        flow_json: Dict[str, Any],
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Replace an existing flow design or create a new version.
        
        Args:
            user_email: User's email address
            flow_name: Name for the flow design
            flow_json: Flow design JSON data
            original_filename: Optional original filename to replace
            
        Returns:
            Result with file path and status
        """
        try:
            # Ensure user directory exists
            user_dir = FlowDesignManagement.ensure_user_directory(user_email)
            
            # If original filename provided, backup the old version
            if original_filename:
                original_path = user_dir / original_filename
                if original_path.exists():
                    # Create backup with timestamp
                    backup_name = f"{original_filename}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = user_dir / backup_name
                    original_path.rename(backup_path)
                    logger.info(f"Backed up original file to: {backup_path}")
            
            # Generate new filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = flow_name.replace(" ", "_").replace("/", "_")
            filename = f"{safe_name}_{timestamp}.json"
            file_path = user_dir / filename
            
            # Write the flow JSON to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(flow_json, f, indent=2, ensure_ascii=False)
            
            # Log the action
            logger.info(f"Replaced/created flow design file: {file_path}")
            
            return {
                "success": True,
                "message": f"Flow design {'replaced' if original_filename else 'created'} successfully",
                "file_path": str(file_path),
                "filename": filename,
                "user_directory": str(user_dir),
                "flow_name": flow_name,
                "timestamp": timestamp,
                "size": file_path.stat().st_size,
                "original_backed_up": bool(original_filename)
            }
            
        except Exception as e:
            logger.error(f"Error replacing flow design: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    async def list_user_flows(user_email: str) -> Dict[str, Any]:
        """
        List all flow designs for a user.
        
        Args:
            user_email: User's email address
            
        Returns:
            List of flow design files
        """
        try:
            # Get user directory
            user_dir = FlowDesignManagement.ensure_user_directory(user_email)
            
            # List all JSON files
            flows = []
            for file_path in user_dir.glob("*.json"):
                # Skip backup files
                if ".backup_" in file_path.name:
                    continue
                    
                stat = file_path.stat()
                flows.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
            
            # Sort by modified date (newest first)
            flows.sort(key=lambda x: x["modified"], reverse=True)
            
            return {
                "success": True,
                "user_directory": str(user_dir),
                "flows": flows,
                "count": len(flows)
            }
            
        except Exception as e:
            logger.error(f"Error listing user flows: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Export the tools for MCP registration
FLOW_DESIGN_MANAGEMENT_TOOLS = [FlowDesignManagement]