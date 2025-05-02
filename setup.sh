#!/bin/bash

# Setup script for the Finger Bot unified server

echo "Setting up Finger Bot unified server..."

# Install Python dependencies
echo "Installing Python dependencies..."
pip install fastapi uvicorn httpx requests websockets qrcode[pil] apscheduler python-multipart python-jose[cryptography] passlib[bcrypt] pydantic[email] pydantic-settings

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo "Setup complete!"
echo ""
echo "To start the unified server:"
echo "1. Start the Next.js frontend development server:"
echo "   cd frontend && npm run dev -- -p 3001"
echo ""
echo "2. In a separate terminal, start the unified server:"
echo "   python server.py"
echo ""
echo "The unified server will be available at http://localhost:3000"
