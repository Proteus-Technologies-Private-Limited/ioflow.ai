# Remote MCP Setup Guide

This guide explains how to access IOFlow's MCP functionality over the network from Claude Desktop on a remote machine.

## Overview

IOFlow now exposes its MCP (Model Context Protocol) functionality through a network-accessible API, allowing Claude Desktop instances on remote machines to interact with IOFlow's seed application management capabilities.

## Architecture

```
┌─────────────────┐         Network          ┌─────────────────┐
│ Claude Desktop  │ ◄──────────────────────► │  IOFlow Server  │
│   (Client PC)   │         HTTP/HTTPS        │  (Remote Host)  │
│                 │                           │                 │
│ ┌─────────────┐ │                           │ ┌─────────────┐ │
│ │Remote MCP   │ │                           │ │FastAPI      │ │
│ │Client       │ │                           │ │MCP Bridge   │ │
│ └─────────────┘ │                           │ └─────────────┘ │
└─────────────────┘                           └─────────────────┘
```

## Setup Instructions

### 1. Server Side (IOFlow Host)

Ensure your IOFlow server is running and accessible on the network:

```bash
# Start IOFlow backend
cd /path/to/ioflow/backend
python main.py

# By default, it runs on http://0.0.0.0:7001
# Make sure port 8000 is open in your firewall
```

### 2. Client Side (Claude Desktop Machine)

#### Option A: Using pip-installed client

```bash
# Install the remote MCP client
pip install httpx mcp

# Download the remote client
wget https://raw.githubusercontent.com/your-repo/ioflow/main/backend/mcp_server/remote_client.py

# Test the connection
python remote_client.py --server-url http://YOUR_SERVER_IP:7001 --api-key YOUR_API_KEY
```

#### Option B: Using the IOFlow repository

```bash
# Clone the IOFlow repository
git clone https://github.com/your-repo/ioflow.git
cd ioflow/backend

# Install dependencies
pip install httpx mcp

# Test the connection
python mcp_server/remote_client.py --server-url http://YOUR_SERVER_IP:7001 --api-key YOUR_API_KEY
```

### 3. Configure Claude Desktop

Add the following to your Claude Desktop configuration file:

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ioflow-remote": {
      "command": "python",
      "args": ["/path/to/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "http://YOUR_SERVER_IP:7001",
        "IOFLOW_API_KEY": "ioflow_YOUR_API_KEY_HERE"
      }
    }
  }
}
```

Replace:
- `/path/to/remote_client.py` with the actual path to the remote client script
- `YOUR_SERVER_IP` with your IOFlow server's IP address (e.g., `192.168.1.100`)
- `YOUR_API_KEY` with your actual IOFlow API key

### 4. Restart Claude Desktop

After updating the configuration, restart Claude Desktop for the changes to take effect.

## Network Configuration

### Finding Your Server IP

On the IOFlow server machine:

**Linux/macOS**:
```bash
ip addr show | grep inet
# or
ifconfig | grep inet
```

**Windows**:
```cmd
ipconfig
```

Look for the IP address on your local network (usually starts with `192.168.`, `10.`, or `172.`).

### Firewall Configuration

Ensure port 8000 (or your configured port) is open:

**Linux (ufw)**:
```bash
sudo ufw allow 8000/tcp
```

**Linux (firewalld)**:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

**Windows**:
```powershell
New-NetFirewallRule -DisplayName "IOFlow API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

### Using a Custom Port

If you need to use a different port:

1. Update your IOFlow server configuration:
   ```bash
   # In backend/main.py or via environment variable
   export IOFLOW_PORT=7001
   ```

2. Update the client configuration:
   ```json
   "IOFLOW_SERVER_URL": "http://YOUR_SERVER_IP:7001"
   ```

## Security Considerations

### 1. Use HTTPS in Production

For production environments, set up HTTPS using a reverse proxy like nginx:

```nginx
server {
    listen 443 ssl;
    server_name ioflow.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:7001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 2. API Key Security

- Never commit API keys to version control
- Use environment variables or secure credential storage
- Rotate API keys regularly
- Use role-based access control to limit permissions

### 3. Network Security

- Use VPN for remote access when possible
- Implement IP whitelisting for API access
- Monitor API usage and set rate limits

## Available MCP Tools

Once connected, you'll have access to all IOFlow MCP tools:

### Exploration Tools
- `explore_seed_applications` - Browse available integrations
- `get_seed_application` - Get details about specific apps
- `search_applications_by_service` - Find apps by service type

### Management Tools
- `create_seed_application` - Create new integrations
- `edit_application_metadata` - Modify app information
- `add_service_to_application` - Add new services

### Testing Tools
- `validate_application_schema` - Validate JSON structure
- `test_service_endpoint` - Test API endpoints
- `simulate_service_execution` - Test service calls

### Deployment Tools
- `install_application` - Deploy apps to IOFlow
- `list_installed_applications` - View deployed apps
- `verify_deployment` - Check deployment status

## Troubleshooting

### Connection Issues

1. **Check server accessibility**:
   ```bash
   # From client machine
   ping YOUR_SERVER_IP
   curl http://YOUR_SERVER_IP:7001/health
   ```

2. **Verify API key**:
   ```bash
   curl -H "X-API-Key: YOUR_API_KEY" http://YOUR_SERVER_IP:7001/api/mcp/info
   ```

3. **Check Claude Desktop logs**:
   - Windows: `%APPDATA%\Claude\logs\`
   - macOS: `~/Library/Logs/Claude/`
   - Linux: `~/.config/Claude/logs/`

### Common Errors

1. **"Connection refused"**
   - Ensure IOFlow server is running
   - Check firewall settings
   - Verify correct IP and port

2. **"Authentication failed"**
   - Verify API key is correct
   - Check API key permissions
   - Ensure API key is active

3. **"Tool not found"**
   - Update remote client to latest version
   - Check server MCP bridge is loaded
   - Verify tool name spelling

## Advanced Configuration

### Using Environment Variables

Instead of hardcoding values in the config:

```json
{
  "mcpServers": {
    "ioflow-remote": {
      "command": "python",
      "args": ["/path/to/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "${IOFLOW_SERVER_URL}",
        "IOFLOW_API_KEY": "${IOFLOW_API_KEY}"
      }
    }
  }
}
```

Then set environment variables:
```bash
export IOFLOW_SERVER_URL=http://192.168.1.100:7001
export IOFLOW_API_KEY=ioflow_your_key_here
```

### Multiple Environments

Configure multiple IOFlow servers:

```json
{
  "mcpServers": {
    "ioflow-dev": {
      "command": "python",
      "args": ["/path/to/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "http://dev-server:7001",
        "IOFLOW_API_KEY": "ioflow_dev_key"
      }
    },
    "ioflow-prod": {
      "command": "python",
      "args": ["/path/to/remote_client.py"],
      "env": {
        "IOFLOW_SERVER_URL": "https://ioflow.company.com",
        "IOFLOW_API_KEY": "ioflow_prod_key"
      }
    }
  }
}
```

## Performance Optimization

### 1. Connection Pooling

The remote client uses connection pooling by default. For high-traffic scenarios, you can tune the pool size:

```python
# In remote_client.py
self.client = httpx.AsyncClient(
    base_url=self.server_url,
    headers={"X-API-Key": api_key},
    timeout=30.0,
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
)
```

### 2. Caching

For frequently accessed resources, consider implementing client-side caching:

```python
# Add to RemoteMCPClient.__init__
self._cache = {}
self._cache_ttl = 300  # 5 minutes

# In _get_remote_resource
if uri in self._cache:
    cached_time, cached_data = self._cache[uri]
    if time.time() - cached_time < self._cache_ttl:
        return cached_data
```

### 3. Compression

Enable response compression on the server:

```python
# In IOFlow's main.py
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

## Support

For issues or questions:
1. Check the IOFlow documentation at `/docs`
2. Review server logs at `/backend/logs/`
3. Open an issue on the IOFlow GitHub repository
4. Contact your system administrator

## Next Steps

1. Test the connection with a simple tool:
   ```
   # In Claude Desktop
   Use the explore_seed_applications tool
   ```

2. Create your first seed application:
   ```
   # In Claude Desktop
   Use the create_seed_application tool to create a new integration
   ```

3. Explore available integrations:
   ```
   # In Claude Desktop
   Get the seed-apps://catalog resource
   ```