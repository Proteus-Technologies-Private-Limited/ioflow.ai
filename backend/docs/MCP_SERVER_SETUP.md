# MCP Server Setup

The MCP (Model Context Protocol) server has been implemented but requires separate installation due to dependency conflicts.

## Installation Options

### Option 1: Use IOFlow without MCP Server (Recommended)

Simply install the regular requirements:
```bash
pip install -r requirements.txt
```

The IOFlow backend will work perfectly without the MCP server. The MCP server code includes fallback implementations for development.

### Option 2: Install MCP Server in a Separate Environment

If you need the MCP server functionality:

1. Create a separate virtual environment:
```bash
python -m venv mcp-env
source mcp-env/bin/activate  # On Windows: mcp-env\Scripts\activate
```

2. Install MCP requirements:
```bash
pip install -r requirements-mcp.txt
pip install fastapi>=0.115.0 httpx sqlalchemy  # Compatible versions
```

3. Run the MCP server separately:
```bash
cd mcp_server
python -m server
```

### Option 3: Update All Dependencies (Advanced)

If you want everything in one environment, you'll need to update FastAPI and related dependencies:

```bash
pip install fastapi>=0.115.0 uvicorn[standard] anyio>=4.6
pip install mcp==1.0.0
# Then install other requirements
```

Note: This may require testing to ensure all functionality still works with newer versions.

## API Key Authentication

The MCP server uses IOFlow API keys for authentication:

1. Create an API key in IOFlow UI (Settings → API Keys)
2. Set the environment variable:
   ```bash
   export IOFLOW_API_KEY="ioflow_your_api_key_here"
   export IOFLOW_BASE_URL="http://localhost:8000"  # Or your IOFlow URL
   ```
3. The MCP server will authenticate using this API key

## Running Without MCP

The codebase is designed to work without the MCP package installed. The mock implementation in `mcp_server/server.py` allows the code to run for development and testing purposes.