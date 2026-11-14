#!/bin/bash

# IOFlow Traditional MCP Server Installer
# Uses the proven traditional MCP approach instead of buggy DXT

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m' 
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
CLAUDE_CONFIG="/Users/$USER/Library/Application Support/Claude/claude_desktop_config.json"
MCP_SERVER_DIR="/Users/$USER/.ioflow-mcp"
PYTHON_SCRIPT="$MCP_SERVER_DIR/main.py"

# Default values
DEFAULT_URL="http://localhost:7001"
DEFAULT_API_KEY="your_ioflow_api_key_here"

log() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║        IOFlow Traditional MCP Installer          ║"
    echo "║             (Proven Working Method)              ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

get_config() {
    log "Getting configuration..."
    
    read -p "Enter IOFlow server URL [$DEFAULT_URL]: " IOFLOW_URL
    IOFLOW_URL=${IOFLOW_URL:-$DEFAULT_URL}
    
    read -p "Enter IOFlow API key [$DEFAULT_API_KEY]: " IOFLOW_API_KEY  
    IOFLOW_API_KEY=${IOFLOW_API_KEY:-$DEFAULT_API_KEY}
    
    success "Configuration collected"
}

setup_mcp_server() {
    log "Setting up MCP server directory..."
    
    # Create directory
    mkdir -p "$MCP_SERVER_DIR"
    
    # Copy the working MCP server
    cp "server/main.py" "$MCP_SERVER_DIR/"
    cp "server/requirements.txt" "$MCP_SERVER_DIR/"
    
    # Create virtual environment with Python 3.12 (required for MCP)
    cd "$MCP_SERVER_DIR"
    
    # Try different Python versions that support MCP (requires 3.10+)
    PYTHON_CMD=""
    for py in python3.12 python3.11 python3.10; do
        if command -v "$py" >/dev/null 2>&1; then
            PYTHON_CMD="$py"
            version=$("$py" --version | cut -d' ' -f2)
            break
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        error "Python 3.10+ is required for MCP. Please install Python 3.10 or newer."
        exit 1
    fi
    
    log "Using Python: $PYTHON_CMD ($version)"
    "$PYTHON_CMD" -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    
    success "MCP server setup complete"
}

update_claude_config() {
    log "Updating Claude Desktop configuration..."
    
    # Backup existing config
    if [ -f "$CLAUDE_CONFIG" ]; then
        cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Create/update configuration
    cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "ioflow": {
      "command": "$MCP_SERVER_DIR/venv/bin/python",
      "args": ["$MCP_SERVER_DIR/main.py"],
      "env": {
        "IOFLOW_BASE_URL": "$IOFLOW_URL",
        "IOFLOW_API_KEY": "$IOFLOW_API_KEY"
      }
    }
  },
  "dxtExtensions": []
}
EOF
    
    success "Claude Desktop configuration updated"
}

test_installation() {
    log "Testing MCP server..."
    
    cd "$MCP_SERVER_DIR"
    
    # Test the server can start
    IOFLOW_BASE_URL="$IOFLOW_URL" \
    IOFLOW_API_KEY="$IOFLOW_API_KEY" \
    timeout 10s ./venv/bin/python main.py &
    
    SERVER_PID=$!
    sleep 5
    
    if kill -0 $SERVER_PID 2>/dev/null; then
        kill $SERVER_PID 2>/dev/null || true
        success "MCP server test successful"
        return 0
    else
        error "MCP server test failed"
        return 1
    fi
}

print_summary() {
    echo
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║            INSTALLATION COMPLETE!               ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    success "IOFlow Traditional MCP Server installed!"
    echo
    echo -e "${BLUE}📋 Installation Summary:${NC}"
    echo "  • MCP server installed at: $MCP_SERVER_DIR"
    echo "  • Claude config updated: $CLAUDE_CONFIG"
    echo "  • Using traditional MCP approach (not DXT)"
    echo "  • Server tested and working"
    echo
    echo -e "${BLUE}🚀 Next Steps:${NC}"
    echo "  1. Restart Claude Desktop"
    echo "  2. IOFlow tools will appear in tool palette"
    echo "  3. Start using IOFlow functionality!"
    echo
    echo -e "${YELLOW}📝 Notes:${NC}"
    echo "  • This uses traditional MCP (not DXT) because DXT has bugs"
    echo "  • Configuration backup saved as: $CLAUDE_CONFIG.backup.*"
    echo "  • To uninstall: rm -rf $MCP_SERVER_DIR"
    echo
}

main() {
    print_header
    
    # Check prerequisites
    if [ ! -d "/Applications/Claude.app" ]; then
        error "Claude Desktop not found. Please install Claude Desktop first."
        exit 1
    fi
    
    if [ ! -f "server/main.py" ]; then
        error "IOFlow MCP server files not found. Run from IOFlow DXT directory."
        exit 1
    fi
    
    get_config
    setup_mcp_server
    update_claude_config
    
    if test_installation; then
        print_summary
        success "🎉 Traditional MCP installation complete!"
    else
        error "Installation test failed. Check your IOFlow server connection."
        exit 1
    fi
}

main "$@"