import glob
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

# --- CONFIGURATION ---
_BASE = Path(__file__).resolve().parent.parent
LOG_DIR = str(_BASE / "logs")
WORKSPACE = str(_BASE)
ERROR_KEYWORDS = ["Traceback", "ERROR", "CRITICAL", "NameError", "ValueError", "TypeError"]

# Patterns that indicate expected infrastructure failures — not fixable by code changes.
# Logs whose entire error content matches only these patterns are skipped.
INFRA_NOISE_PATTERNS = [
    "ConnectionRefusedError",  # NATS/remote server offline — handled by retry logic
    "nats: no servers available",  # NATS all-server failure — handled by retry loop
    "nats: encountered error",  # NATS library internal log — suppressed at source
    "_ON_EMIT_RECURSION_COUNT_KEY",  # opentelemetry version mismatch — already fixed
    "import chromadb",  # old vault.py chromadb import — already migrated
]


def _is_infra_noise_only(content: str) -> bool:
    """Return True if the log content contains only known infrastructure noise, not code bugs."""
    error_lines = [
        line
        for line in content.splitlines()
        if any(k in line for k in ERROR_KEYWORDS)
        and "Traceback (most recent call last)" not in line
    ]
    if not error_lines:
        return True
    return all(any(p in line for p in INFRA_NOISE_PATTERNS) for line in error_lines)


def get_error_context():
    """Scans all log files and returns a summary of recent errors."""
    error_summary = []

    # Scan all log files
    log_files = glob.glob(os.path.join(LOG_DIR, "*.log*"))

    for log_path in log_files:
        if os.path.basename(log_path) == "self_healer_run.log":
            continue
        try:
            with open(log_path) as f:
                # Read last 50 lines to catch recent issues
                lines = f.readlines()[-50:]
                content = "".join(lines)

                # Check for keywords, skip files that only contain known infra noise
                if any(keyword in content for keyword in ERROR_KEYWORDS):
                    if not _is_infra_noise_only(content):
                        error_summary.append(
                            f"--- FILE: {os.path.basename(log_path)} ---\n{content}"
                        )
        except Exception:
            continue

    return "\n\n".join(error_summary)


def _send_telegram_alert(message: str) -> None:
    token = os.environ.get("QNT_TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("QNT_TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        payload = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        ).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=payload
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_self_healing():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting self-healing scan...")

    context = get_error_context()

    if not context:
        print("No errors found in logs. System healthy.")
        return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Errors detected at {timestamp} — writing findings report.")

    findings = {
        "scanned_at": timestamp,
        "error_context": context,
        "action_required": "Manual review needed. No automatic fixes applied.",
    }

    findings_path = os.path.join(LOG_DIR, "self_healer_findings.json")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(findings_path, "w") as f:
        json.dump(findings, f, indent=2)

    print(f"Findings written to {findings_path}")

    # Truncate context for Telegram (4096 char limit)
    preview = context[:800] + ("..." if len(context) > 800 else "")
    alert = (
        f"<b>[Cipher Self-Healer]</b> Errors detected at {timestamp}\n\n"
        f"<pre>{preview}</pre>\n\n"
        f"Review: <code>logs/self_healer_findings.json</code>"
    )
    _send_telegram_alert(alert)


if __name__ == "__main__":
    run_self_healing()
