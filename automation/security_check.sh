#!/bin/bash
# MasterBot Security Audit Script

BASE_DIR="/Users/aatifquamre/masterbot"
cd "$BASE_DIR"
source .env

FAILED=0

check_pass() { echo -e "[\033[0;32mPASS\033[0m] $1"; }
check_fail() { echo -e "[\033[0;31mFAIL\033[0m] $1"; FAILED=$((FAILED + 1)); }

# 1. .env exists
if [ -f .env ]; then check_pass ".env file exists"; else check_fail ".env file missing"; fi

# 2. .env permissions 600
PERM=$(stat -f "%Mp%Lp" .env)
if [ "$PERM" == "0600" ]; then check_pass ".env permissions are 600"; else check_fail ".env permissions too open ($PERM)"; fi

# 3. .env tracked
TRACKED=$(git ls-files .env)
if [ -z "$TRACKED" ]; then check_pass ".env is not tracked by git"; else check_fail ".env IS TRACKED BY GIT"; fi

# 4. Required keys
MISSING_KEYS=""
for key in BINANCE_API_KEY BINANCE_SECRET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID FREQTRADE_UI_USERNAME FREQTRADE_UI_PASSWORD; do
    if ! grep -q "^$key=" .env; then MISSING_KEYS="$MISSING_KEYS $key"; fi
done
if [ -z "$MISSING_KEYS" ]; then check_pass "All required keys exist in .env"; else check_fail "Missing keys:$MISSING_KEYS"; fi

# 5. API key not empty
if [ -n "$BINANCE_API_KEY" ]; then check_pass "Binance API key is not empty"; else check_fail "Binance API key is EMPTY"; fi

# 6. Telegram reachable
TG_RES=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe")
if [[ "$TG_RES" == *"\"ok\":true"* ]]; then check_pass "Telegram reachable"; else check_fail "Telegram unreachable"; fi

# 7. Freqtrade API reachable
FT_RES=$(curl -s -u "${FREQTRADE_UI_USERNAME}:${FREQTRADE_UI_PASSWORD}" http://100.90.68.42:8080/api/v1/ping)
if [[ "$FT_RES" == *"pong"* ]]; then check_pass "Freqtrade API accessible"; else check_fail "Freqtrade API unreachable"; fi

# 8. M2 Reachable (Tailscale)
if ping -c 1 -W 2 100.74.110.36 > /dev/null 2>&1; then check_pass "M2 reachable via Tailscale"; else check_fail "M2 unreachable"; fi

# 9. Git log visual check
echo -e "\n--- Latest Git Commits ---"
git log --all --oneline | head -10

if [ $FAILED -eq 0 ]; then
    echo -e "\n✅ ALL SECURITY CHECKS PASSED — Safe to start bot"
    exit 0
else
    echo -e "\n❌ $FAILED CHECKS FAILED — Fix issues before starting bot"
    exit 1
fi
