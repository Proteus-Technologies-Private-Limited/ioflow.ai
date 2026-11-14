"""
SSH Command Executor for executing remote commands on servers via SSH
"""
import asyncio
import logging
from typing import Dict, Any
from services.service_executors import ServiceExecutor
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSHCommandExecutor(ServiceExecutor):
    """Executor for running commands on remote servers via SSH using paramiko"""

    async def execute(self, parameters: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an SSH command on a remote server"""
        try:
            import paramiko
        except ImportError:
            return {
                'error': True,
                'message': 'paramiko library is required for SSH command execution. Install with: pip install paramiko'
            }

        try:
            # Get connection details from service config and auth credentials
            base_url = self.service_config.get('base_url', '')
            parsed = urlparse(base_url)

            host = parsed.hostname or parameters.get('host', '')
            port = parsed.port or int(parameters.get('port', 22))
            username = self.auth_credentials.get('username') if self.auth_credentials else None
            password = self.auth_credentials.get('password') if self.auth_credentials else None
            private_key = self.auth_credentials.get('private_key') if self.auth_credentials else None

            if not host:
                return {'error': True, 'message': 'SSH host is required. Configure it in the application base URL (ssh://host:port) or pass as parameter.'}
            if not username:
                return {'error': True, 'message': 'SSH username is required for authentication.'}

            # Build the command - handle specialized services
            command = self._build_command(parameters)
            if not command:
                return {'error': True, 'message': 'Command parameter is required.'}

            # Get timeout from parameters or service config
            timeout = int(parameters.get('timeout', self.service_config.get('timeout_seconds', 30)))

            logger.info(f"SSH command execution on {host}:{port} as {username}")

            # Run the blocking SSH operations in a thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self._execute_ssh_command,
                host, port, username, password, private_key, command, timeout
            )

            return result

        except Exception as e:
            logger.error(f"SSH command execution failed: {str(e)}")
            return {
                'error': True,
                'message': f'SSH command execution failed: {str(e)}'
            }

    def _build_command(self, parameters: Dict[str, Any]) -> str:
        """Build the final command from parameters, handling specialized services"""
        service_name = self.service_config.get('service_name', '')
        command = parameters.get('command', '').strip()

        # Handle check_disk_space: append path if provided
        if service_name == 'check_disk_space':
            path = parameters.get('path', '').strip()
            if not command:
                command = 'df -h'
            if path:
                command = f'{command} {path}'

        # Handle list_processes: build from sort_by and limit
        elif service_name == 'list_processes':
            sort_by = parameters.get('sort_by', 'memory')
            limit = int(parameters.get('limit', 20))
            sort_flag = '-%mem' if sort_by == 'memory' else '-%cpu'
            command = f'ps aux --sort={sort_flag} | head -{limit}'

        return command

    def _execute_ssh_command(self, host: str, port: int, username: str,
                             password: str, private_key: str,
                             command: str, timeout: int) -> Dict[str, Any]:
        """Execute SSH command synchronously (called from thread pool)"""
        import paramiko
        import io

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Connect with private key or password
            if private_key:
                key = paramiko.RSAKey.from_private_key(io.StringIO(private_key))
                ssh.connect(host, port, username, pkey=key, timeout=timeout)
            else:
                ssh.connect(host, port, username, password, timeout=timeout)

            # Execute command
            stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)

            # Read output
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode('utf-8', errors='replace')
            stderr_text = stderr.read().decode('utf-8', errors='replace')

            return {
                'success': exit_code == 0,
                'exit_code': exit_code,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'host': host,
                'command': command
            }

        except paramiko.AuthenticationException:
            return {
                'error': True,
                'message': f'Authentication failed for {username}@{host}:{port}. Check credentials or SSH key.'
            }
        except paramiko.SSHException as e:
            return {
                'error': True,
                'message': f'SSH connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f'Connection failed to {host}:{port}: {str(e)}'
            }
        finally:
            ssh.close()
