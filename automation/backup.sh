#!/bin/bash
# Masterbot Weekly Backup (R2 + GitHub)

BASE_DIR="/Users/aatifquamre/masterbot"
DATE=$(date +%Y%m%d)

# 1. Cloudflare R2 Backup (SQLite, ChromaDB, Models)
echo "Backing up to Cloudflare R2..."
$BASE_DIR/qnt/bin/qnt-backup run

# 2. GitHub Backup (Strategies, Configs)
echo "Backing up to GitHub..."
cd "$BASE_DIR"
git add strategies/ config/ risk/ sentiment/ automation/ qnt/
git commit -m "backup: weekly state $(date +%Y-%m-%d)" --allow-empty
git push

# 3. Telegram Notification
if [ -f "$BASE_DIR/.env" ]; then
  source "$BASE_DIR/.env"
  if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ ! -z "$TELEGRAM_CHAT_ID" ]; then
    curl -s -X POST \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" \
      -d text="✅ Weekly backup complete.
Date: $(date)
R2: SQLite + ChromaDB + Models uploaded
GitHub: Strategies and configs pushed
Storage: Cloudflare R2 (free tier)" > /dev/null
  fi
fi

# Log to QNT operational history
echo "[$(date +%Y-%m-%d)] NOTED: Full system backup completed (R2 + GitHub)." >> "$BASE_DIR/qnt/.issues_log"
