#!/bin/bash

echo "Starting IOFlow Frontend..."

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start the frontend with Vite
echo "Starting frontend server on http://localhost:5173"
npm run dev