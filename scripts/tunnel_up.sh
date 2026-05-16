#!/usr/bin/env bash
# Start the full stack, extract the Cloudflare quick-tunnel URL, patch .env,
# then restart n8n so it picks up the correct WEBHOOK_URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"

echo "Starting all services..."
docker compose -f "$ROOT/docker-compose.yml" up -d

echo "Waiting for Cloudflare quick tunnel URL..."
TUNNEL_URL=""
for i in $(seq 1 40); do
    TUNNEL_URL=$(docker compose -f "$ROOT/docker-compose.yml" logs cloudflared 2>/dev/null \
        | grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' \
        | tail -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 3
done

if [ -z "$TUNNEL_URL" ]; then
    echo "ERROR: Tunnel URL not found in cloudflared logs after 2 minutes." >&2
    echo "Run: docker compose logs cloudflared" >&2
    exit 1
fi

echo "Got tunnel URL: $TUNNEL_URL"

# Write N8N_WEBHOOK_URL into .env (replace existing line or append)
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

if grep -q "^N8N_WEBHOOK_URL=" "$ENV_FILE"; then
    sed -i "s|^N8N_WEBHOOK_URL=.*|N8N_WEBHOOK_URL=${TUNNEL_URL}|" "$ENV_FILE"
else
    printf "\nN8N_WEBHOOK_URL=%s\n" "$TUNNEL_URL" >> "$ENV_FILE"
fi

echo "Updated .env → N8N_WEBHOOK_URL=${TUNNEL_URL}"

echo "Restarting n8n to apply new webhook URL..."
docker compose -f "$ROOT/docker-compose.yml" restart n8n

echo ""
echo "Stack is up:"
echo "  Dashboard → http://localhost:8501"
echo "  n8n       → http://localhost:5678"
echo "  Webhook   → ${TUNNEL_URL}"
