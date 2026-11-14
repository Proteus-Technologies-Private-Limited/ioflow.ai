#!/bin/bash

# IOFlow Simple Installer - Handles DXT installation correctly
# Usage: ./ioflow-simple-installer.sh [base_url] [api_key]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DXT_FILE="$SCRIPT_DIR/ioflow-mcp-v1.0-final.dxt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect OS and set paths
case "$(uname -s)" in
    Darwin*) 
        OS="macos"
        CLAUDE_DIR="$HOME/Library/Application Support/Claude"
        ;;
    Linux*) 
        OS="linux"
        CLAUDE_DIR="$HOME/.config/Claude"
        ;;
    *)
        log_error "Unsupported operating system"
        exit 1
        ;;
esac

EXTENSIONS_DIR="$CLAUDE_DIR/Claude Extensions"
CONFIG_FILE="$CLAUDE_DIR/claude_desktop_config.json"

echo "🚀 IOFlow Simple Installer for Claude Desktop"
echo "=============================================="
echo

# Check prerequisites
if [ ! -d "$CLAUDE_DIR" ]; then
    log_error "Claude Desktop not found. Please install Claude Desktop first."
    exit 1
fi
log_success "Claude Desktop found"

if [ ! -f "$DXT_FILE" ]; then
    log_error "DXT package not found: $DXT_FILE"
    exit 1
fi
log_success "DXT package found"

# Get configuration
if [ $# -ge 2 ]; then
    BASE_URL="$1"
    API_KEY="$2"
else
    echo "Please provide your IOFlow configuration:"
    read -p "IOFlow Server URL: " BASE_URL
    read -p "IOFlow API Key: " -s API_KEY
    echo
fi

if [ -z "$BASE_URL" ] || [ -z "$API_KEY" ]; then
    log_error "Both URL and API key are required"
    exit 1
fi

# Test IOFlow connection
log_info "Testing IOFlow connection..."
if command -v curl >/dev/null 2>&1; then
    if curl -s --max-time 10 "$BASE_URL/api/mcp/info" -H "Authorization: Bearer $API_KEY" >/dev/null; then
        log_success "IOFlow server is accessible"
    else
        log_warning "Could not connect to IOFlow server. Continuing anyway..."
    fi
fi

# Clean up existing installations
log_info "Cleaning up existing installations..."
rm -f "$EXTENSIONS_DIR"/*ioflow*.dxt 2>/dev/null || true
rm -rf "$EXTENSIONS_DIR"/*ioflow* 2>/dev/null || true

# Create extensions directory if needed
mkdir -p "$EXTENSIONS_DIR"

# Install DXT package
log_info "Installing DXT package..."
cp "$DXT_FILE" "$EXTENSIONS_DIR/"

# Important: Start Claude Desktop to trigger extraction
log_info "Starting Claude Desktop to process the extension..."
log_warning "Claude Desktop will start automatically. Please wait for it to fully load before continuing."

case "$OS" in
    macos)
        open -a "Claude" || open "/Applications/Claude.app" || log_warning "Could not auto-start Claude Desktop"
        ;;
    linux)
        (nohup claude >/dev/null 2>&1 &) || log_warning "Could not auto-start Claude Desktop"
        ;;
esac

# Wait for user confirmation that Claude Desktop has started
echo
echo "⏳ Please wait for Claude Desktop to fully start and load."
echo "   You should see the Claude Desktop window open."
echo
read -p "Press Enter once Claude Desktop has fully loaded..."

# Wait for extraction with better logic
log_info "Waiting for extension extraction..."
EXTRACTION_TIMEOUT=60
COUNTER=0

while [ $COUNTER -lt $EXTRACTION_TIMEOUT ]; do
    # Check for extracted directories
    if ls -d "$EXTENSIONS_DIR"/*ioflow* >/dev/null 2>&1; then
        EXTRACTED_DIR=$(ls -d "$EXTENSIONS_DIR"/*ioflow* | head -1)
        if [ -d "$EXTRACTED_DIR" ] && [ "$EXTRACTED_DIR" != "$EXTENSIONS_DIR/ioflow-mcp-v1.0-final.dxt" ]; then
            log_success "Extension extracted to: $(basename "$EXTRACTED_DIR")"
            break
        fi
    fi
    
    # Check installation registry
    if [ -f "$CLAUDE_DIR/extensions-installations.json" ]; then
        if grep -q "ioflow" "$CLAUDE_DIR/extensions-installations.json" 2>/dev/null; then
            log_success "Extension registered in Claude Desktop"
            break
        fi
    fi
    
    echo -n "."
    sleep 2
    ((COUNTER+=2))
done

if [ $COUNTER -ge $EXTRACTION_TIMEOUT ]; then
    log_warning "Extension may not have been extracted automatically"
    echo
    echo "Manual steps to complete installation:"
    echo "1. In Claude Desktop, look for the extensions menu"
    echo "2. Check if IOFlow extension appears in the list"
    echo "3. If not, try restarting Claude Desktop"
fi

echo

# Fix permissions on any extracted extensions
log_info "Fixing permissions on extracted extensions..."
FIXED_ANY=false

for dir in "$EXTENSIONS_DIR"/*ioflow*/; do
    if [ -d "$dir" ]; then
        log_info "Fixing permissions in $(basename "$dir")"
        
        # Fix Python executables
        if [ -d "$dir/server/venv/bin" ]; then
            chmod +x "$dir/server/venv/bin"/* 2>/dev/null || true
            log_info "Fixed Python executable permissions"
        fi
        
        # Fix Python files
        if [ -d "$dir/server" ]; then
            find "$dir/server" -type f -name "python*" -exec chmod +x {} \; 2>/dev/null || true
            find "$dir/server" -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
            log_info "Fixed Python file permissions"
        fi
        
        FIXED_ANY=true
    fi
done

if [ "$FIXED_ANY" = true ]; then
    log_success "Permissions fixed on extracted extensions"
else
    log_warning "No extracted extensions found to fix permissions on"
fi

# Get extension ID
EXT_ID=""
if [ -f "$CLAUDE_DIR/extensions-installations.json" ]; then
    EXT_ID=$(grep -o '"[^"]*ioflow[^"]*"' "$CLAUDE_DIR/extensions-installations.json" 2>/dev/null | head -1 | tr -d '"' || echo "")
fi

if [ -z "$EXT_ID" ]; then
    # Fallback: look for directory
    IOFLOW_DIR=$(ls -d "$EXTENSIONS_DIR"/*ioflow* 2>/dev/null | head -1 | grep -v "\.dxt$" || echo "")
    if [ -n "$IOFLOW_DIR" ]; then
        EXT_ID=$(basename "$IOFLOW_DIR")
    else
        EXT_ID="local.dxt.ioflow-team.ioflow"  # Default fallback
    fi
fi

log_info "Using extension ID: $EXT_ID"

# Create configuration
log_info "Creating Claude Desktop configuration..."

# Backup existing config
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    log_info "Backed up existing configuration"
fi

# Create new configuration
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {},
  "dxtExtensions": [
    {
      "dxt": "$EXT_ID",
      "config": {
        "ioflow_base_url": "$BASE_URL",
        "ioflow_api_key": "$API_KEY"
      }
    }
  ]
}
EOF

log_success "Configuration created"

# Create permission fixer script for later use
PERM_SCRIPT="$HOME/.ioflow-fix-permissions.sh"
cat > "$PERM_SCRIPT" << 'EOF'
#!/bin/bash
# IOFlow Permission Fixer - Run this if you have permission issues

CLAUDE_DIR=""
case "$(uname -s)" in
    Darwin*) CLAUDE_DIR="$HOME/Library/Application Support/Claude" ;;
    Linux*)  CLAUDE_DIR="$HOME/.config/Claude" ;;
esac

EXTENSIONS_DIR="$CLAUDE_DIR/Claude Extensions"

echo "🔧 Fixing IOFlow extension permissions..."

FIXED=false
for dir in "$EXTENSIONS_DIR"/*ioflow*/; do
    if [ -d "$dir" ]; then
        echo "Fixing $(basename "$dir")..."
        
        if [ -d "$dir/server/venv/bin" ]; then
            chmod +x "$dir/server/venv/bin"/* 2>/dev/null || true
        fi
        
        if [ -d "$dir/server" ]; then
            find "$dir/server" -type f -name "python*" -exec chmod +x {} \; 2>/dev/null || true
            find "$dir/server" -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
        fi
        
        FIXED=true
    fi
done

if [ "$FIXED" = true ]; then
    echo "✅ Permissions fixed! Restart Claude Desktop to apply changes."
else
    echo "⚠️  No IOFlow extensions found."
fi
EOF

chmod +x "$PERM_SCRIPT"

# Final instructions
echo
log_success "Installation completed!"
echo
echo "📋 Next Steps:"
echo "1. ✅ Claude Desktop should be running with the extension"
echo "2. ✅ Configuration has been updated"
echo "3. 🔄 Restart Claude Desktop to ensure everything loads"
echo "4. 🧪 Test with: 'List my IOFlow applications'"
echo
echo "🔧 If you encounter permission issues later:"
echo "   Run: $PERM_SCRIPT"
echo
echo "📊 Verification:"
echo "   Extension ID: $EXT_ID"
echo "   Config file: $CONFIG_FILE"
echo "   IOFlow URL: $BASE_URL"
echo
echo "🎉 Installation should now be working!"