import sys
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# Configuration
LOG_DOC_ID = '1N1Mk2z4WYtWAd9JU1VK52HeLu3IqucBHA2_ZBHvZasQ'
_HOOK_DIR = Path(__file__).resolve().parent
_LOG_FILE = _HOOK_DIR.parent.parent / 'logs' / 'audit_errors.log'
_QNT_TIMEOUT = 30  # seconds; prevents SIGKILL from runaway subprocess

def log_change(author, action, rationale):
    # Use Local Time for the user's convenience (Asia/Calcutta)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not shutil.which('qnt'):
        return  # qnt CLI not available; skip silently rather than logging noise

    # Format as a clean Markdown-style block for Google Docs
    block = f"""
---
### {date_str} | {author}
**Action:** {action}
**Rationale:** {rationale}
"""

    # We use a specific instruction to the assistant to ensure it applies formatting
    prompt = f"Append this entry to the Google Doc '{LOG_DOC_ID}'. Format the first line as a Heading and ensure the Action/Rationale labels are Bold: {block}"

    try:
        subprocess.run(
            ['qnt', '-p', prompt],
            check=True,
            capture_output=True,
            timeout=_QNT_TIMEOUT,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass  # qnt failed or timed out; audit logging is best-effort
    except Exception as e:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_FILE, 'a') as f:
            f.write(f"{date_str} - Failed to log: {str(e)}\n")

if __name__ == "__main__":
    if len(sys.argv) > 3:
        log_change(sys.argv[1], sys.argv[2], sys.argv[3])
