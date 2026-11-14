#!/bin/bash

# Build Complete Distribution Script for IOFlow
# This script builds the frontend and sets up the backend to serve it as static files

set -e  # Exit on error

echo "🚀 Building IOFlow Complete Distribution..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed. Please install Node.js first.${NC}"
    exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed. Please install Python 3 first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Step 1: Building Frontend...${NC}"
cd frontend

# Install frontend dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Build the frontend
echo "Building frontend production bundle..."
npm run build

# Check if build was successful
if [ ! -d "dist" ]; then
    echo -e "${RED}❌ Frontend build failed. No dist directory found.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Frontend build completed successfully!${NC}"

# Go back to root directory
cd "$SCRIPT_DIR"

echo -e "${YELLOW}📋 Step 2: Setting up Backend Python environment...${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip first
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements with verbose output to see what's being installed
echo "Installing packages from backend/requirements.txt..."
pip install -r backend/requirements.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install Python dependencies${NC}"
    echo "Please check the error messages above and ensure:"
    echo "  - You have internet connection"
    echo "  - Python 3.10+ is installed"
    echo "  - pip is working correctly"
    exit 1
fi

# Verify critical packages are installed
echo "Verifying installation..."
python3 -c "import fastapi, sqlalchemy, uvicorn, razorpay, httpx, paramiko" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Some critical packages are missing${NC}"
    echo "Attempting to reinstall..."
    pip install --force-reinstall -r backend/requirements.txt
fi

echo -e "${GREEN}✅ Backend Python dependencies installed successfully!${NC}"

echo -e "${YELLOW}📦 Step 3: Setting up Backend to serve static files...${NC}"

# Create static directory in backend if it doesn't exist
if [ ! -d "backend/static" ]; then
    mkdir -p backend/static
fi

# Copy the built frontend to backend static directory
echo "Copying frontend build to backend static directory..."
rm -rf backend/static/*
cp -r frontend/dist/* backend/static/

echo -e "${GREEN}✅ Frontend files copied to backend/static!${NC}"

echo -e "${YELLOW}🔧 Step 4: Updating backend configuration...${NC}"

# Create a backup of main.py if it exists
if [ -f "backend/main.py" ]; then
    cp backend/main.py backend/main.py.backup
    echo "Created backup of main.py as main.py.backup"
fi

echo -e "${GREEN}✅ Build process completed!${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. The backend main.py needs to be updated to serve static files."
echo "2. Add the following to your FastAPI app in main.py:"
echo ""
echo "   from fastapi.staticfiles import StaticFiles"
echo "   from fastapi.responses import FileResponse"
echo ""
echo "   # Mount static files"
echo "   app.mount(\"/assets\", StaticFiles(directory=\"static/assets\"), name=\"static-assets\")"
echo ""
echo "   # Serve index.html for all non-API routes"
echo "   @app.get(\"/{full_path:path}\")"
echo "   async def serve_spa(full_path: str):"
echo "       if full_path.startswith(\"api/\"):"
echo "           raise HTTPException(status_code=404)"
echo "       return FileResponse(\"static/index.html\")"
echo ""
echo "3. Start the backend with: ./start_backend.sh"
echo "4. Access the complete application at: http://localhost:7001"
echo ""
echo -e "${GREEN}🎉 Distribution build complete!${NC}"