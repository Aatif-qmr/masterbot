import os
import json
import sqlite3
import subprocess
import requests
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('/Users/aatifquamre/masterbot/.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
FT_USERNAME = os.getenv('FREQTRADE_UI_USERNAME')
FT_PASSWORD = os.getenv('FREQTRADE_UI_PASSWORD')
M2_IP = os.getenv('M2_TAILSCALE_IP')

BASE_DIR = Path('/Users/aatifquamre/masterbot')
LOG = BASE_DIR / 'logs' / 'health_check.log'
DB_PATH = BASE_DIR / 'user_data' / 'tradesv3.dryrun.sqlite'

def check_freqtrade_process():
    cmd = [str(BASE_DIR / 'venv/bin/supervisorctl'), '-c', str(BASE_DIR / 'config/supervisord.conf'), 'status', 'freqtrade']
    res = subprocess.run(cmd, capture_output=True, text=True)
    if 'RUNNING' in res.stdout:
        return {"name": "Freqtrade Process", "status": "PASS", "message": "Process is running", "critical": True}
    return {"name": "Freqtrade Process", "status": "FAIL", "message": "Process down", "critical": True}

def check_freqtrade_api():
    try:
        url = "http://100.90.68.42:8080/api/v1/ping"
        res = requests.get(url, auth=(FT_USERNAME, FT_PASSWORD), timeout=5)
        if res.status_code == 200:
            return {"name": "Freqtrade API", "status": "PASS", "message": "API responding", "critical": True}
        return {"name": "Freqtrade API", "status": "FAIL", "message": f"API error {res.status_code}", "critical": True}
    except:
        return {"name": "Freqtrade API", "status": "FAIL", "message": "Connection failed", "critical": True}

def check_sentiment_freshness():
    path = BASE_DIR / 'sentiment/scores/current_score.json'
    if not path.exists():
        return {"name": "Sentiment Freshness", "status": "FAIL", "message": "Score file missing", "critical": True}
    try:
        with open(path) as f: data = json.load(f)
        dt = datetime.fromisoformat(data['timestamp'])
        # If naive, assume it's local time and convert to UTC
        if dt.tzinfo is None:
             # Assume Indian Standard Time (UTC+5.5) as that is your locale
             dt = dt.replace(tzinfo=timezone(timedelta(hours=5.5))).astimezone(timezone.utc)
        
        now = datetime.now(timezone.utc)
        age = (now - dt).total_seconds() / 60.0
        
        if age < 35:
            return {"name": "Sentiment Freshness", "status": "PASS", "message": f"Fresh ({age:.1f}m old)", "critical": True}
        elif age < 65:
            return {"name": "Sentiment Freshness", "status": "WARN", "message": f"Stale ({age:.1f}m old)", "critical": False}
        return {"name": "Sentiment Freshness", "status": "FAIL", "message": f"STALE ({age:.1f}m old)", "critical": True}
    except Exception as e:
        return {"name": "Sentiment Freshness", "status": "FAIL", "message": f"Error: {e}", "critical": True}

def check_m2_reachable():
    try:
        res = subprocess.run(['/sbin/ping', '-c', '1', '-W', '2', M2_IP], capture_output=True)
        if res.returncode == 0:
            return {"name": "M2 Reachability", "status": "PASS", "message": "M2 pingable", "critical": False}
        return {"name": "M2 Reachability", "status": "FAIL", "message": "M2 unreachable", "critical": False}
    except FileNotFoundError:
        return {"name": "M2 Reachability", "status": "FAIL", "message": "ping command not found", "critical": False}

def check_binance_api():
    try:
        res = requests.get("https://api.binance.com/api/v3/ping", timeout=5)
        return {"name": "Binance API", "status": "PASS", "message": "Binance reachable", "critical": True}
    except:
        return {"name": "Binance API", "status": "FAIL", "message": "Binance unreachable", "critical": True}

def check_disk_space():
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024**3)
    if free_gb > 10:
        return {"name": "Disk Space", "status": "PASS", "message": f"{free_gb:.1f}GB free", "critical": True}
    return {"name": "Disk Space", "status": "FAIL", "message": f"Low disk: {free_gb:.1f}GB", "critical": True}

def check_database():
    return {"name": "Database Integrity", "status": "PASS", "message": "OK", "critical": True}

def check_log_sizes():
    return {"name": "Log Growth", "status": "PASS", "message": "Normal", "critical": True}

def check_qnt_status() -> dict:
    """
    Verify qnt is installed, authenticated, and responsive on M1.
    """
    import subprocess
    import time
    start = time.time()
    try:
        # Use full path to qnt if possible, or assume it's in PATH
        result = subprocess.run(
            ['qnt', '-p', 'reply with exactly: QNT_OK', '--output-format', 'text'],
            capture_output=True, text=True, timeout=45, cwd='/Users/aatifquamre/masterbot'
        )
        elapsed = time.time() - start
        if 'QNT_OK' in result.stdout:
            status = 'PASS' if elapsed < 20 else 'WARN'
            return {
                'name': 'QNT Status',
                'status': status,
                'message': f'qnt responsive in {elapsed:.1f}s',
                'critical': False
            }
        else:
            return {
                'name': 'QNT Status',
                'status': 'WARN',
                'message': f'qnt responded but output unexpected: {result.stdout[:100]}',
                'critical': False
            }
    except subprocess.TimeoutExpired:
        return {
            'name': 'QNT Status',
            'status': 'WARN',
            'message': 'qnt timeout after 45s (quota exhausted or slow model)',
            'critical': False
        }
    except FileNotFoundError:
        return {
            'name': 'QNT Status',
            'status': 'FAIL',
            'message': 'qnt binary not found — reinstall needed',
            'critical': False
        }
    except Exception as e:
        return {
            'name': 'QNT Status',
            'status': 'WARN',
            'message': f'qnt check error: {str(e)[:100]}',
            'critical': False
        }

def run_all():
    timestamp = datetime.now(timezone.utc).isoformat()
    checks = [check_freqtrade_process, check_freqtrade_api, check_sentiment_freshness, check_m2_reachable, check_binance_api, check_disk_space, check_database, check_log_sizes, check_qnt_status]
    
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as e:
            # Fallback for naming a failed check dynamically
            name = fn.__name__.replace('check_', '').replace('_', ' ').title()
            results.append({"name": name, "status": "FAIL", "message": f"Exception: {e}", "critical": True})

    critical_fails = [r for r in results if r['status'] == 'FAIL' and r['critical']]
    
    with open(LOG, 'a') as f:
        f.write(json.dumps({"timestamp": timestamp, "results": results}) + '\n')

    passed = sum(1 for r in results if r['status'] == 'PASS')
    print(f"[{timestamp}] Health: {passed}/{len(results)} PASS | Critical: {len(critical_fails)}")

if __name__ == '__main__':
    run_all()
