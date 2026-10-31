#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Nyaya.ai — Push to Server
# Run this on your Mac to deploy to the Hetzner VPS
#
# Usage: bash push-to-server.sh YOUR_SERVER_IP
# Example: bash push-to-server.sh 65.21.42.123
# ═══════════════════════════════════════════════════════════════════

set -e

SERVER_IP=$1
if [ -z "$SERVER_IP" ]; then
    echo "Usage: bash push-to-server.sh YOUR_SERVER_IP"
    echo "Example: bash push-to-server.sh 65.21.42.123"
    echo ""
    echo "Find your server IP in the Hetzner Cloud console."
    exit 1
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "🚀  Deploying Nyaya.ai to $SERVER_IP"
echo ""

# ── Step 1: Upload all files ───────────────────────────────────────
echo -e "${YELLOW}[1/3] Uploading files to server...${NC}"
echo "   (This copies your entire nyaya-ai folder)"

# Create directory on server
ssh root@$SERVER_IP "mkdir -p /opt/nyaya-ai"

# Upload with rsync (skips unchanged files for speed)
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'backend/venv' \
    --exclude '.env' \
    "$(dirname "$0")/" \
    root@$SERVER_IP:/opt/nyaya-ai/

echo -e "   ${GREEN}✓ Files uploaded${NC}"

# ── Step 2: Set up .env on server ─────────────────────────────────
echo -e "${YELLOW}[2/3] Checking environment config...${NC}"

# Check if .env already exists on server
ENV_EXISTS=$(ssh root@$SERVER_IP "[ -f /opt/nyaya-ai/.env ] && echo yes || echo no")

if [ "$ENV_EXISTS" = "no" ]; then
    ssh root@$SERVER_IP "cp /opt/nyaya-ai/.env.example /opt/nyaya-ai/.env"
    echo ""
    echo -e "   ${YELLOW}⚠️  IMPORTANT: You need to add your ANTHROPIC_API_KEY${NC}"
    echo "   Run this command to edit it on the server:"
    echo -e "   ${YELLOW}ssh root@$SERVER_IP 'nano /opt/nyaya-ai/.env'${NC}"
    echo ""
    echo "   Replace 'your_api_key_here' with your actual key from:"
    echo "   https://console.anthropic.com"
    echo ""
    read -p "   Press Enter when you have added the key, or Ctrl+C to skip..."
fi
echo -e "   ${GREEN}✓ Environment config ready${NC}"

# ── Step 3: Run setup on server ───────────────────────────────────
echo -e "${YELLOW}[3/3] Running setup on server...${NC}"
ssh root@$SERVER_IP "bash /opt/nyaya-ai/server-setup.sh"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}✅  Deployment complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "  Your site is running at:"
echo -e "  ${YELLOW}http://$SERVER_IP${NC}"
echo ""
echo "  To get a free HTTPS URL (shareable link), run:"
echo -e "  ${YELLOW}ssh root@$SERVER_IP 'bash /opt/nyaya-ai/start-tunnel.sh'${NC}"
echo ""
echo "  To update the site later, just run this script again."
echo ""
