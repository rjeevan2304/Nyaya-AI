#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Nyaya.ai — Server Setup Script
# This runs ON the Hetzner VPS, not on your Mac.
# Called automatically by push-to-server.sh
# ═══════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd /opt/nyaya-ai

echo ""
echo "🏛  Nyaya.ai Server Setup"
echo "═════════════════════════"

# ── Install Docker if not present ────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo -e "${YELLOW}Installing Docker...${NC}"
    apt-get update -qq
    apt-get install -y -qq docker.io curl
    systemctl start docker
    systemctl enable docker
    echo -e "   ${GREEN}✓ Docker installed${NC}"
else
    echo -e "   ${GREEN}✓ Docker already installed${NC}"
fi

# ── Install Docker Compose plugin if not present ─────────────────
if ! docker compose version &>/dev/null 2>&1; then
    apt-get install -y -qq docker-compose-plugin
fi
echo -e "   ${GREEN}✓ Docker Compose ready${NC}"

# ── Build and start all containers ───────────────────────────────
echo -e "${YELLOW}Building and starting containers (first time: ~5 minutes)...${NC}"
docker compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
docker compose -f docker-compose.prod.yml up -d --build

echo -e "   ${GREEN}✓ Containers started${NC}"

# ── Wait for services to be healthy ──────────────────────────────
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
MAX_WAIT=120
ELAPSED=0
until curl -sf http://localhost/ping > /dev/null 2>&1; do
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo "⚠️  Services taking longer than expected. Check with: docker compose -f docker-compose.prod.yml logs"
        break
    fi
done
echo -e "   ${GREEN}✓ Services are up${NC}"

# ── Run data ingestion ────────────────────────────────────────────
echo -e "${YELLOW}Loading cases into database...${NC}"

# Wait for the API container to be healthy before ingesting
sleep 10
docker compose -f docker-compose.prod.yml exec -T api python ingest.py

echo -e "   ${GREEN}✓ Cases indexed${NC}"

# ── Install cloudflared for free tunnel ──────────────────────────
if ! command -v cloudflared &>/dev/null; then
    echo -e "${YELLOW}Installing Cloudflare tunnel tool...${NC}"
    ARCH=$(dpkg --print-architecture)
    if [ "$ARCH" = "arm64" ]; then
        DEB_FILE="cloudflared-linux-arm64.deb"
    else
        DEB_FILE="cloudflared-linux-amd64.deb"
    fi
    curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/$DEB_FILE" -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
    echo -e "   ${GREEN}✓ cloudflared installed${NC}"
fi

echo ""
echo "═════════════════════════════════════════════"
echo -e "${GREEN}✅  Nyaya.ai is running!${NC}"
echo "═════════════════════════════════════════════"
echo ""
echo "  Access via IP:    http://$(curl -s ifconfig.me)"
echo ""
echo "  For a free shareable HTTPS URL, run:"
echo -e "  ${YELLOW}bash /opt/nyaya-ai/start-tunnel.sh${NC}"
echo ""
