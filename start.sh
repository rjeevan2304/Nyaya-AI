#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Nyaya.ai — Start Script
# Run this every time you want to use the app: bash start.sh
# ═══════════════════════════════════════════════════════════════════

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "🏛  Starting Nyaya.ai..."
echo ""

# Make sure Docker is running
if ! docker info &>/dev/null; then
    echo -e "${YELLOW}⚠️  Docker is not running. Please open Docker Desktop first.${NC}"
    exit 1
fi

# Start Qdrant if not already running
docker-compose up -d
echo -e "   ${GREEN}✓ Qdrant database running${NC}"

# Activate venv and load env vars
cd "$(dirname "$0")/backend"
source venv/bin/activate
if [ -f "../.env" ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

echo -e "   ${GREEN}✓ Starting backend server...${NC}"
echo ""
echo -e "   ${YELLOW}Open your browser at: http://localhost:8000${NC}"
echo "   Press Ctrl+C to stop"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
