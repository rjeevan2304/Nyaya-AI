#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# Nyaya.ai — Start Cloudflare Tunnel
# Run this ON the server to get a free shareable HTTPS URL.
#
# The URL changes each restart. For a permanent URL, you need to
# connect a domain in your Cloudflare account (free).
# ═══════════════════════════════════════════════════════════════════

echo ""
echo "🌐  Starting Cloudflare Tunnel..."
echo ""
echo "   A public HTTPS URL will appear below."
echo "   Share that URL with lawyers to access Nyaya.ai."
echo ""
echo "   ⚠️  The URL changes every time you restart this."
echo "   For a permanent URL, follow the guide in the Word document."
echo ""
echo "   Press Ctrl+C to stop the tunnel."
echo ""
echo "═══════════════════════════════════════════"

# Run in foreground so the URL shows in terminal
cloudflared tunnel --url http://localhost:80
