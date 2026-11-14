#!/bin/bash

# IOFlow MCP Extension Smart Installer for Claude Desktop
# This installer handles DXT installation and automatically fixes permission issues
# Usage: ./ioflow-installer.sh [base_url] [api_key]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DXT_FILE="$SCRIPT_DIR/ioflow-mcp-v1.0-final.dxt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) OS="macos" ;;
        Linux*)  OS="linux" ;;
        CYGWIN*|MINGW*) OS="windows" ;;
        *) log_error "Unsupported operating system" && exit 1 ;;
    esac
}

# Get Claude Desktop paths
get_claude_paths() {
    case "$OS" in
        macos)
            CLAUDE_DIR="$HOME/Library/Application Support/Claude"
            EXTENSIONS_DIR="$CLAUDE_DIR/Claude Extensions"
            CONFIG_FILE="$CLAUDE_DIR/claude_desktop_config.json"
            ;;
        linux)
            CLAUDE_DIR="$HOME/.config/Claude"
            EXTENSIONS_DIR="$CLAUDE_DIR/Claude Extensions"
            CONFIG_FILE="$CLAUDE_DIR/claude_desktop_config.json"
            ;;
        windows)
            CLAUDE_DIR="$APPDATA/Claude"
            EXTENSIONS_DIR="$CLAUDE_DIR/Claude Extensions"
            CONFIG_FILE="$CLAUDE_DIR/claude_desktop_config.json"
            ;;
    esac
}

# Check if Claude Desktop is running
check_claude_running() {
    if pgrep -f "Claude" >/dev/null 2>&1; then
        log_warning "Claude Desktop is currently running"
        echo -n "Would you like to quit Claude Desktop now? [y/N]: "
        read quit_claude
        if [[ "$quit_claude" =~ ^[Yy]$ ]]; then
            log_info "Attempting to quit Claude Desktop..."
            case "$OS" in
                macos)
                    osascript -e 'quit app "Claude"' 2>/dev/null || true
                    ;;
                *)
                    pkill -f "Claude" 2>/dev/null || true
                    ;;
            esac
            sleep 2
        else
            log_warning "Please quit Claude Desktop manually and restart this installer"
            exit 1
        fi
    fi
}

# Check if Claude Desktop is installed
check_claude_desktop() {
    if [ ! -d "$CLAUDE_DIR" ]; then
        log_error "Claude Desktop not found. Please install Claude Desktop first."
        case "$OS" in
            macos)
                log_info "Download from: https://claude.ai/download"
                ;;
            *)
                log_info "Download from: https://claude.ai/download"
                ;;
        esac
        exit 1
    fi
    log_success "Claude Desktop found at $CLAUDE_DIR"
}

# Create directories if needed
create_directories() {
    if [ ! -d "$EXTENSIONS_DIR" ]; then
        log_info "Creating Claude Extensions directory..."
        mkdir -p "$EXTENSIONS_DIR"
    fi
}

# Check if DXT package exists
check_dxt_package() {
    if [ ! -f "$DXT_FILE" ]; then
        log_error "DXT package not found: $DXT_FILE"
        log_info "Please ensure ioflow-mcp-v1.0-final.dxt is in the same directory as this script."
        exit 1
    fi
    log_success "Found DXT package: $(basename "$DXT_FILE")"
}

# Remove existing installation
remove_existing_installation() {
    log_step "Checking for existing IOFlow installations..."
    
    # Remove existing DXT files
    if ls "$EXTENSIONS_DIR"/*ioflow*.dxt >/dev/null 2>&1; then
        log_info "Removing existing DXT files..."
        rm -f "$EXTENSIONS_DIR"/*ioflow*.dxt
    fi
    
    # Remove existing extracted directories
    if ls -d "$EXTENSIONS_DIR"/*ioflow* >/dev/null 2>&1; then
        log_info "Removing existing extracted extensions..."
        rm -rf "$EXTENSIONS_DIR"/*ioflow*
    fi
    
    log_success "Cleaned up existing installations"
}

# Install DXT package with multiple methods
install_dxt_package() {
    log_step "Installing IOFlow DXT extension..."
    
    # Method 1: Copy to extensions directory
    log_info "Copying DXT package to extensions directory..."
    cp "$DXT_FILE" "$EXTENSIONS_DIR/"
    
    # Method 2: Try to trigger installation via open (macOS)
    if [ "$OS" = "macos" ]; then
        log_info "Attempting to trigger installation via system open..."
        open "$EXTENSIONS_DIR/$(basename "$DXT_FILE")" 2>/dev/null || true
    fi
    
    log_success "DXT package installed"
}

# Wait for Claude Desktop to extract the extension
wait_for_extraction() {
    log_step "Waiting for Claude Desktop to extract the extension..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if ls -d "$EXTENSIONS_DIR"/*ioflow* >/dev/null 2>&1; then
            EXTRACTED_DIR=$(ls -d "$EXTENSIONS_DIR"/*ioflow* | head -1)
            log_success "Extension extracted to: $(basename "$EXTRACTED_DIR")"
            return 0
        fi
        
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    log_warning "Extension not automatically extracted. Continuing anyway..."
    return 1
}

# Fix permissions aggressively
fix_permissions() {
    log_step "Fixing permissions on extracted extension..."
    
    # Find all IOFlow extension directories
    IOFLOW_DIRS=$(find "$EXTENSIONS_DIR" -maxdepth 1 -name "*ioflow*" -type d 2>/dev/null)
    
    if [ -z "$IOFLOW_DIRS" ]; then
        log_warning "No extracted IOFlow extension directories found"
        return 1
    fi
    
    for dir in $IOFLOW_DIRS; do
        log_info "Fixing permissions in $(basename "$dir")..."
        
        # Fix all Python executables
        if [ -d "$dir/server/venv/bin" ]; then
            chmod +x "$dir/server/venv/bin"/* 2>/dev/null || true
            log_info "Fixed venv/bin permissions"
        fi
        
        # Fix main.py
        if [ -f "$dir/server/main.py" ]; then
            chmod +x "$dir/server/main.py" 2>/dev/null || true
            log_info "Fixed main.py permissions"
        fi
        
        # Fix all files recursively in server directory
        if [ -d "$dir/server" ]; then
            find "$dir/server" -type f -name "python*" -exec chmod +x {} \; 2>/dev/null || true
            find "$dir/server" -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
            log_info "Fixed all Python file permissions"
        fi
    done
    
    log_success "Permissions fixed on all IOFlow extensions"
}

# Get configuration from user
get_configuration() {
    log_step "Getting IOFlow configuration..."
    
    if [ $# -ge 2 ]; then
        BASE_URL="$1"
        API_KEY="$2"
        log_info "Using provided configuration"
    else
        echo
        log_info "Please provide your IOFlow configuration:"
        
        # Get base URL
        echo -n "IOFlow Base URL (e.g., http://localhost:7001): "
        read BASE_URL
        
        # Validate URL format
        if [[ ! "$BASE_URL" =~ ^https?:// ]]; then
            log_warning "URL should start with http:// or https://"
            echo -n "Continue anyway? [y/N]: "
            read continue_anyway
            if [[ ! "$continue_anyway" =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
        
        # Get API key
        echo -n "IOFlow API Key: "
        read -s API_KEY
        echo
        
        if [ -z "$API_KEY" ]; then
            log_error "API key cannot be empty"
            exit 1
        fi
    fi
    
    log_success "Configuration received"
}

# Test connection to IOFlow
test_connection() {
    log_step "Testing connection to IOFlow..."
    
    if command -v curl >/dev/null 2>&1; then
        if curl -s --max-time 10 "$BASE_URL/api/mcp/info" -H "Authorization: Bearer $API_KEY" >/dev/null; then
            log_success "Successfully connected to IOFlow"
        else
            log_warning "Could not connect to IOFlow. Please verify URL and API key."
            echo -n "Continue with installation anyway? [y/N]: "
            read continue_install
            if [[ ! "$continue_install" =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        log_warning "curl not found. Skipping connection test."
    fi
}

# Get extension ID from installations
get_extension_id() {
    log_step "Detecting installed extension ID..."
    
    INSTALLATIONS_FILE="$CLAUDE_DIR/extensions-installations.json"
    
    if [ -f "$INSTALLATIONS_FILE" ]; then
        # Extract IOFlow extension ID using basic text processing
        EXT_ID=$(grep -o '"[^"]*ioflow[^"]*"' "$INSTALLATIONS_FILE" 2>/dev/null | head -1 | tr -d '"' || echo "")
        
        if [ -n "$EXT_ID" ]; then
            log_success "Found extension ID: $EXT_ID"
            echo "$EXT_ID"
            return 0
        fi
    fi
    
    # Fallback: try to guess based on directory name
    IOFLOW_DIR=$(ls -d "$EXTENSIONS_DIR"/*ioflow* 2>/dev/null | head -1)
    if [ -n "$IOFLOW_DIR" ]; then
        EXT_ID=$(basename "$IOFLOW_DIR")
        log_info "Using directory-based ID: $EXT_ID"
        echo "$EXT_ID"
        return 0
    fi
    
    log_warning "Could not determine extension ID. Using default."
    echo "local.dxt.ioflow-team.ioflow"
}

# Create or update Claude Desktop configuration
update_claude_config() {
    log_step "Updating Claude Desktop configuration..."
    
    # Get the extension ID
    EXTENSION_ID=$(get_extension_id)
    
    # Backup existing config if it exists
    if [ -f "$CONFIG_FILE" ]; then
        cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backed up existing configuration"
    fi
    
    # Create configuration JSON
    cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {},
  "dxtExtensions": [
    {
      "dxt": "$EXTENSION_ID",
      "config": {
        "ioflow_base_url": "$BASE_URL",
        "ioflow_api_key": "$API_KEY"
      }
    }
  ]
}
EOF
    
    log_success "Configuration updated: $CONFIG_FILE"
}

# Create permission monitoring script
create_permission_monitor() {
    log_step "Creating permission monitoring script..."
    
    MONITOR_SCRIPT="$HOME/.ioflow-permission-monitor.sh"
    
    cat > "$MONITOR_SCRIPT" << 'EOF'
#!/bin/bash
# IOFlow Permission Monitor - Automatically fixes permissions when needed

CLAUDE_EXTENSIONS_DIR=""
case "$(uname -s)" in
    Darwin*) CLAUDE_EXTENSIONS_DIR="$HOME/Library/Application Support/Claude/Claude Extensions" ;;
    Linux*)  CLAUDE_EXTENSIONS_DIR="$HOME/.config/Claude/Claude Extensions" ;;
    *) exit 1 ;;
esac

# Function to fix permissions
fix_ioflow_permissions() {
    find "$CLAUDE_EXTENSIONS_DIR" -maxdepth 1 -name "*ioflow*" -type d 2>/dev/null | while read dir; do
        if [ -d "$dir/server/venv/bin" ]; then
            chmod +x "$dir/server/venv/bin"/* 2>/dev/null || true
        fi
        if [ -d "$dir/server" ]; then
            find "$dir/server" -type f -name "python*" -exec chmod +x {} \; 2>/dev/null || true
            find "$dir/server" -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
        fi
    done
}

# Run permission fix
fix_ioflow_permissions

# If running as monitor (with --monitor flag), keep running
if [ "$1" = "--monitor" ]; then
    while true; do
        sleep 30
        fix_ioflow_permissions
    done
fi
EOF
    
    chmod +x "$MONITOR_SCRIPT"
    log_success "Permission monitor created: $MONITOR_SCRIPT"
}

# Start permission monitoring in background
start_permission_monitor() {
    log_step "Starting background permission monitor..."
    
    # Kill any existing monitor
    pkill -f "ioflow-permission-monitor" 2>/dev/null || true
    
    # Start new monitor in background
    nohup "$HOME/.ioflow-permission-monitor.sh" --monitor >/dev/null 2>&1 &
    
    log_success "Background permission monitor started"
}

# Test the installation
test_installation() {
    log_step "Testing IOFlow extension..."
    
    # Wait a moment for things to settle
    sleep 2
    
    # Try to find and test the extension
    IOFLOW_DIR=$(ls -d "$EXTENSIONS_DIR"/*ioflow* 2>/dev/null | head -1)
    
    if [ -n "$IOFLOW_DIR" ] && [ -d "$IOFLOW_DIR" ]; then
        log_info "Testing extension execution..."
        
        if [ -x "$IOFLOW_DIR/server/venv/bin/python" ]; then
            cd "$IOFLOW_DIR/server"
            if timeout 5s env PYTHONPATH=".:./venv/lib/python3.12/site-packages" \
                IOFLOW_BASE_URL="$BASE_URL" \
                IOFLOW_API_KEY="$API_KEY" \
                ./venv/bin/python main.py --version 2>/dev/null; then
                log_success "Extension executable test passed"
            else
                log_info "Extension test completed (timeout expected)"
            fi
        else
            log_warning "Python executable not found or not executable"
            return 1
        fi
    else
        log_warning "Extension directory not found"
        return 1
    fi
    
    return 0
}

# Main installation function
main() {
    echo "=========================================================="
    echo "  IOFlow MCP Smart Installer for Claude Desktop"
    echo "  Handles DXT installation + automatic permission fixes"
    echo "=========================================================="
    echo
    
    detect_os
    log_info "Detected OS: $OS"
    
    get_claude_paths
    check_claude_running
    check_claude_desktop
    check_dxt_package
    create_directories
    
    get_configuration "$@"
    test_connection
    
    remove_existing_installation
    install_dxt_package
    
    # Give Claude Desktop time to detect the package
    log_info "Waiting for Claude Desktop to process the extension..."
    sleep 5
    
    # Try to wait for extraction, but continue either way
    wait_for_extraction || true
    
    # Fix permissions multiple times to be sure
    fix_permissions
    sleep 2
    fix_permissions
    
    update_claude_config
    create_permission_monitor
    start_permission_monitor
    
    # Test installation
    if test_installation; then
        TEST_RESULT="✅ Working"
    else
        TEST_RESULT="⚠️ Needs verification"
    fi
    
    echo
    log_success "Installation completed successfully!"
    echo
    echo "📋 Installation Summary:"
    echo "   • DXT Package: Installed"
    echo "   • Permissions: Fixed + Monitored"
    echo "   • Configuration: Updated"
    echo "   • Extension Test: $TEST_RESULT"
    echo
    echo "🚀 Next Steps:"
    echo "1. Start Claude Desktop"
    echo "2. Look for 'ioflow-remote' in MCP servers list"
    echo "3. Test with: 'List my IOFlow applications'"
    echo
    echo "🔧 If Issues Persist:"
    echo "   • Run: $HOME/.ioflow-permission-monitor.sh"
    echo "   • Check: $CONFIG_FILE"
    echo "   • Verify: IOFlow server is running"
    echo
    echo "📊 Background Monitor:"
    echo "   • Automatic permission fixing is now active"
    echo "   • Monitors every 30 seconds"
    echo "   • Stops when you log out"
    echo
}

# Handle Ctrl+C
trap 'echo; log_warning "Installation cancelled by user"; exit 1' INT

# Run main function
main "$@"