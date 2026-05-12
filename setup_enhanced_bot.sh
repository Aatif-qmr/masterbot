#!/bin/bash
# Enhanced Telegram Bot Setup and Testing Script
# ================================================
# This script helps you:
# 1. Configure iMessage integration for iPhone
# 2. Test the enhanced bot with inline keyboards
# 3. Setup webhook for instant responses

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🤖 MasterBot QNT - Enhanced Telegram Bot Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Function to display menu
show_menu() {
    echo "Select an option:"
    echo "  1) Test enhanced bot (inline keyboards)"
    echo "  2) Send main menu to Telegram"
    echo "  3) Configure iMessage integration"
    echo "  4) Test iMessage (Mac only)"
    echo "  5) Setup webhook for instant responses"
    echo "  6) Remove webhook (use polling instead)"
    echo "  7) View bot status"
    echo "  8) Exit"
    echo ""
}

# Function to test enhanced bot
test_bot() {
    echo "Testing enhanced bot..."
    python3 qnt/memory/enhanced_bot.py --test
    echo ""
    echo "✅ Test complete! Check your Telegram for:"
    echo "   - A test notification message"
    echo "   - A message with inline keyboard buttons"
}

# Function to send main menu
send_menu() {
    echo "Sending main menu..."
    python3 qnt/memory/enhanced_bot.py --menu
    echo ""
    echo "✅ Main menu sent! Check Telegram for interactive buttons."
}

# Function to configure iMessage
configure_imessage() {
    echo ""
    echo "📱 iMessage Integration Setup (Mac + iPhone)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "This will allow CRITICAL alerts to be sent to your iPhone via iMessage."
    echo ""
    read -p "Enter your iPhone number (with country code, e.g., +1234567890): " iphone_number
    
    if [ -z "$iphone_number" ]; then
        echo "❌ No number provided. Skipping configuration."
        return
    fi
    
    # Check if .env exists
    ENV_FILE="$SCRIPT_DIR/.env"
    if [ ! -f "$ENV_FILE" ]; then
        echo "⚠️  .env file not found. Creating from .env.example..."
        cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    fi
    
    # Add/update iMessage config in .env
    if grep -q "ENABLE_IMESSAGE" "$ENV_FILE"; then
        sed -i.bak "s/^ENABLE_IMESSAGE=.*/ENABLE_IMESSAGE=true/" "$ENV_FILE"
        sed -i.bak "s/^IPHONE_NUMBER=.*/IPHONE_NUMBER=$iphone_number/" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    else
        echo "" >> "$ENV_FILE"
        echo "# iMessage Integration (Mac + iPhone)" >> "$ENV_FILE"
        echo "ENABLE_IMESSAGE=true" >> "$ENV_FILE"
        echo "IPHONE_NUMBER=$iphone_number" >> "$ENV_FILE"
    fi
    
    echo ""
    echo "✅ iMessage configured!"
    echo "   - ENABLE_IMESSAGE=true"
    echo "   - IPHONE_NUMBER=$iphone_number"
    echo ""
    echo "⚠️  IMPORTANT: On your Mac, ensure:"
    echo "   1. Messages app is open and signed in"
    echo "   2. iMessage is enabled in System Preferences"
    echo "   3. Your iPhone number is registered with iMessage"
    echo ""
}

# Function to test iMessage
test_imessage() {
    echo ""
    echo "Testing iMessage..."
    
    # Check if running on Mac
    if [[ "$OSTYPE" != "darwin"* ]]; then
        echo "❌ iMessage only works on macOS. You're running on: $OSTYPE"
        return
    fi
    
    # Load iPhone number from .env
    ENV_FILE="$SCRIPT_DIR/.env"
    if [ ! -f "$ENV_FILE" ]; then
        echo "❌ .env file not found. Run option 3 first."
        return
    fi
    
    source "$ENV_FILE" 2>/dev/null || true
    
    if [ -z "$IPHONE_NUMBER" ] || [ "$ENABLE_IMESSAGE" != "true" ]; then
        echo "❌ iMessage not configured. Run option 3 first."
        return
    fi
    
    # Send test iMessage using AppleScript
    TEST_MSG="🚨 QNT Test Alert - $(date '+%H:%M IST')
This is a test of the critical alert system.
If you received this, iMessage integration is working!"
    
    osascript <<EOF
tell application "Messages"
    send "$TEST_MSG" to buddy "$IPHONE_NUMBER"
end tell
EOF
    
    if [ $? -eq 0 ]; then
        echo "✅ Test iMessage sent to $IPHONE_NUMBER"
        echo "   Check your iPhone!"
    else
        echo "❌ Failed to send iMessage"
        echo "   Make sure:"
        echo "   - Messages app is running on your Mac"
        echo "   - You're signed into iMessage"
        echo "   - The phone number is correct"
    fi
}

# Function to setup webhook
setup_webhook() {
    echo ""
    echo "🌐 Webhook Setup for Instant Responses"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Webhooks allow instant bot responses without polling delays."
    echo ""
    echo "Requirements:"
    echo "  - Public HTTPS URL (use ngrok for testing)"
    echo "  - SSL certificate (or use ngrok's auto-SSL)"
    echo ""
    read -p "Enter your public webhook URL (e.g., https://your-domain.com:8443/webhook): " webhook_url
    
    if [ -z "$webhook_url" ]; then
        echo "❌ No URL provided."
        return
    fi
    
    echo ""
    echo "Setting up webhook..."
    python3 qnt/memory/telegram_webhook_server.py --webhook-url "$webhook_url" --setup-only
    
    echo ""
    echo "✅ Webhook configured!"
    echo ""
    echo "To run the webhook server:"
    echo "  python3 qnt/memory/telegram_webhook_server.py \\"
    echo "    --webhook-url '$webhook_url' \\"
    echo "    --port 8443"
    echo ""
    echo "💡 Tip: For local testing, use ngrok:"
    echo "  brew install ngrok"
    echo "  ngrok http 8443"
    echo "  (Then use the ngrok HTTPS URL as your webhook URL)"
}

# Function to remove webhook
remove_webhook() {
    echo "Removing webhook..."
    python3 qnt/memory/enhanced_bot.py --remove-webhook
    echo ""
    echo "✅ Webhook removed. Bot will use polling mode."
}

# Function to view status
view_status() {
    echo ""
    echo "📊 Bot Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check environment variables
    ENV_FILE="$SCRIPT_DIR/.env"
    if [ -f "$ENV_FILE" ]; then
        echo "Environment file: ✅ Found"
        
        if grep -q "QNT_TELEGRAM_TOKEN" "$ENV_FILE" 2>/dev/null; then
            echo "Telegram Token: ✅ Configured"
        else
            echo "Telegram Token: ❌ Missing"
        fi
        
        if grep -q "QNT_TELEGRAM_CHAT_ID" "$ENV_FILE" 2>/dev/null; then
            echo "Chat ID: ✅ Configured"
        else
            echo "Chat ID: ❌ Missing"
        fi
        
        if grep -q "ENABLE_IMESSAGE=true" "$ENV_FILE" 2>/dev/null; then
            echo "iMessage: ✅ Enabled"
            if grep -q "IPHONE_NUMBER=" "$ENV_FILE" 2>/dev/null; then
                iphone=$(grep "IPHONE_NUMBER=" "$ENV_FILE" | cut -d'=' -f2)
                echo "iPhone Number: $iphone"
            fi
        else
            echo "iMessage: ❌ Disabled"
        fi
    else
        echo "Environment file: ❌ Not found"
    fi
    
    echo ""
    
    # Check if webhook is set
    if [ -f "$ENV_FILE" ]; then
        source "$ENV_FILE" 2>/dev/null || true
        if [ -n "$QNT_TELEGRAM_TOKEN" ]; then
            echo "Checking webhook status..."
            curl -s "https://api.telegram.org/bot$QNT_TELEGRAM_TOKEN/getWebhookInfo" | python3 -m json.tool 2>/dev/null || echo "Unable to fetch webhook info"
        fi
    fi
}

# Main loop
while true; do
    show_menu
    read -p "Enter choice [1-8]: " choice
    
    case $choice in
        1) test_bot ;;
        2) send_menu ;;
        3) configure_imessage ;;
        4) test_imessage ;;
        5) setup_webhook ;;
        6) remove_webhook ;;
        7) view_status ;;
        8) echo "Goodbye!"; exit 0 ;;
        *) echo "Invalid option. Try again." ;;
    esac
    
    echo ""
    echo "Press Enter to continue..."
    read
done
