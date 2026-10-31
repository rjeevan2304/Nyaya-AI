#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Nyaya.ai — One-Click Setup Script for Mac M1
# Run this once: bash setup.sh
# ═══════════════════════════════════════════════════════════════════

set -e  # Exit immediately if any command fails

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

echo ""
echo "🏛  ═══════════════════════════════════════════"
echo "   Nyaya.ai — Setup for Mac M1"
echo "   ═══════════════════════════════════════════"
echo ""

# ── Step 1: Check for Homebrew ──────────────────────────────────────
echo -e "${BLUE}[1/7] Checking for Homebrew...${NC}"
if ! command -v brew &>/dev/null; then
    echo "   Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi
echo -e "   ${GREEN}✓ Homebrew ready${NC}"

# ── Step 2: Check for Python 3.11 ───────────────────────────────────
echo -e "${BLUE}[2/7] Checking Python 3.11...${NC}"
if ! command -v python3.11 &>/dev/null; then
    echo "   Installing Python 3.11 via Homebrew..."
    brew install python@3.11
fi
echo -e "   ${GREEN}✓ Python 3.11 ready${NC}"

# ── Step 3: Check for Docker Desktop ───────────────────────────────
echo -e "${BLUE}[3/7] Checking Docker...${NC}"
if ! command -v docker &>/dev/null; then
    echo ""
    echo -e "   ${YELLOW}⚠️  Docker Desktop is not installed.${NC}"
    echo "   Please download and install Docker Desktop for Mac:"
    echo "   → https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "   After installing, run this script again: bash setup.sh"
    exit 1
fi
if ! docker info &>/dev/null; then
    echo ""
    echo -e "   ${YELLOW}⚠️  Docker is installed but not running.${NC}"
    echo "   Please open Docker Desktop from your Applications folder."
    echo "   Wait for it to start, then run: bash setup.sh"
    exit 1
fi
echo -e "   ${GREEN}✓ Docker is running${NC}"

# ── Step 4: Create Python virtual environment ────────────────────────
echo -e "${BLUE}[4/7] Creating Python virtual environment...${NC}"
cd "$(dirname "$0")/backend"
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi
source venv/bin/activate
echo -e "   ${GREEN}✓ Virtual environment ready${NC}"

# ── Step 5: Install Python dependencies ─────────────────────────────
echo -e "${BLUE}[5/7] Installing Python packages (this may take 3-5 minutes)...${NC}"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo -e "   ${GREEN}✓ All packages installed${NC}"

# ── Step 6: Set up .env file ─────────────────────────────────────────
echo -e "${BLUE}[6/7] Setting up environment config...${NC}"
cd ..
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo -e "   ${YELLOW}→ Created .env file from template${NC}"
    echo -e "   ${YELLOW}→ IMPORTANT: Open .env and add your ANTHROPIC_API_KEY${NC}"
    echo "      Get your key at: https://console.anthropic.com"
    echo ""
fi
echo -e "   ${GREEN}✓ Environment config ready${NC}"

# ── Step 7: Start Qdrant and run ingestion ────────────────────────────
echo -e "${BLUE}[7/7] Starting Qdrant database...${NC}"
docker-compose up -d
echo "   Waiting for Qdrant to be ready..."
sleep 5

echo "   Loading cases into database..."
cd backend
source venv/bin/activate
python ingest.py

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}✅  Setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  To start Nyaya.ai, run:"
echo -e "  ${YELLOW}bash start.sh${NC}"
echo ""
echo "  Then open your browser:"
echo -e "  ${YELLOW}http://localhost:8000${NC}"
echo ""
