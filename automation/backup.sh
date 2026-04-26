#!/bin/bash
# Masterbot Weekly Backup

BASE_DIR="/Users/aatifquamre/masterbot"
BACKUP_DIR="$BASE_DIR/logs/reports/backups"
DATE=$(date +%Y%m%d)

mkdir -p "$BACKUP_DIR"

# Zip important data
cd "$BASE_DIR"
tar -czf "$BACKUP_DIR/masterbot_backup_$DATE.tar.gz" \
    config/*.json .env \
    user_data/*.sqlite \
    strategies/active/*.py \
    risk/balance_state.json

# Only keep last 4 backups
ls -t "$BACKUP_DIR"/masterbot_backup_*.tar.gz | tail -n +5 | xargs rm -f -- 2>/dev/null

echo "Backup created: masterbot_backup_$DATE.tar.gz"
