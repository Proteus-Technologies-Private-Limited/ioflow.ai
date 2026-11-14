# IOFlow MCP Remote Installation Guide

Connect any Claude Desktop instance to your IOFlow server remotely.

## 📋 Prerequisites

- **Claude Desktop** installed on the target machine
- **Python 3.10+** (Python 3.12 recommended)
- **Network access** to your IOFlow server
- **IOFlow API key** from your IOFlow instance

## 🚀 Quick Installation

### Step 1: Download Installer
Download `ioflow-mcp-remote-installer.sh` to the target machine.

### Step 2: Run Installer
```bash
chmod +x ioflow-mcp-remote-installer.sh
./ioflow-mcp-remote-installer.sh
```

### Step 3: Provide Configuration
When prompted, enter:
- **IOFlow Server URL**: `https://your-ioflow-server.com:7001`
- **IOFlow API Key**: `ioflow_xxxxxxxxxxxxx`

### Step 4: Restart Claude Desktop
The installer will update Claude Desktop's configuration. Restart Claude Desktop to load IOFlow tools.

## 🔧 Manual Installation (Alternative)

If the automatic installer doesn't work, you can install manually:

### 1. Install Python Dependencies
```bash
# Create directory
mkdir ~/.ioflow-mcp
cd ~/.ioflow-mcp

# Create virtual environment (requires Python 3.10+)
python3.12 -m venv venv
source venv/bin/activate

# Install MCP packages
pip install mcp httpx typing-extensions
```

### 2. Download MCP Server
Download `main.py` and `requirements.txt` to `~/.ioflow-mcp/`

### 3. Update Claude Desktop Configuration
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ioflow": {
      "command": "/Users/YOUR_USERNAME/.ioflow-mcp/venv/bin/python",
      "args": ["/Users/YOUR_USERNAME/.ioflow-mcp/main.py"],
      "env": {
        "IOFLOW_BASE_URL": "https://your-ioflow-server.com:7001",
        "IOFLOW_API_KEY": "ioflow_xxxxxxxxxxxxx"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

## 🔍 Troubleshooting

### IOFlow Tools Not Appearing
1. **Restart Claude Desktop** completely (quit and reopen)
2. **Check configuration** file syntax is valid JSON
3. **Verify server connectivity** - can you access the IOFlow URL in browser?
4. **Check API key** - ensure it's valid and has MCP permissions

### Connection Errors
1. **Firewall**: Ensure target machine can reach IOFlow server
2. **HTTPS**: If using HTTPS, ensure SSL certificate is valid
3. **Port**: Verify IOFlow server is running on specified port (default 7001)

### Python Version Issues
```bash
# Check Python version
python3 --version

# If < 3.10, install newer Python:
# macOS: brew install python@3.12
# Ubuntu: sudo apt install python3.12
# Windows: Download from python.org
```

### Log Files
Check logs for errors:
- **macOS**: `~/Library/Logs/Claude/main.log`
- **MCP Server**: Error messages appear in Claude Desktop developer console

## 📦 Distribution

To distribute IOFlow MCP to multiple machines:

1. **Package installer**: Share `ioflow-mcp-remote-installer.sh`
2. **Provide server details**: Share IOFlow server URL and API key
3. **Documentation**: Include this installation guide

## 🔒 Security Notes

- **API Keys**: Keep IOFlow API keys secure and private
- **Network**: Use HTTPS for IOFlow server in production
- **Firewall**: Only open necessary ports (default 7001)
- **Access Control**: Configure IOFlow user permissions appropriately

## ✅ Success Indicators

IOFlow MCP is working when:
- ✅ Claude Desktop shows IOFlow tools in tool palette
- ✅ You can ask Claude to use IOFlow functionality
- ✅ No error messages in Claude Desktop logs
- ✅ Claude can execute IOFlow operations (create flows, manage apps, etc.)

## 🆘 Support

If you encounter issues:
1. Check this troubleshooting guide
2. Verify IOFlow server is accessible from target machine
3. Ensure Python 3.10+ is available
4. Check Claude Desktop logs for specific error messages

---

**🎉 Once installed, you can use IOFlow's 43 tools and 5 resources directly in Claude Desktop!**