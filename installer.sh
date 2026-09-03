#!/bin/bash

# Phoenix Obliterator Ultra Pro - Installer
# Cross-platform installer for Kali Linux, Termux, Windows

echo "╔═══════════════════════════════════════════════════╗"
echo "║  🔥 PHOENIX OBLITERATOR ULTRA PRO INSTALLER      ║"
echo "╚═══════════════════════════════════════════════════╝"

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "[✓] Linux detected"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv nodejs npm
    pip3 install playwright
    python3 -m playwright install chromium
    pip3 install -r backend/python_core/requirements.txt
    npm install --prefix backend/node_whatsapp
    
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "[✓] macOS detected"
    brew install python3 node
    pip3 install -r backend/python_core/requirements.txt
    pip3 install playwright
    python3 -m playwright install chromium
    npm install --prefix backend/node_whatsapp
    
elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
    echo "[✓] Windows detected"
    pip install -r backend/python_core/requirements.txt
    pip install playwright
    python -m playwright install chromium
    cd backend/node_whatsapp && npm install
    
elif [[ -d "/data/data/com.termux" ]]; then
    echo "[✓] Termux detected"
    pkg update
    pkg install -y python python-pip nodejs
    pip install -r backend/python_core/requirements.txt
    pip install playwright
    python -m playwright install chromium
    npm install --prefix backend/node_whatsapp
    
else
    echo "[!] Unknown OS. Installing dependencies manually..."
    pip install -r backend/python_core/requirements.txt
fi

echo "[✓] Installation complete!"
echo ""
echo "To start the tool:"
echo "  cd WhatsApp_Phoenix_Obliterator_Pro"
echo "  python backend/python_core/main.py"