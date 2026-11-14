"""
File Protocol Executor for handling FTP, SFTP, SMB, NFS, and Local file operations
"""
import os
import stat
import base64
import json
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import logging
from datetime import datetime

from services.service_executors import ServiceExecutor

logger = logging.getLogger(__name__)


class FileProtocolExecutor(ServiceExecutor):
    """Universal file protocol executor - handles FTP, SFTP, SMB, NFS, Local file operations"""
    
    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file operation based on configured protocol"""
        try:
            # Get base_url from service config
            base_url = self.service_config.get('base_url', 'file:///')
            
            # Parse protocol from base_url
            parsed = urlparse(base_url)
            protocol = parsed.scheme or 'file'
            
            # Get operation from parameters or from schema default
            operation = parameters.get('operation')
            
            # If operation is not provided, check schema for default
            if not operation:
                schema = self.service_config.get('parameter_schema', {})
                properties = schema.get('properties', {})
                operation_schema = properties.get('operation', {})
                operation = operation_schema.get('default')
                
                if not operation:
                    # If still no operation, this is an error
                    service_name = self.service_config.get('service_name', 'unknown')
                    return {
                        'error': True,
                        'message': f"Operation parameter is missing for service '{service_name}'. Please configure the operation type (read, write, list, etc.)"
                    }
                
                logger.info(f"Using default operation from schema: {operation}")
            
            # Validate required parameters based on operation
            if operation in ['write', 'write_base64']:
                if not parameters.get('path'):
                    return {
                        'error': True,
                        'message': "Missing required parameter 'path'. Please specify where to save the file."
                    }
                content = parameters.get('content')
                # Check if content exists and is not None
                # Allow dict (file object), string (base64), or any truthy value
                if content is None or (isinstance(content, str) and content == ''):
                    return {
                        'error': True,
                        'message': "Missing required parameter 'content'. Please provide the file content or reference {{input.file}} for uploaded files."
                    }
                # Additional validation: if content is a dict, ensure it has the required fields
                if isinstance(content, dict) and not ('content' in content or 'data' in content):
                    logger.warning(f"File object missing content/data field. Keys: {list(content.keys())}")
                    return {
                        'error': True,
                        'message': f"File object is missing 'content' or 'data' field. Available keys: {list(content.keys())}"
                    }
            elif operation in ['read', 'read_base64']:
                if not parameters.get('path'):
                    return {
                        'error': True,
                        'message': "Missing required parameter 'path'. Please specify which file to read."
                    }
            elif operation == 'list':
                # path is optional for list, defaults to root
                pass
            
            logger.info(f"Executing file operation: {operation} on protocol: {protocol}")
            
            # Route to appropriate handler based on protocol
            if protocol == 'ftp':
                return await self._handle_ftp(parsed, parameters, operation)
            elif protocol == 'sftp' or protocol == 'ssh':
                return await self._handle_sftp(parsed, parameters, operation)
            elif protocol == 'smb' or protocol == 'cifs':
                return await self._handle_smb(parsed, parameters, operation)
            elif protocol == 'nfs':
                return await self._handle_nfs(parsed, parameters, operation)
            else:  # file:// or local
                return await self._handle_local(parameters, operation)
                
        except Exception as e:
            logger.error(f"File operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"File operation failed: {str(e)}"
            }
    
    async def _handle_local(self, parameters: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle local file system operations"""
        try:
            path = parameters.get('path', '')
            
            if not path:
                return {'error': True, 'message': 'File path is required'}
            
            # Expand user home directory if needed
            if path.startswith('~'):
                path = os.path.expanduser(path)
            
            if operation == 'read' or operation == 'read_base64':
                # Read file and return in base64
                if not os.path.exists(path):
                    return {'error': True, 'message': f'File not found: {path}'}
                
                with open(path, 'rb') as f:
                    content = f.read()
                
                # Get file info
                stat = os.stat(path)
                
                return {
                    'success': True,
                    'content': base64.b64encode(content).decode('utf-8'),
                    'encoding': 'base64',
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'path': path
                }
                
            elif operation == 'write' or operation == 'write_base64':
                # Write file from base64 content
                content = parameters.get('content', '')
                mode = parameters.get('mode', 'overwrite')
                
                # Debug logging to understand what's being passed
                logger.info(f"Write operation - content type: {type(content)}, content preview: {str(content)[:100] if content else 'empty'}")
                
                # Store the original filename if available from file object
                filename = None
                
                # Handle file object (from file input) - extract content if it's a dict
                if isinstance(content, dict):
                    logger.info(f"File object detected. Keys: {list(content.keys())}")
                    # Extract filename if available - check both 'filename' and 'name' fields
                    # 'name' is from frontend file uploads, 'filename' is from backend processing
                    filename = content.get('name') or content.get('filename')
                    
                    if 'content' in content:
                        # File object from trigger - extract the base64 content
                        logger.info(f"Extracting content from file object: filename={filename}, size={content.get('size')}")
                        content = content['content']
                    elif 'data' in content:
                        # Alternative structure - some file inputs use 'data' instead of 'content'
                        logger.info(f"Extracting data from file object (alternative structure): filename={filename}")
                        content = content['data']
                    else:
                        # File object but no content/data field
                        logger.error(f"File object missing 'content' or 'data' field. Keys: {list(content.keys())}, full object: {content}")
                        return {'error': True, 'message': f'File object is missing content field. Available keys: {list(content.keys())}'}
                
                if not content:
                    return {'error': True, 'message': 'File content is required'}
                
                # Ensure content is a string before decoding
                if not isinstance(content, str):
                    logger.error(f"Content is not a string: type={type(content)}")
                    return {'error': True, 'message': f'File content must be a base64 string, got {type(content).__name__}'}
                
                # Decode base64 content
                try:
                    decoded_content = base64.b64decode(content)
                except Exception as e:
                    return {'error': True, 'message': f'Invalid base64 content: {str(e)}'}
                
                # Check if path is a directory and append filename if needed
                if os.path.exists(path) and os.path.isdir(path):
                    # Path is a directory, append filename
                    if filename:
                        logger.info(f"Path is a directory, appending filename: {filename}")
                        path = os.path.join(path, filename)
                    else:
                        # Generate a default filename if none provided
                        import time
                        default_filename = f"file_{int(time.time())}.dat"
                        logger.info(f"Path is a directory, using default filename: {default_filename}")
                        path = os.path.join(path, default_filename)
                elif not os.path.exists(path):
                    # Path doesn't exist - check if it looks like a directory (ends with /)
                    if path.endswith('/') or path.endswith('\\'):
                        # Treat as directory path
                        if filename:
                            logger.info(f"Path ends with separator, treating as directory and appending filename: {filename}")
                            os.makedirs(path, exist_ok=True)
                            path = os.path.join(path, filename)
                        else:
                            import time
                            default_filename = f"file_{int(time.time())}.dat"
                            logger.info(f"Path ends with separator, using default filename: {default_filename}")
                            os.makedirs(path, exist_ok=True)
                            path = os.path.join(path, default_filename)
                    # Otherwise check if it has no extension (likely a directory)
                    else:
                        # Check if the path has no extension
                        parent_dir = os.path.dirname(path)
                        base_name = os.path.basename(path)
                        
                        # If we have a filename from file object and path has no extension, treat path as directory
                        if filename and '.' not in base_name:
                            logger.info(f"Path '{path}' has no extension, treating as directory and appending filename: {filename}")
                            os.makedirs(path, exist_ok=True)
                            path = os.path.join(path, filename)
                        # If basename has no extension and no filename provided, might need a default extension
                        elif not filename and '.' not in base_name:
                            logger.warning(f"Path '{path}' has no extension and no filename provided, treating as file path")
                
                # Create directory if it doesn't exist
                directory = os.path.dirname(path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                
                # Write file
                write_mode = 'ab' if mode == 'append' else 'wb'
                with open(path, write_mode) as f:
                    f.write(decoded_content)
                
                return {
                    'success': True,
                    'message': f'File written successfully: {path}',
                    'size': len(decoded_content),
                    'path': path
                }
                
            elif operation == 'list':
                # List files in directory
                if not os.path.exists(path):
                    return {'error': True, 'message': f'Directory not found: {path}'}
                
                if not os.path.isdir(path):
                    return {'error': True, 'message': f'Path is not a directory: {path}'}
                
                pattern = parameters.get('pattern', '*')
                include_hidden = parameters.get('include_hidden', False)
                
                files = []
                for entry in os.listdir(path):
                    # Skip hidden files if requested
                    if not include_hidden and entry.startswith('.'):
                        continue
                    
                    # Apply pattern filter (simple wildcard matching)
                    if pattern != '*':
                        import fnmatch
                        if not fnmatch.fnmatch(entry, pattern):
                            continue
                    
                    full_path = os.path.join(path, entry)
                    stat = os.stat(full_path)
                    
                    files.append({
                        'name': entry,
                        'path': full_path,
                        'is_directory': os.path.isdir(full_path),
                        'size': stat.st_size if not os.path.isdir(full_path) else 0,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                
                return {
                    'success': True,
                    'files': files,
                    'count': len(files),
                    'path': path
                }
                
            elif operation == 'delete':
                # Delete file
                if not os.path.exists(path):
                    return {'error': True, 'message': f'File not found: {path}'}
                
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                    message = f'Directory deleted: {path}'
                else:
                    os.remove(path)
                    message = f'File deleted: {path}'
                
                return {
                    'success': True,
                    'message': message,
                    'path': path
                }
                
            elif operation == 'move' or operation == 'rename':
                # Move or rename file
                destination = parameters.get('destination', '')
                if not destination:
                    return {'error': True, 'message': 'Destination path is required'}
                
                if not os.path.exists(path):
                    return {'error': True, 'message': f'Source file not found: {path}'}
                
                # Create destination directory if needed
                dest_dir = os.path.dirname(destination)
                if dest_dir and not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                
                os.rename(path, destination)
                
                return {
                    'success': True,
                    'message': f'File moved from {path} to {destination}',
                    'source': path,
                    'destination': destination
                }
                
            elif operation == 'mkdir' or operation == 'create_directory':
                # Create directory
                recursive = parameters.get('recursive', True)
                
                if not path:
                    return {'error': True, 'message': 'Directory path is required'}
                
                if os.path.exists(path):
                    return {
                        'success': True,
                        'message': f'Directory already exists: {path}',
                        'path': path
                    }
                
                if recursive:
                    os.makedirs(path, exist_ok=True)
                else:
                    os.mkdir(path)
                
                return {
                    'success': True,
                    'message': f'Directory created: {path}',
                    'path': path
                }
                
            elif operation == 'info' or operation == 'stat':
                # Get file/directory information
                if not os.path.exists(path):
                    return {
                        'success': False,
                        'exists': False,
                        'message': f'Path does not exist: {path}',
                        'path': path
                    }
                
                stat = os.stat(path)
                is_dir = os.path.isdir(path)
                is_file = os.path.isfile(path)
                
                # Get MIME type for files
                mime_type = None
                if is_file:
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(path)
                
                # Get permissions in octal format
                import stat as stat_module
                permissions = oct(stat.st_mode)[-3:]
                
                return {
                    'success': True,
                    'exists': True,
                    'is_directory': is_dir,
                    'is_file': is_file,
                    'size': stat.st_size if is_file else 0,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'accessed': datetime.fromtimestamp(stat.st_atime).isoformat(),
                    'permissions': permissions,
                    'mime_type': mime_type,
                    'path': path
                }
                
            elif operation == 'copy':
                # Copy file
                destination = parameters.get('destination', '')
                if not destination:
                    return {'error': True, 'message': 'Destination path is required'}
                
                if not os.path.exists(path):
                    return {'error': True, 'message': f'Source file not found: {path}'}
                
                # Create destination directory if needed
                dest_dir = os.path.dirname(destination)
                if dest_dir and not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                
                if os.path.isdir(path):
                    import shutil
                    shutil.copytree(path, destination)
                else:
                    import shutil
                    shutil.copy2(path, destination)
                
                return {
                    'success': True,
                    'message': f'File copied from {path} to {destination}',
                    'source': path,
                    'destination': destination
                }
                
            else:
                return {'error': True, 'message': f'Unknown operation: {operation}'}
                
        except Exception as e:
            logger.error(f"Local file operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"Local file operation failed: {str(e)}"
            }
    
    async def _handle_ftp(self, parsed, parameters: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle FTP file operations"""
        try:
            import ftplib
            
            # Get connection parameters
            host = parsed.hostname or 'localhost'
            port = parsed.port or 21
            username = self.auth_credentials.get('username', 'anonymous') if self.auth_credentials else 'anonymous'
            password = self.auth_credentials.get('password', 'anonymous@') if self.auth_credentials else 'anonymous@'
            
            # Connect to FTP server
            ftp = ftplib.FTP()
            ftp.connect(host, port)
            ftp.login(username, password)
            
            try:
                path = parameters.get('path', '')
                
                if operation == 'read' or operation == 'read_base64':
                    # Read file from FTP
                    import io
                    buffer = io.BytesIO()
                    ftp.retrbinary(f'RETR {path}', buffer.write)
                    content = buffer.getvalue()
                    
                    return {
                        'success': True,
                        'content': base64.b64encode(content).decode('utf-8'),
                        'encoding': 'base64',
                        'size': len(content),
                        'path': path
                    }
                    
                elif operation == 'write' or operation == 'write_base64':
                    # Write file to FTP
                    content = parameters.get('content', '')
                    
                    # Store the original filename if available from file object
                    filename = None
                    
                    # Handle file object (from file input) - extract content if it's a dict
                    if isinstance(content, dict):
                        # Extract filename - check both 'filename' and 'name' fields
                        filename = content.get('filename') or content.get('name')
                        if 'content' in content:
                            content = content['content']
                        elif 'data' in content:
                            content = content['data']
                        else:
                            return {'error': True, 'message': 'File object is missing content field'}
                    
                    if not content:
                        return {'error': True, 'message': 'File content is required'}
                    
                    # Ensure content is a string before decoding
                    if not isinstance(content, str):
                        return {'error': True, 'message': f'File content must be a base64 string, got {type(content).__name__}'}
                    
                    # Decode base64 content
                    decoded_content = base64.b64decode(content)
                    
                    import io
                    buffer = io.BytesIO(decoded_content)
                    ftp.storbinary(f'STOR {path}', buffer)
                    
                    return {
                        'success': True,
                        'message': f'File uploaded to FTP: {path}',
                        'size': len(decoded_content),
                        'path': path
                    }
                    
                elif operation == 'list':
                    # List files in FTP directory
                    files = []
                    ftp.cwd(path if path else '/')
                    
                    # Parse FTP LIST output
                    for line in ftp.nlst():
                        files.append({
                            'name': line,
                            'path': f"{path}/{line}" if path else line
                        })
                    
                    return {
                        'success': True,
                        'files': files,
                        'count': len(files),
                        'path': path or '/'
                    }
                    
                elif operation == 'delete':
                    # Delete file from FTP
                    ftp.delete(path)
                    
                    return {
                        'success': True,
                        'message': f'File deleted from FTP: {path}',
                        'path': path
                    }
                    
                else:
                    return {'error': True, 'message': f'Operation {operation} not supported for FTP'}
                    
            finally:
                ftp.quit()
                
        except Exception as e:
            logger.error(f"FTP operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"FTP operation failed: {str(e)}"
            }
    
    async def _handle_sftp(self, parsed, parameters: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle SFTP file operations"""
        try:
            import paramiko
            
            # Get connection parameters
            host = parsed.hostname or 'localhost'
            port = parsed.port or 22
            username = self.auth_credentials.get('username') if self.auth_credentials else None
            password = self.auth_credentials.get('password') if self.auth_credentials else None
            private_key = self.auth_credentials.get('private_key') if self.auth_credentials else None
            
            if not username:
                return {'error': True, 'message': 'SFTP username is required'}
            
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with password or key
            if private_key:
                import io
                key = paramiko.RSAKey.from_private_key(io.StringIO(private_key))
                ssh.connect(host, port, username, pkey=key)
            else:
                ssh.connect(host, port, username, password)
            
            sftp = ssh.open_sftp()
            
            try:
                path = parameters.get('path', '')
                
                # Handle empty path or just '.'
                if not path or path == '.':
                    path = '.'
                # Don't modify absolute paths
                elif not path.startswith('/'):
                    # For relative paths, ensure they don't start with ~/
                    # SFTP handles relative paths from the user's home directory
                    if path.startswith('~/'):
                        path = path[2:]  # Remove ~/ as SFTP is already in home
                
                logger.info(f"SFTP operation '{operation}' with path: '{path}'")
                
                if operation == 'read' or operation == 'read_base64':
                    # Read file from SFTP
                    with sftp.open(path, 'rb') as f:
                        content = f.read()
                    
                    file_stat = sftp.stat(path)
                    
                    return {
                        'success': True,
                        'content': base64.b64encode(content).decode('utf-8'),
                        'encoding': 'base64',
                        'size': file_stat.st_size,
                        'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        'path': path
                    }
                    
                elif operation == 'write' or operation == 'write_base64':
                    # Write file to SFTP
                    content = parameters.get('content', '')
                    
                    # Store the original filename if available from file object
                    filename = None
                    
                    # Handle file object (from file input) - extract content if it's a dict
                    if isinstance(content, dict):
                        # Extract filename - check both 'filename' and 'name' fields
                        filename = content.get('filename') or content.get('name')
                        if 'content' in content:
                            content = content['content']
                        elif 'data' in content:
                            content = content['data']
                        else:
                            return {'error': True, 'message': 'File object is missing content field'}
                    
                    if not content:
                        return {'error': True, 'message': 'File content is required'}
                    
                    # Ensure content is a string before decoding
                    if not isinstance(content, str):
                        return {'error': True, 'message': f'File content must be a base64 string, got {type(content).__name__}'}
                    
                    # Decode base64 content
                    decoded_content = base64.b64decode(content)
                    
                    # Log initial state for debugging
                    logger.info(f"SFTP write operation - Initial path: '{path}', Has filename: {bool(filename)}, Filename: '{filename}'")
                    
                    # Check if path is a directory on SFTP server
                    try:
                        # Try to stat the path
                        path_stat = sftp.stat(path)
                        # Check if it's a directory using S_ISDIR
                        if stat.S_ISDIR(path_stat.st_mode):
                            # Path is a directory, append filename
                            if filename:
                                logger.info(f"SFTP path is a directory, appending filename: {filename}")
                                path = f"{path}/{filename}" if path else filename
                            else:
                                # Generate a default filename if none provided
                                import time
                                default_filename = f"file_{int(time.time())}.dat"
                                logger.info(f"SFTP path is a directory, using default filename: {default_filename}")
                                path = f"{path}/{default_filename}" if path else default_filename
                    except FileNotFoundError as e:
                        logger.info(f"SFTP path '{path}' not found, will check if it's a directory path")
                        # Path doesn't exist - check if it looks like a directory
                        if path.endswith('/'):
                            # Treat as directory path - try to create it
                            try:
                                sftp.mkdir(path.rstrip('/'))
                                logger.info(f"Created SFTP directory: {path.rstrip('/')}")
                            except Exception as mkdir_err:
                                logger.debug(f"Could not create directory: {mkdir_err}")
                            
                            if filename:
                                logger.info(f"SFTP path ends with /, treating as directory and appending filename: {filename}")
                                path = f"{path}{filename}"
                            else:
                                import time
                                default_filename = f"file_{int(time.time())}.dat"
                                logger.info(f"SFTP path ends with /, using default filename: {default_filename}")
                                path = f"{path}{default_filename}"
                        else:
                            # Check if the path has no extension (likely a directory)
                            if '.' not in os.path.basename(path) and filename:
                                # Looks like a directory path without trailing slash
                                try:
                                    sftp.mkdir(path)
                                    logger.info(f"Created SFTP directory: {path}")
                                except Exception as mkdir_err:
                                    logger.debug(f"Could not create directory: {mkdir_err}")
                                logger.info(f"SFTP path looks like directory, appending filename: {filename}")
                                path = f"{path}/{filename}"
                            else:
                                # Path is likely a full file path, but might need parent dirs
                                logger.info(f"SFTP path appears to be a full file path: {path}")
                    except Exception as e:
                        logger.warning(f"Error checking SFTP path: {e}")
                        # If we have a filename and path doesn't have an extension, treat as directory
                        if filename and '.' not in os.path.basename(path):
                            logger.info(f"Error checking path, but treating as directory since no extension and have filename")
                            path = f"{path}/{filename}" if path else filename
                    
                    mode = parameters.get('mode', 'overwrite')
                    file_mode = 'ab' if mode == 'append' else 'wb'
                    
                    # Create parent directories if they don't exist
                    parent_dir = os.path.dirname(path)
                    if parent_dir:
                        try:
                            # Try to create parent directories
                            dirs = parent_dir.split('/')
                            current_path = ''
                            for dir_part in dirs:
                                if dir_part:
                                    current_path = f"{current_path}/{dir_part}" if current_path else dir_part
                                    try:
                                        sftp.mkdir(current_path)
                                        logger.debug(f"Created parent directory: {current_path}")
                                    except Exception as mkdir_err:
                                        # Directory might already exist
                                        logger.debug(f"Parent directory {current_path} exists or cannot create: {mkdir_err}")
                        except Exception as e:
                            logger.warning(f"Error creating parent directories: {e}")
                    
                    # Log the final path being written
                    logger.info(f"SFTP writing to final path: '{path}', mode: {file_mode}")
                    
                    try:
                        with sftp.open(path, file_mode) as f:
                            f.write(decoded_content)
                    except FileNotFoundError as e:
                        # Parent directory might not exist, try to create it
                        parent_dir = os.path.dirname(path)
                        if parent_dir and parent_dir != '/':
                            logger.info(f"File not found error, attempting to create parent directory: {parent_dir}")
                            try:
                                # Create all parent directories recursively
                                parts = parent_dir.strip('/').split('/')
                                for i in range(len(parts)):
                                    partial_path = '/' + '/'.join(parts[:i+1])
                                    try:
                                        sftp.mkdir(partial_path)
                                        logger.info(f"Created directory: {partial_path}")
                                    except:
                                        pass  # Directory exists
                                
                                # Try writing again
                                with sftp.open(path, file_mode) as f:
                                    f.write(decoded_content)
                                logger.info(f"Successfully wrote file after creating parent directories")
                            except Exception as retry_err:
                                logger.error(f"Failed to write file even after creating directories: {retry_err}")
                                raise Exception(f"Cannot write to SFTP path '{path}': {retry_err}")
                        else:
                            raise Exception(f"Cannot write to SFTP path '{path}': {e}")
                    
                    return {
                        'success': True,
                        'message': f'File uploaded via SFTP: {path}',
                        'size': len(decoded_content),
                        'path': path
                    }
                    
                elif operation == 'list':
                    # List files in SFTP directory
                    files = []
                    list_path = path if path else '.'
                    
                    try:
                        for entry in sftp.listdir_attr(list_path):
                            files.append({
                                'name': entry.filename,
                                'path': f"{path}/{entry.filename}" if path else entry.filename,
                                'is_directory': stat.S_ISDIR(entry.st_mode),
                                'size': entry.st_size,
                                'modified': datetime.fromtimestamp(entry.st_mtime).isoformat()
                            })
                    except FileNotFoundError:
                        logger.warning(f"SFTP directory not found: {list_path}")
                        # Return empty list for non-existent directory
                        return {
                            'success': True,
                            'files': [],
                            'count': 0,
                            'path': path or '/',
                            'message': f'Directory not found: {list_path}'
                        }
                    
                    return {
                        'success': True,
                        'files': files,
                        'count': len(files),
                        'path': path or '/'
                    }
                    
                elif operation == 'delete':
                    # Delete file from SFTP
                    sftp.remove(path)
                    
                    return {
                        'success': True,
                        'message': f'File deleted via SFTP: {path}',
                        'path': path
                    }
                    
                else:
                    return {'error': True, 'message': f'Operation {operation} not supported for SFTP'}
                    
            finally:
                sftp.close()
                ssh.close()
                
        except ImportError:
            return {
                'error': True,
                'message': 'SFTP support requires paramiko library. Please install: pip install paramiko'
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"SFTP operation failed: {str(e)}\nTraceback:\n{error_details}")
            
            # Provide more user-friendly error messages
            error_msg = str(e)
            if "[Errno 2] No such file" in error_msg:
                # Try to extract the path from the logs/context
                path_info = parameters.get('path', 'unknown') if 'parameters' in locals() else 'unknown'
                error_msg = f"Cannot access path '{path_info}' on SFTP server. The directory may not exist or you may not have permission. Error: {error_msg}"
            elif "[Errno 13] Access denied" in error_msg or "Permission denied" in error_msg:
                error_msg = f"Permission denied on SFTP server. Check your credentials and file permissions. Error: {error_msg}"
            elif "Authentication failed" in error_msg:
                error_msg = f"SFTP authentication failed. Check your username and password. Error: {error_msg}"
            else:
                error_msg = f"SFTP operation failed: {error_msg}"
            
            return {
                'error': True,
                'message': error_msg
            }
    
    async def _handle_smb(self, parsed, parameters: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle SMB/CIFS file operations"""
        try:
            from smb.SMBConnection import SMBConnection
            
            # Get connection parameters
            host = parsed.hostname or 'localhost'
            port = parsed.port or 445
            username = self.auth_credentials.get('username', 'guest') if self.auth_credentials else 'guest'
            password = self.auth_credentials.get('password', '') if self.auth_credentials else ''
            domain = self.auth_credentials.get('domain', '') if self.auth_credentials else ''
            
            # Parse share and path from URL path
            url_path = parsed.path.lstrip('/')
            if '/' in url_path:
                share_name, file_path = url_path.split('/', 1)
            else:
                share_name = url_path
                file_path = ''
            
            # Create SMB connection
            conn = SMBConnection(username, password, 'ioflow', host, domain=domain, use_ntlm_v2=True)
            conn.connect(host, port)
            
            try:
                path = parameters.get('path', file_path)
                
                if operation == 'read' or operation == 'read_base64':
                    # Read file from SMB
                    import tempfile
                    with tempfile.NamedTemporaryFile() as tmp:
                        conn.retrieveFile(share_name, path, tmp)
                        tmp.seek(0)
                        content = tmp.read()
                    
                    return {
                        'success': True,
                        'content': base64.b64encode(content).decode('utf-8'),
                        'encoding': 'base64',
                        'size': len(content),
                        'path': path
                    }
                    
                elif operation == 'write' or operation == 'write_base64':
                    # Write file to SMB
                    content = parameters.get('content', '')
                    
                    # Store the original filename if available from file object
                    filename = None
                    
                    # Handle file object (from file input) - extract content if it's a dict
                    if isinstance(content, dict):
                        # Extract filename - check both 'filename' and 'name' fields
                        filename = content.get('filename') or content.get('name')
                        if 'content' in content:
                            content = content['content']
                        elif 'data' in content:
                            content = content['data']
                        else:
                            return {'error': True, 'message': 'File object is missing content field'}
                    
                    if not content:
                        return {'error': True, 'message': 'File content is required'}
                    
                    # Ensure content is a string before decoding
                    if not isinstance(content, str):
                        return {'error': True, 'message': f'File content must be a base64 string, got {type(content).__name__}'}
                    
                    # Decode base64 content
                    decoded_content = base64.b64decode(content)
                    
                    import io
                    file_obj = io.BytesIO(decoded_content)
                    conn.storeFile(share_name, path, file_obj)
                    
                    return {
                        'success': True,
                        'message': f'File uploaded via SMB: {path}',
                        'size': len(decoded_content),
                        'path': path
                    }
                    
                elif operation == 'list':
                    # List files in SMB directory
                    files = []
                    for entry in conn.listPath(share_name, path if path else '/'):
                        if entry.filename not in ['.', '..']:
                            files.append({
                                'name': entry.filename,
                                'path': f"{path}/{entry.filename}" if path else entry.filename,
                                'is_directory': entry.isDirectory,
                                'size': entry.file_size if not entry.isDirectory else 0
                            })
                    
                    return {
                        'success': True,
                        'files': files,
                        'count': len(files),
                        'path': path or '/'
                    }
                    
                elif operation == 'delete':
                    # Delete file from SMB
                    conn.deleteFiles(share_name, path)
                    
                    return {
                        'success': True,
                        'message': f'File deleted via SMB: {path}',
                        'path': path
                    }
                    
                else:
                    return {'error': True, 'message': f'Operation {operation} not supported for SMB'}
                    
            finally:
                conn.close()
                
        except ImportError:
            return {
                'error': True,
                'message': 'SMB support requires pysmb library. Please install: pip install pysmb'
            }
        except Exception as e:
            logger.error(f"SMB operation failed: {str(e)}")
            return {
                'error': True,
                'message': f"SMB operation failed: {str(e)}"
            }
    
    async def _handle_nfs(self, parsed, parameters: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Handle NFS file operations"""
        # NFS typically requires OS-level mounting, so we'll use local file operations
        # after the NFS share is mounted to a local path
        return {
            'error': True,
            'message': 'NFS operations require the share to be mounted at OS level. Use local file operations with the mounted path.'
        }