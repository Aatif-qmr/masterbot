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

def check_freqtrade_processes():
    cmd = [str(BASE_DIR / 'venv/bin/supervisorctl'), '-c', str(BASE_DIR / 'config/supervisord.conf'), 'status']
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    programs = [
        'freqtrade_daily',
        'freqtrade_mean_reversion',
        'freqtrade_scalp',
        'freqtrade_swing',
        'freqtrade_trend_follow'
    ]
    
    status_map = {}
    all_running = True
    for prog in programs:
        is_running = any(prog in line and 'RUNNING' in line for line in res.stdout.split('\n'))
        status_map[prog] = 'UP' if is_running else 'DOWN'
        if not is_running:
            all_running = False
            
    message = " | ".join([f"{k[10:] if k.startswith('freqtrade_') else k}: {v}" for k, v in status_map.items()])
    
    if all_running:
        return {"name": "Freqtrade Processes", "status": "PASS", "message": "All 5 instances running", "critical": True}
    return {"name": "Freqtrade Processes", "status": "FAIL", "message": message, "critical": True}

def check_freqtrade_apis():
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    ports = [8080, 8081, 8082, 8083, 8084]
    results = {}
    all_ok = True
    
    for port in ports:
        try:
            url = f"http://100.90.68.42:{port}/api/v1/ping"
            res = requests.get(url, auth=(user, pwd), timeout=3)
            if res.status_code == 200:
                results[port] = "OK"
            else:
                results[port] = f"ERR:{res.status_code}"
                all_ok = False
        except Exception as e:
            results[port] = "FAIL"
            all_ok = False
            
    message = " | ".join([f"{p}: {v}" for p, v in results.items()])
    if all_ok:
        return {"name": "Freqtrade APIs", "status": "PASS", "message": "All 5 APIs responding", "critical": True}
    return {"name": "Freqtrade APIs", "status": "FAIL", "message": message, "critical": True}

def check_sentiment_freshness():
    path = BASE_DIR / 'sentiment/scores/current_score.json'
    if not path.exists():
        return {"name": "Sentiment Freshness", "status": "FAIL", "message": "Score file missing", "critical": True}
    try:
        with open(path) as f: data = json.load(f)
        dt = datetime.fromisoformat(data['timestamp'])
        if dt.tzinfo is None:
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
            return {"name": "M2 Node Reachable", "status": "PASS", "message": f"IP {M2_IP} responding", "critical": True}
        return {"name": "M2 Node Reachable", "status": "FAIL", "message": f"IP {M2_IP} unreachable", "critical": True}
    except Exception as e:
        return {"name": "M2 Node Reachable", "status": "FAIL", "message": f"Ping error: {e}", "critical": True}

def check_binance_api():
    try:
        # Mock test or simple ping to binance
        res = requests.get("https://api.binance.com/api/v3/ping", timeout=5)
        if res.status_code == 200:
            return {"name": "Binance Connectivity", "status": "PASS", "message": "API responding", "critical": True}
        return {"name": "Binance Connectivity", "status": "FAIL", "message": f"HTTP {res.status_code}", "critical": True}
    except Exception as e:
        return {"name": "Binance Connectivity", "status": "FAIL", "message": f"Connection error: {e}", "critical": True}

def check_disk_space():
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024**3)
    if free_gb > 5:
        return {"name": "Disk Space", "status": "PASS", "message": f"{free_gb:.1f} GB free", "critical": True}
    return {"name": "Disk Space", "status": "WARN", "message": f"Low space: {free_gb:.1f} GB", "critical": False}

def check_database():
    if not os.path.exists(DB_PATH):
        return {"name": "Database Access", "status": "FAIL", "message": "DB file missing", "critical": True}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        return {"name": "Database Access", "status": "PASS", "message": "SQLite OK", "critical": True}
    except Exception as e:
        return {"name": "Database Access", "status": "FAIL", "message": f"DB Error: {e}", "critical": True}

def check_log_sizes():
    log_dir = BASE_DIR / 'logs'
    total_size = sum(f.stat().st_size for f in log_dir.glob('*.log')) / (1024**2)
    if total_size < 500:
        return {"name": "Log Sizes", "status": "PASS", "message": f"{total_size:.1f} MB total", "critical": False}
    return {"name": "Log Sizes", "status": "WARN", "message": f"Logs large: {total_size:.1f} MB", "critical": False}

def check_qnt_status():
    try:
        # Detect qnt binary
        qnt_bin = shutil.which('qnt') or '/usr/local/bin/qnt'
        result = subprocess.run([qnt_bin, '/model_info'], capture_output=True, text=True, timeout=45)
        if result.returncode == 0:
            return {
                'name': 'QNT Status',
                'status': 'PASS',
                'message': 'Intelligence CLI active',
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

def check_nats_connection() -> dict:
    """
    Verify NATS connection M1 -> M2.
    """
    import subprocess
    try:
        result = subprocess.run(
            ['/Users/aatifquamre/masterbot/venv/bin/python', '-c',
             'import asyncio,nats,os;'
             'from dotenv import load_dotenv;'
             'load_dotenv("/Users/aatifquamre/masterbot/.env");'
             'asyncio.run(nats.connect(os.getenv("NATS_URL")));'
             'print("NATS_OK")'],
            capture_output=True, text=True,
            timeout=10
        )
        if 'NATS_OK' in result.stdout:
            return {
                'name': 'NATS Connection',
                'status': 'PASS',
                'message': 'NATS JetStream connected',
                'critical': True
            }
        else:
            return {
                'name': 'NATS Connection',
                'status': 'FAIL',
                'message': 'NATS unreachable — using SCP fallback',
                'critical': False
            }
    except Exception as e:
        return {
            'name': 'NATS Connection',
            'status': 'WARN',
            'message': f'NATS check error: {e}',
            'critical': False
        }

def run_all():
    timestamp = datetime.now(timezone.utc).isoformat()
    checks = [
        check_freqtrade_processes, 
        check_freqtrade_apis, 
        check_sentiment_freshness, 
        check_m2_reachable, 
        check_binance_api, 
        check_disk_space, 
        check_database, 
        check_log_sizes, 
        check_qnt_status,
        check_nats_connection
    ]
    
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as e:
            name = fn.__name__.replace('check_', '').replace('_', ' ').title()
            results.append({"name": name, "status": "FAIL", "message": f"Exception: {e}", "critical": True})

    critical_fails = [r for r in results if r['status'] == 'FAIL' and r['critical']]
    
    with open(LOG, 'a') as f:
        f.write(json.dumps({"timestamp": timestamp, "results": results}) + '\n')

    passed = sum(1 for r in results if r['status'] == 'PASS')
    print(f"[{timestamp}] Health: {passed}/{len(results)} PASS | Critical: {len(critical_fails)}")

if __name__ == '__main__':
    run_all()
