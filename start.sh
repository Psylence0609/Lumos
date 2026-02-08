#!/bin/bash
# Smart Home Agent System - Startup Script
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "============================================="
echo "  Smart Home Agent System"
echo "============================================="

# Check for venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Build frontend if needed
if [ ! -d "frontend/dist" ]; then
    echo "Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Generate self-signed certs if they don't exist
if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
    echo "Generating self-signed SSL certificate..."
    mkdir -p certs
    openssl req -x509 -newkey rsa:2048 \
        -keyout certs/key.pem -out certs/cert.pem \
        -days 365 -nodes \
        -subj "/CN=smarthome.local" \
        -addext "subjectAltName=DNS:smarthome.local,DNS:localhost,IP:0.0.0.0"
fi

# Start MQTT broker (mosquitto) if available and not already running
if command -v mosquitto &> /dev/null; then
    if ! pgrep -x mosquitto > /dev/null; then
        echo "Starting Mosquitto MQTT broker..."
        mosquitto -c config/mosquitto.conf -d 2>/dev/null || true
    else
        echo "Mosquitto already running"
    fi
else
    echo "WARNING: Mosquitto not installed."
    echo "  Install with: brew install mosquitto"
    exit 1
fi

# Detect LAN IP
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")

echo ""
echo "Starting Smart Home API server (HTTPS)..."
echo "  Local:      https://localhost:8443"
echo "  LAN:        https://${LAN_IP}:8443"
echo "  Simulation: https://${LAN_IP}:8443/simulation"
echo "  API Docs:   https://${LAN_IP}:8443/docs"
echo ""
echo "  On your iPhone: open https://${LAN_IP}:8443"
echo "  Accept the certificate warning once, then it works."
echo ""

# Start FastAPI server with HTTPS
python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8443 \
    --ssl-keyfile certs/key.pem \
    --ssl-certfile certs/cert.pem \
    --reload
