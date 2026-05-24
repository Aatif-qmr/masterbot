import os
import subprocess
import time
import glob
from pathlib import Path

# --- CONFIGURATION ---
LOG_DIR = "/Users/aatifquamre/cipher/logs"
CLAUDE_BIN = "/Users/aatifquamre/.local/bin/claude"
WORKSPACE = "/Users/aatifquamre/cipher"
ERROR_KEYWORDS = ["Traceback", "ERROR", "CRITICAL", "NameError", "ValueError", "TypeError"]

# Patterns that indicate expected infrastructure failures — not fixable by code changes.
# Logs whose entire error content matches only these patterns are skipped.
INFRA_NOISE_PATTERNS = [
    "ConnectionRefusedError",       # NATS/remote server offline — handled by retry logic
    "nats: no servers available",   # NATS all-server failure — handled by retry loop
    "nats: encountered error",      # NATS library internal log — suppressed at source
    "_ON_EMIT_RECURSION_COUNT_KEY", # opentelemetry version mismatch — already fixed
    "import chromadb",              # old vault.py chromadb import — already migrated
]


def _is_infra_noise_only(content: str) -> bool:
    """Return True if the log content contains only known infrastructure noise, not code bugs."""
    error_lines = [
        l for l in content.splitlines()
        if any(k in l for k in ERROR_KEYWORDS)
        and "Traceback (most recent call last)" not in l
    ]
    if not error_lines:
        return True
    return all(any(p in l for p in INFRA_NOISE_PATTERNS) for l in error_lines)

def get_error_context():
    """Scans all log files and returns a summary of recent errors."""
    error_summary = []
    
    # Scan all log files
    log_files = glob.glob(os.path.join(LOG_DIR, "*.log*"))
    
    for log_path in log_files:
        if os.path.basename(log_path) == "self_healer_run.log":
            continue
        try:
            with open(log_path, 'r') as f:
                # Read last 50 lines to catch recent issues
                lines = f.readlines()[-50:]
                content = "".join(lines)
                
                # Check for keywords, skip files that only contain known infra noise
                if any(keyword in content for keyword in ERROR_KEYWORDS):
                    if not _is_infra_noise_only(content):
                        error_summary.append(f"--- FILE: {os.path.basename(log_path)} ---\n{content}")
        except Exception:
            continue
            
    return "\n\n".join(error_summary)

def run_self_healing():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting self-healing scan...")
    
    context = get_error_context()
    
    if not context:
        print("✅ No errors found in logs. System healthy.")
        return

    print("⚠️ Errors detected! Invoking QNT CLI to fix...")
    
    # Construct the prompt for QNT CLI
    healing_prompt = f"""
I am the Cipher Self-Healer. I have detected the following errors in the system logs.
Your task:
1. Analyze the errors below.
2. Identify the source files causing these issues.
3. Apply targeted, surgical fixes to resolve them.
4. Verify the fix by checking if the project still compiles or by running a relevant check.

ERRORS FROM LOGS:
{context}

Proceed in YOLO mode to apply the fixes immediately.
"""

    try:
        cmd = [
            CLAUDE_BIN,
            "-p", healing_prompt,
            "--dangerously-skip-permissions",
        ]
        
        # Run and wait for it to finish
        result = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        
        # Log the healer's output
        with open(os.path.join(LOG_DIR, "self_healer_run.log"), "a") as f:
            f.write(f"\n\n=== RUN AT {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\nERRORS:\n" + result.stderr)
                
        print("✅ Healing session complete. Results logged to logs/self_healer_run.log")
        
    except Exception as e:
        print(f"❌ Failed to invoke QNT CLI: {e}")

if __name__ == "__main__":
    run_self_healing()
