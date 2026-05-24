"""
Telegram Webhook Server for Enhanced Bot
=========================================
Handles inline keyboard callbacks and instant message responses.
Run this as a service to receive webhook updates from Telegram.

Usage:
    python3 telegram_webhook_server.py --port 8443 --webhook-url https://your-domain.com:8443/webhook
"""

import os
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import sys
import time
import threading
import requests

# Add memory dir to path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'qnt/memory'))

from enhanced_bot import (
    TOKEN, CHAT_ID, API_URL, handle_callback_query, 
    send_telegram_message, execute_command_raw
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("telegram_webhook")


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for Telegram webhook."""
    
    def do_POST(self):
        """Handle POST requests from Telegram."""
        if self.path == '/webhook':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            if not post_data.strip():
                self.send_response(200)
                self.end_headers()
                return

            try:
                update = json.loads(post_data.decode('utf-8'))
                logger.info(f"Received update: {json.dumps(update, indent=2)[:500]}")

                # Process the update
                self.process_update(update)

                # Respond with 200 OK
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')

            except Exception as e:
                logger.error(f"Error processing update: {e}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
        elif self.path == '/ft_alert':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                # errors='replace' handles non-UTF8 bytes; strip null bytes that fool the empty check
                body = post_data.decode('utf-8', errors='replace').strip().strip('\x00')
                if not body:
                    self.send_response(200)
                    self.end_headers()
                    return
                try:
                    payload = json.loads(body)
                except (json.JSONDecodeError, ValueError) as e:
                    # Return 200 so freqtrade does not retry on bad/empty payloads
                    logger.warning(f"ft_alert received invalid JSON (ignoring): {e}")
                    self.send_response(200)
                    self.end_headers()
                    return
                # Freqtrade Webhook JSON: forward the pre-formatted message if present
                msg = payload.get('message', str(payload))
                if 'message' in payload:
                    send_telegram_message(msg, chat_id=str(CHAT_ID))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            except Exception as e:
                logger.error(f"Error processing ft_alert: {e}")
                try:
                    self.send_response(500)
                    self.end_headers()
                except Exception:
                    pass
        else:
            self.send_response(404)
            self.end_headers()
    
    def process_update(self, update: dict):
        """Process Telegram update (message or callback)."""
        
        # Handle callback query (inline keyboard button press)
        if 'callback_query' in update:
            callback = update['callback_query']
            callback_data = callback.get('data', '')
            message_id = callback['message']['message_id']
            chat_id = callback['message']['chat']['id']
            from_user = callback['from']
            
            logger.info(f"Callback from @{from_user.get('username', 'unknown')}: {callback_data}")
            
            # Verify authorized user
            if str(chat_id) != str(CHAT_ID):
                logger.warning(f"Unauthorized callback attempt from chat {chat_id}")
                return
            
            # Handle the callback
            response_text = handle_callback_query(callback_data, message_id)
            
            # Answer the callback query (removes loading state)
            self.answer_callback_query(callback['id'], response_text[:200])
            
            # Send full response as new message
            if response_text:
                send_telegram_message(response_text, chat_id=str(chat_id))
            
            # Log the action
            self.log_action("callback_executed", f"Button: {callback_data}")
        
        # Handle regular message
        elif 'message' in update:
            message = update['message']
            text = message.get('text', '').strip()
            chat_id = message['chat']['id']
            from_user = message.get('from', {})
            
            logger.info(f"Message from @{from_user.get('username', 'unknown')}: {text}")
            
            # Verify authorized user
            if str(chat_id) != str(CHAT_ID):
                logger.warning(f"Unauthorized message from chat {chat_id}")
                return
            
            # Process commands
            if text.startswith('/'):
                self.handle_command(text, chat_id)
            else:
                # Regular message - could be reply to escalation
                self.handle_reply(text, chat_id)
    
    def answer_callback_query(self, callback_query_id: str, text: str):
        """Send answer to callback query to remove loading state."""
        try:
            requests.post(f"{API_URL}/answerCallbackQuery", json={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": False
            }, timeout=5)
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
    
    def handle_command(self, text: str, chat_id: str):
        """Handle slash commands."""
        cmd_map = {
            "/start": self.send_help,
            "/help": self.send_help,
            "/menu": self.send_menu,
            "/status": lambda: execute_command_raw("qnt-bot status"),
            "/risk": lambda: execute_command_raw("qnt-risk-check"),
            "/skeptic": lambda: execute_command_raw("qnt-skeptic stats"),
            "/shadow": lambda: execute_command_raw("qnt-shadow status"),
            "/backup": lambda: execute_command_raw("qnt-backup run"),
            "/logs": lambda: execute_command_raw("tail -n 30 logs/supervisord.log"),
            "/health": lambda: execute_command_raw("python3 automation/health_check.py"),
            "/analytics": self.send_analytics
        }
        
        handler = cmd_map.get(text.split()[0].lower())
        if handler:
            try:
                result = handler()
                if isinstance(result, str):
                    send_telegram_message(result, chat_id=str(chat_id))
            except Exception as e:
                send_telegram_message(f"❌ Error: {str(e)}", chat_id=str(chat_id))
        else:
            send_telegram_message(f"❌ Unknown command: {text}\nUse /help for available commands", chat_id=str(chat_id))
    
    def send_help(self) -> str:
        """Return help message."""
        return (
            "🤖 <b>Cipher QNT Control Center</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Available Commands:</b>\n\n"
            "/menu - Show interactive control menu\n"
            "/status - System status overview\n"
            "/risk - Current risk levels\n"
            "/skeptic - Skeptic Agent stats\n"
            "/shadow - Shadow hyperopt status\n"
            "/backup - Trigger backup\n"
            "/logs - Recent system logs\n"
            "/health - Run health check\n"
            "/analytics - View analytics dashboard\n"
            "/help - Show this help message\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Tip: Use the inline menu buttons for quick access!</i>"
        )
    
    def send_menu(self):
        """Send main menu with inline keyboard."""
        from enhanced_bot import send_main_menu
        send_main_menu()
        return "Menu sent!"
    
    def send_analytics(self) -> str:
        """Send analytics summary."""
        from enhanced_bot import send_analytics_summary
        send_analytics_summary()
        return "Analytics sent!"
    
    def handle_reply(self, text: str, chat_id: str):
        """Handle non-command messages (potential replies to escalations)."""
        # Import reply handling from reply_listener
        try:
            from reply_listener import process_update
            # Create a mock update structure
            mock_update = {
                'message': {
                    'chat': {'id': chat_id},
                    'text': text
                }
            }
            process_update(mock_update)
        except Exception as e:
            logger.error(f"Error processing reply: {e}")
    
    def log_action(self, action_type: str, details: str):
        """Log action to memory."""
        try:
            from memory_manager import log_action
            log_action(action_type, details)
        except Exception as e:
            logger.error(f"Failed to log action: {e}")
    
    def log_message(self, format: str, *args):
        """Override to use our logger."""
        logger.info(format % args)


def run_polling():
    """Run long-polling to get Telegram updates (no public URL required)."""
    logger.info("Starting Telegram Polling loop...")
    offset = 0
    
    # Must delete webhook first to allow polling
    try:
        requests.post(f"{API_URL}/deleteWebhook", timeout=10)
        logger.info("Webhook deleted, safe to poll.")
    except Exception as e:
        logger.error(f"Failed to delete webhook before polling: {e}")

    while True:
        try:
            res = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40)
            if res.status_code == 200:
                data = res.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    handler = TelegramWebhookHandler(None, None, None)
                    handler.process_update(update)
            time.sleep(1)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

# Patch BaseHTTPRequestHandler init so we can instantiate it standalone for polling
def patched_init(self, request, client_address, server):
    if request is None:
        return
    super(TelegramWebhookHandler, self).__init__(request, client_address, server)

TelegramWebhookHandler.__init__ = patched_init

def run_server(port: int = 8443, cert_file: str = None, key_file: str = None):
    """Run the webhook server."""
    import requests
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, TelegramWebhookHandler)
    
    # Setup SSL if certificates provided
    if cert_file and key_file:
        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        protocol = "HTTPS"
    else:
        protocol = "HTTP"
    
    logger.info(f"Starting Telegram Webhook Server ({protocol}) on port {port}...")
    logger.info(f"Webhook endpoint: /webhook")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        httpd.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Webhook Server")
    parser.add_argument("--port", type=int, default=8443, help="Server port")
    parser.add_argument("--webhook-url", type=str, 
                        help="Public URL for webhook (e.g., https://your-domain.com:8443/webhook)")
    parser.add_argument("--polling", action="store_true",
                        help="Use long-polling instead of webhooks for inbound commands")
    parser.add_argument("--cert", type=str, help="SSL certificate file path")
    parser.add_argument("--key", type=str, help="SSL private key file path")
    parser.add_argument("--setup-only", action="store_true", 
                        help="Only setup webhook, don't run server")
    
    args = parser.parse_args()
    
    if args.polling:
        logger.info("Running in POLLING mode. Starting polling thread.")
        # Start polling in background
        threading.Thread(target=run_polling, daemon=True).start()
    elif args.webhook_url:
        # Setup webhook
        webhook_url = args.webhook_url
        if not webhook_url.endswith('/webhook'):
            webhook_url = webhook_url.rstrip('/') + '/webhook'
        
        logger.info(f"Setting up webhook: {webhook_url}")
        res = requests.post(f"{API_URL}/setWebhook", json={
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query"]
        }, timeout=10)
        
        if res.status_code == 200:
            logger.info("✅ Webhook configured successfully!")
            verify_res = requests.get(f"{API_URL}/getWebhookInfo", timeout=10)
            if verify_res.status_code == 200:
                logger.info(f"Webhook info: {json.dumps(verify_res.json(), indent=2)}")
        else:
            logger.error(f"❌ Webhook setup failed: {res.text}")
            sys.exit(1)
    else:
        logger.warning("No --webhook-url or --polling specified! Inbound commands will not work.")
    
    if not args.setup_only:
        run_server(args.port, args.cert, args.key)
