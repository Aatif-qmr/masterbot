import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# Load env from root
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")


class LarkNotifier:
    """
    Wrapper for lark-cli (npm package @larksuite/cli)
    Allows sending messages and interacting with Lark Base from Python.
    """

    def __init__(self, chat_id=None):
        self.chat_id = chat_id or os.getenv("LARK_CHAT_ID")
        self.app_id = os.getenv("LARK_APP_ID")
        self.app_secret = os.getenv("LARK_APP_SECRET")

    def send_text(self, text, chat_id=None):
        """Sends a simple text message via lark-cli"""
        cid = chat_id or self.chat_id
        if not cid:
            print("Error: No Lark Chat ID provided.")
            return False

        cmd = ["lark-cli", "im", "messages-send", "--chat-id", cid, "--text", text]

        try:
            # Use shell=True if lark-cli is in path but not directly executable in some envs
            # Or use npx if not installed globally
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return True
            else:
                print(f"Lark CLI Error: {result.stderr}")
                return False
        except FileNotFoundError:
            print("Error: lark-cli not found. Install with: npm install -g @larksuite/cli")
            return False

    def send_post(self, title, content_list, chat_id=None):
        """
        Sends a rich text (Post) message.
        content_list: list of strings or list of lists (for multi-line)
        """
        cid = chat_id or self.chat_id
        # Note: lark-cli post command syntax might vary,
        # but usually it supports complex JSON payloads for messages-send

        # Simplified: Construct an interactive card or post payload
        # For now, let's keep it simple with text but formatted
        formatted_text = f"**{title}**\n\n" + "\n".join(content_list)
        return self.send_text(formatted_text, cid)

    def update_base_record(self, app_token, table_id, fields):
        """Updates or adds a record to a Lark Base table"""
        cmd = [
            "lark-cli",
            "base",
            "records-create",
            "--app-token",
            app_token,
            "--table-id",
            table_id,
            "--fields",
            json.dumps(fields),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"Lark Base Update Error: {e}")
            return False


if __name__ == "__main__":
    # Test
    notifier = LarkNotifier()
    notifier.send_text("🚀 Cipher Lark Integration Test: Active")
