import psutil
import json
import time
import subprocess
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Path setup for M2 environment
HOME = Path.home()
BASE_DIR = HOME / 'masterbot'
MONITOR_FILE = BASE_DIR / 'qnt/shadow/resource_state.json'
LOG_FILE = BASE_DIR / 'logs/resource_alerts.log'

# RAM-tier pressure thresholds — tighter on 8GB, relaxed on 16GB
_PRESSURE_THRESHOLDS = {
    8:  {"warning": 60, "critical": 75},
    16: {"warning": 70, "critical": 85},
    32: {"warning": 75, "critical": 88},
}


def get_ram_tier() -> int:
    """Return installed RAM tier in GB (8, 16, or 32)."""
    raw = psutil.virtual_memory().total / (1024 ** 3)
    if raw < 12:
        return 8
    if raw < 24:
        return 16
    return 32


def _pressure_levels() -> dict:
    return _PRESSURE_THRESHOLDS.get(get_ram_tier(), _PRESSURE_THRESHOLDS[8])


def get_resource_snapshot():
    """Captures a snapshot of current system resources."""
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    ram_tier = get_ram_tier()

    # RAM pressure logic — thresholds depend on physical RAM installed
    percent_used = ram.percent
    levels = _pressure_levels()
    if percent_used < levels["warning"]:
        pressure = "normal"
    elif percent_used < levels["critical"]:
        pressure = "warning"
    else:
        pressure = "critical"
        
    # CPU throttling detection
    # Simple logic: if usage > 90% for sustained period (handled in monitor loop)
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Top processes by RAM - extremely defensive
    top_procs = []
    proc_list = []
    for p in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
        try:
            info = p.info
            if info.get('memory_info') and hasattr(info['memory_info'], 'rss'):
                proc_list.append({
                    "name": info['name'],
                    "ram_mb": info['memory_info'].rss / (1024 * 1024),
                    "cpu_percent": info['cpu_percent'] or 0.0
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort and take top 5
    top_procs = sorted(proc_list, key=lambda x: x['ram_mb'], reverse=True)[:5]

    # Check for running bot components
    hyperopt_running = False
    freqai_running = False
    sentiment_running = False
    
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            name = p.info['name'].lower()
            cmdline = " ".join(p.info['cmdline'] or [])
            if "freqtrade" in name and "hyperopt" in cmdline:
                hyperopt_running = True
            if "freqai" in name or "freqai" in cmdline:
                freqai_running = True
            if "sentiment" in name or "sentiment" in cmdline:
                sentiment_running = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ram": {
            "total_gb": round(ram.total / (1024**3), 2),
            "used_gb": round(ram.used / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "percent_used": percent_used,
            "pressure": pressure,
            "tier_gb": ram_tier,
            "thresholds": levels,
        },
        "cpu": {
            "percent_used": cpu_percent,
            "core_count": psutil.cpu_count(),
            "throttling_detected": False # Updated in continuous loop
        },
        "swap": {
            "used_gb": round(swap.used / (1024**3), 2),
            "percent_used": swap.percent
        },
        "top_processes": top_procs,
        "hyperopt_running": hyperopt_running,
        "freqai_running": freqai_running,
        "sentiment_running": sentiment_running
    }

def monitor_continuously(interval=30):
    """Main monitoring loop."""
    print(f"Resource Monitor started. Interval: {interval}s")
    os.makedirs(MONITOR_FILE.parent, exist_ok=True)
    os.makedirs(LOG_FILE.parent, exist_ok=True)
    
    sustained_high_cpu_count = 0
    
    while True:
        try:
            snapshot = get_resource_snapshot()
            
            # Refined throttling detection
            if snapshot['cpu']['percent_used'] > 90:
                sustained_high_cpu_count += 1
            else:
                sustained_high_cpu_count = 0
            
            if sustained_high_cpu_count >= (60 // interval):
                snapshot['cpu']['throttling_detected'] = True
            
            # Persistent state storage
            history = []
            if MONITOR_FILE.exists():
                try:
                    with open(MONITOR_FILE, 'r') as f:
                        history = json.load(f)
                except: pass
            
            history.append(snapshot)
            # Keep only last 24h of data (approx 2880 snapshots at 30s)
            max_snapshots = 86400 // interval
            history = history[-max_snapshots:]
            
            with open(MONITOR_FILE, 'w') as f:
                json.dump(history, f, indent=2)
                
            # Alerts
            if snapshot['ram']['pressure'] == "critical":
                msg = f"[{snapshot['timestamp']}] ⚠️ M2 RAM CRITICAL: {snapshot['ram']['percent_used']}% used. Top process: {snapshot['top_processes'][0]['name']}"
                with open(LOG_FILE, 'a') as f:
                    f.write(msg + "\n")
                
                # SSH to M1 for notification
                # M2 environment likely has M1_IP or hostname defined in /etc/hosts or Tailscale
                # Using placeholder for actual notification command
                subprocess.run(['ssh', 'aatifquamre@100.90.68.42', f'source ~/.zshrc && echo "{msg}" | qnt-notify'], stderr=subprocess.DEVNULL)
                
            time.sleep(interval)
        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(interval)

def get_daily_report():
    """Aggregates last 24h of data into a report."""
    if not MONITOR_FILE.exists():
        return "No resource data found."
        
    try:
        with open(MONITOR_FILE, 'r') as f:
            history = json.load(f)
            
        if not history: return "History empty."
        
        ram_vals = [s['ram']['percent_used'] for s in history]
        cpu_vals = [s['cpu']['percent_used'] for s in history]
        throttling_events = sum(1 for s in history if s['cpu']['throttling_detected'])
        
        peak_ram = max(ram_vals)
        peak_time = next(s['timestamp'] for s in history if s['ram']['percent_used'] == peak_ram)
        
        avg_ram = sum(ram_vals) / len(ram_vals)
        avg_cpu = sum(cpu_vals) / len(cpu_vals)
        
        # Option A vs B recommendation — uses tier-aware critical threshold
        tier = get_ram_tier()
        levels = _pressure_levels()
        critical_pct = levels["critical"]

        recommendation = "Option A (Sustainable Continuous)"
        if peak_ram > critical_pct or throttling_events > 5:
            recommendation = "Option B (Switch to Scheduled Optimization)"

        report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
M2 RESOURCE DAILY REPORT  [{tier}GB node]
Generated: {datetime.now(timezone.utc).isoformat()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RAM TIER:    {tier}GB  (warn>{levels['warning']}% / crit>{critical_pct}%)
AVG RAM USAGE: {avg_ram:.1f}%
PEAK RAM USAGE: {peak_ram:.1f}% at {peak_time}
AVG CPU LOAD: {avg_cpu:.1f}%
THROTTLING EVENTS: {throttling_events}

RECOMMENDATION: {recommendation}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return report
    except Exception as e:
        return f"Report error: {e}"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        print(get_daily_report())
    else:
        monitor_continuously()
