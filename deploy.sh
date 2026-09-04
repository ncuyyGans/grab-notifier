#!/bin/bash
# Script Deploy Otomatis Grab Notifier Bot ke Fly.io
# Usage: ./deploy.sh [APP_NAME] [BOT_TOKEN]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
APP_NAME="${1:-grab-notifier-bot}"
BOT_TOKEN="${2:-}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Grab Notifier Bot - Fly.io Deployer${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo -e "${YELLOW}Fly CLI belum terinstall. Menginstall...${NC}"
    curl -L https://fly.io/install.sh | sh
    
    # Add to PATH
    export PATH="$HOME/.fly/bin:$PATH"
    
    # Check again
    if ! command -v fly &> /dev/null; then
        echo -e "${RED}Gagal install Fly CLI. Coba install manual:${NC}"
        echo "curl -L https://fly.io/install.sh | sh"
        exit 1
    fi
fi

echo -e "${GREEN}✓ Fly CLI sudah terinstall${NC}"

# Check if logged in
if ! fly auth whoami &> /dev/null; then
    echo -e "${YELLOW}Belum login ke Fly.io. Silakan login...${NC}"
    fly auth login
fi

echo -e "${GREEN}✓ Sudah login ke Fly.io${NC}"

# Get bot token if not provided
if [ -z "$BOT_TOKEN" ]; then
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
        BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
        echo -e "${GREEN}✓ Menggunakan TELEGRAM_BOT_TOKEN dari environment${NC}"
    else
        echo -e "${YELLOW}Masukkan Telegram Bot Token:${NC}"
        read -s BOT_TOKEN
        echo ""
    fi
fi

if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}Error: Bot token tidak boleh kosong!${NC}"
    exit 1
fi

# Update fly.toml with app name
echo -e "${YELLOW}Mengupdate konfigurasi app name...${NC}"
sed -i "s/app = \".*\"/app = \"$APP_NAME\"/" fly.toml

# Check if app exists
echo -e "${YELLOW}Mengecek app '$APP_NAME'...${NC}"
if fly status --app "$APP_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ App sudah ada, akan di-update${NC}"
else
    echo -e "${YELLOW}App belum ada, membuat baru...${NC}"
    fly apps create "$APP_NAME"
    echo -e "${GREEN}✓ App '$APP_NAME' berhasil dibuat${NC}"
fi

# Set secrets
echo -e "${YELLOW}Mengatur secrets...${NC}"
echo "$BOT_TOKEN" | fly secrets set TELEGRAM_BOT_TOKEN="$BOT_TOKEN" --app "$APP_NAME"
echo -e "${GREEN}✓ Secrets berhasil di-set${NC}"

# Deploy
echo -e "${YELLOW}Deploying ke Fly.io...${NC}"
echo -e "${YELLOW}(Ini bisa memakan waktu 2-5 menit pertama kali)${NC}"
fly deploy --app "$APP_NAME"

# Get app URL
APP_URL="https://$APP_NAME.fly.dev"
WEBHOOK_URL="$APP_URL/webhook"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deploy Berhasil! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "App URL: ${YELLOW}$APP_URL${NC}"
echo -e "Webhook: ${YELLOW}$WEBHOOK_URL${NC}"
echo ""

# Set webhook automatically
echo -e "${YELLOW}Mengatur webhook Telegram...${NC}"
WEBHOOK_RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$WEBHOOK_URL\",\"allowed_updates\":[\"message\",\"edited_message\"]}")

if echo "$WEBHOOK_RESPONSE" | grep -q '"ok":true'; then
    echo -e "${GREEN}✓ Webhook berhasil di-set${NC}"
else
    echo -e "${RED}⚠ Gagal set webhook. Response:${NC}"
    echo "$WEBHOOK_RESPONSE"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup Selesai!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Command yang berguna:"
echo -e "  ${YELLOW}fly logs --app $APP_NAME${NC}     - Lihat logs"
echo -e "  ${YELLOW}fly status --app $APP_NAME${NC}   - Cek status"
echo -e "  ${YELLOW}fly restart --app $APP_NAME${NC}  - Restart app"
echo ""
echo -e "Test bot dengan kirim link Grab ke bot Telegram!"
echo ""
