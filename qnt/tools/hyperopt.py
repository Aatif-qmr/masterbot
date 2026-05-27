"""Hyperopt tools: shadow hyperopt control on M2 via SSH."""

import os
import subprocess
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent
_M2_USER = "azmatsaif"
_M2_PATH = "/Users/azmatsaif/cipher"


def _m2_ip() -> str:
    """Resolve M2 Tailscale IP from env or tailscale CLI."""
    ip = os.getenv("M2_TAILSCALE_IP", "")
    if ip:
        return ip
    try:
        result = subprocess.run(
            ["tailscale", "ip", "azmatsaif-m2"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _ssh(command: str, timeout: int = 15) -> str:
    """Run a command on M2 via SSH and return stdout."""
    ip = _m2_ip()
    if not ip:
        return "M2 unreachable: M2_TAILSCALE_IP not set and tailscale lookup failed"
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", f"{_M2_USER}@{ip}", command],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "SSH timeout"
    except Exception as e:
        return f"SSH error: {e}"


def get_shadow_status() -> str:
    """Get shadow hyperopt resource usage and process status from M2."""
    resource_cmd = (
        f"source {_M2_PATH}/venv/bin/activate && "
        f"python {_M2_PATH}/qnt/shadow/resource_monitor.py 2>/dev/null || echo '{{}}'"
    )
    resource_out = _ssh(resource_cmd)
    process_out = _ssh("pgrep -f shadow_hyperopt.py && echo RUNNING || echo STOPPED")
    return f"Resources: {resource_out}\nProcess: {process_out}"


def get_shadow_report() -> str:
    """Get recent shadow hyperopt results (last 24h) from M2."""
    cmd = (
        f"tail -100 {_M2_PATH}/logs/shadow_hyperopt_*.log 2>/dev/null "
        f"| grep -E '(Sharpe|improvement|SKIPPED|ERROR)' | tail -20"
    )
    return _ssh(cmd)


def control_shadow(action: str, strategy: str | None = None) -> str:
    """Start, stop, or promote shadow hyperopt on M2."""
    if action == "start":
        cmd = (
            f"cd {_M2_PATH} && source venv/bin/activate && "
            f"nohup python3 qnt/shadow/shadow_hyperopt.py "
            f">> logs/shadow_hyperopt_main.log 2>&1 & "
            f"echo $! > logs/shadow_hyperopt.pid && "
            f"echo \"Started PID $(cat logs/shadow_hyperopt.pid)\""
        )
        return _ssh(cmd)
    elif action == "stop":
        cmd = (
            f"if [ -f {_M2_PATH}/logs/shadow_hyperopt.pid ]; then "
            f"kill $(cat {_M2_PATH}/logs/shadow_hyperopt.pid) 2>/dev/null && "
            f"rm {_M2_PATH}/logs/shadow_hyperopt.pid && echo Stopped; "
            f"else pkill -f shadow_hyperopt.py && echo 'Stopped by name' || echo 'Not running'; fi"
        )
        return _ssh(cmd)
    elif action == "promote":
        if not strategy:
            return "Error: strategy name required for promote"
        cmd = (
            f"echo \"[$(date)] PROMOTE_REQUEST: {strategy}\" "
            f">> {_M2_PATH}/logs/shadow_promotions.log"
        )
        _ssh(cmd)
        return f"Promotion request for {strategy} logged. Manual parameter merge required."
    else:
        return f"Unknown action: {action}. Use: status, start, stop, promote"
