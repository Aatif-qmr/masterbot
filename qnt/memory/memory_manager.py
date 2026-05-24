import os
import json
import time
import socket
import fcntl
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURATION ---
BASE_DIR = Path("/Users/aatifquamre/cipher")
M1_PATH = Path("/Users/aatifquamre/cipher")
M2_PATH = Path("/Users/azmatsaif/cipher")
MEMORY_DIR = "qnt/memory"
MEMORY_FILENAME = "qnt_memory.json"
MAX_ACTION_LOG_ENTRIES = 1000

load_dotenv(BASE_DIR / ".env")

M2_IP = os.getenv("M2_TAILSCALE_IP", "100.74.110.36")
M1_USER = "aatifquamre"
M2_USER = "azmatsaif"

def get_device_identity():
    """Detect if running on M1 or M2 and return identity dict."""
    username = os.getenv("USER") or os.getenv("USERNAME")
    hostname = socket.gethostname()
    cwd = os.getcwd()
    
    if "azmatsaif" in cwd or username == M2_USER:
        return {
            "device": "M2",
            "username": M2_USER,
            "hostname": hostname,
            "role": "intelligence",
            "cipher_path": M2_PATH
        }
    else:
        return {
            "device": "M1",
            "username": M1_USER,
            "hostname": hostname,
            "role": "execution",
            "cipher_path": M1_PATH
        }

IDENTITY = get_device_identity()
MEMORY_FILE = IDENTITY["cipher_path"] / MEMORY_DIR / MEMORY_FILENAME

def create_initial_memory():
    return {
        "version": "1.0",
        "created": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "last_updated": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "last_sync_m2": None,
        "action_log": [],
        "device_state": {
            "M1": {"last_seen": None, "last_action": None, "hostname": None},
            "M2": {"last_seen": None, "last_action": None, "hostname": None}
        },
        "decisions": [],
        "site_maps": {},
        "calendar_cache": {"last_fetched": None, "events": []},
        "strategy_history": [],
        "escalation_log": [],
        "autonomous_actions_today": 0,
        "autonomous_actions_total": 0
    }

def load_memory():
    """Read memory file with file locking."""
    if not MEMORY_FILE.exists():
        return create_initial_memory()
    
    try:
        with open(MEMORY_FILE, 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
            return data
    except (json.JSONDecodeError, IOError):
        return create_initial_memory()

def save_memory(data):
    """Save memory file atomically with file locking."""
    # Ensure directory exists
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    data["last_updated"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    temp_file = MEMORY_FILE.with_name(f"{MEMORY_FILE.name}.tmp.{os.getpid()}")
    
    with open(temp_file, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)
        
    os.rename(temp_file, MEMORY_FILE)
    os.chmod(MEMORY_FILE, 0o600)

def log_action(action, result, device=None, escalated=False, notify=False):
    """Append entry to action log and update state counters."""
    if device is None:
        device = IDENTITY["device"]
        
    if device == "M2" and IDENTITY["device"] == "M2":
        # Remote write from M2 to M1
        return write_from_m2({"action": "log_action", "args": [action, result, device, escalated, notify]})

    data = load_memory()
    
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "device": device,
        "action": action,
        "result": result,
        "escalated": escalated,
        "notified": notify
    }
    
    data["action_log"].append(entry)
    
    # Trim log
    if len(data["action_log"]) > MAX_ACTION_LOG_ENTRIES:
        data["action_log"] = data["action_log"][-MAX_ACTION_LOG_ENTRIES:]
        
    # Update state
    data["device_state"][device]["last_seen"] = entry["timestamp"]
    data["device_state"][device]["last_action"] = action
    data["device_state"][device]["hostname"] = IDENTITY["hostname"]
    
    data["autonomous_actions_total"] += 1
    # Simple check for 'today' (UTC)
    data["autonomous_actions_today"] += 1 
    
    save_memory(data)

def log_decision(situation, options, chosen, reasoning, device=None):
    """Append entry to decisions log."""
    if device is None:
        device = IDENTITY["device"]
        
    if device == "M2" and IDENTITY["device"] == "M2":
        return write_from_m2({"action": "log_decision", "args": [situation, options, chosen, reasoning, device]})

    data = load_memory()
    
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "device": device,
        "situation": situation,
        "options_presented": options,
        "chosen": chosen,
        "reasoning": reasoning,
        "outcome": None
    }
    
    data["decisions"].append(entry)
    save_memory(data)

def update_decision_outcome(timestamp, outcome):
    """Find decision by timestamp and update outcome."""
    if IDENTITY["device"] == "M2":
        return write_from_m2({"action": "update_decision_outcome", "args": [timestamp, outcome]})

    data = load_memory()
    for d in data["decisions"]:
        if d["timestamp"] == timestamp:
            d["outcome"] = outcome
            break
    save_memory(data)

def get_recent_actions(hours=24, device=None):
    """Filter actions from last N hours."""
    data = load_memory()
    now = datetime.now(timezone.utc)
    threshold = now.timestamp() - (hours * 3600)
    
    recent = []
    for entry in data["action_log"]:
        # Naive parse of ISO format
        try:
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).timestamp()
            if ts >= threshold:
                if device is None or entry["device"] == device:
                    recent.append(entry)
        except ValueError:
            continue
            
    return recent

def check_connectivity():
    """Test internet connectivity via DNS port."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def write_from_m2(data_update):
    """Initiate remote write from M2 to M1 via SSH."""
    if IDENTITY["device"] != "M2":
        return False
        
    payload = json.dumps(data_update)
    # The remote command on M1 will be memory_manager.py's CLI interface
    cmd = [
        "ssh", "-o", "ConnectTimeout=10",
        f"{M1_USER}@{os.getenv('M1_IP', '100.90.68.42')}",
        f"python3 {M1_PATH}/qnt/memory/memory_manager.py --apply-update"
    ]
    
    try:
        proc = subprocess.run(cmd, input=payload, text=True, capture_output=True)
        return proc.returncode == 0
    except Exception as e:
        print(f"Remote write failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    if "--apply-update" in sys.argv:
        # Receiver logic on M1
        try:
            payload = json.load(sys.stdin)
            action = payload.get("action")
            args = payload.get("args", [])
            
            if action == "log_action":
                log_action(*args)
            elif action == "log_decision":
                log_decision(*args)
            elif action == "update_decision_outcome":
                update_decision_outcome(*args)
            sys.exit(0)
        except Exception as e:
            print(f"Error applying update: {e}", file=sys.stderr)
            sys.exit(1)
