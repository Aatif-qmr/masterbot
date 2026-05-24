import os
import json
import sqlite3
import subprocess
import requests
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load env dynamically
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
QNT_TELEGRAM_TOKEN = os.getenv('QNT_TELEGRAM_TOKEN')
QNT_TELEGRAM_CHAT_ID = os.getenv('QNT_TELEGRAM_CHAT_ID')
FT_USERNAME = os.getenv('FREQTRADE_UI_USERNAME')
FT_PASSWORD = os.getenv('FREQTRADE_UI_PASSWORD')
M2_IP = os.getenv('M2_TAILSCALE_IP')
M2_USER = os.getenv('M2_SSH_USER')
if not M2_IP or not M2_USER:
    raise ValueError("Missing critical configuration: M2_TAILSCALE_IP and M2_SSH_USER must be set in .env")

LOG = BASE_DIR / 'logs' / 'health_check.log'
DB_PATH = BASE_DIR / 'user_data' / 'tradesv3_micro.sqlite'

def send_telegram_health_report(results: list, timestamp: str):
    """Send health check results to both Telegram bots."""
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = [r for r in results if r['status'] == 'FAIL']
    warned = [r for r in results if r['status'] == 'WARN']
    
    # Build message
    emoji = "✅" if len(failed) == 0 else "⚠️" if len(failed) == 0 or all(not f.get('critical', False) for f in failed) else "🚨"
    
    text = f"{emoji} <b>Health Check Report</b>\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"<b>Summary:</b> {passed}/{len(results)} checks passed\n"
    
    if failed:
        text += f"\n🔴 <b>Critical Failures:</b>\n"
        for f in failed:
            if f.get('critical', False):
                text += f"• {f['name']}: {f['message']}\n"
    
    if warned:
        text += f"\n⚠️ <b>Warnings:</b>\n"
        for w in warned:
            text += f"• {w['name']}: {w['message']}\n"
    
    text += f"\n<i>⏰ {timestamp}</i>"
    
    # Send to Trading Bot (TELEGRAM_BOT_TOKEN)
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
        except Exception as e:
            print(f"Failed to send to trading bot: {e}")
    
    # Send to QNT Bot (QNT_TELEGRAM_TOKEN)
    if QNT_TELEGRAM_TOKEN and QNT_TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{QNT_TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": QNT_TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
        except Exception as e:
            print(f"Failed to send to QNT bot: {e}")

def check_freqtrade_processes():
    supervisor_bin = str(BASE_DIR / 'venv/bin/supervisorctl')
    config_file = str(BASE_DIR / 'config/supervisord.conf')
    cmd = [supervisor_bin, '-c', config_file, 'status']
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    programs = [
        'freqtrade_daily',
        'freqtrade_mean_reversion',
        'freqtrade_scalp',
        'freqtrade_swing',
        'freqtrade_trend_follow',
        'freqtrade_micro'
    ]
    
    import time
    
    status_map = {}
    restart_attempts = {}
    all_running = True
    
    for prog in programs:
        is_running = any(prog in line and 'RUNNING' in line for line in res.stdout.split('\n'))
        if is_running:
            status_map[prog] = 'UP'
        else:
            restarted = False
            for attempt in range(1, 4):
                print(f"Auto-restart attempt {attempt} for {prog}...")
                restart_cmd = [supervisor_bin, '-c', config_file, 'restart', prog]
                subprocess.run(restart_cmd, capture_output=True, text=True)
                
                # Wait a bit for status to update
                time.sleep(3)
                
                check_cmd = [supervisor_bin, '-c', config_file, 'status', prog]
                check_res = subprocess.run(check_cmd, capture_output=True, text=True)
                if 'RUNNING' in check_res.stdout:
                    restarted = True
                    restart_attempts[prog] = attempt
                    break
            
            if restarted:
                status_map[prog] = f'RECOVERED ({restart_attempts[prog]} attempts)'
            else:
                status_map[prog] = 'DOWN'
                all_running = False
            
    message = " | ".join([f"{k[10:] if k.startswith('freqtrade_') else k}: {v}" for k, v in status_map.items()])
    
    if all_running:
        if restart_attempts:
            recovered_msg = ", ".join([f"{k}: recovered in {v} attempts" for k, v in restart_attempts.items()])
            return {"name": "Freqtrade Processes", "status": "WARN", "message": f"Recovered: {recovered_msg} | {message}", "critical": False}
        return {"name": "Freqtrade Processes", "status": "PASS", "message": f"All {len(programs)} instances running", "critical": True}
    return {"name": "Freqtrade Processes", "status": "FAIL", "message": message, "critical": True}

def check_freqtrade_apis():
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    ports = [8081, 8082, 8083, 8084, 8085, 8087, 8088]
    results = {}
    all_ok = True
    
    m1_ip = os.getenv('M1_TAILSCALE_IP', '127.0.0.1')
    for port in ports:
        try:
            url = f"http://{m1_ip}:{port}/api/v1/ping"
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
        return {"name": "Freqtrade APIs", "status": "PASS", "message": f"All {len(ports)} APIs responding", "critical": True}
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
    GEMINI_BIN = '/Users/aatifquamre/.nvm/versions/node/v20.20.2/bin/gemini'
    CLAUDE_BIN = '/Users/aatifquamre/.local/bin/claude'

    missing = []
    for name, path in [('gemini', GEMINI_BIN), ('claude', CLAUDE_BIN)]:
        if not os.path.exists(path):
            missing.append(name)

    if missing:
        return {
            'name': 'QNT Status',
            'status': 'WARN',
            'message': f'Missing CLI binaries: {", ".join(missing)}',
            'critical': False
        }

    try:
        result = subprocess.run([GEMINI_BIN, '--version'], capture_output=True, text=True, timeout=10)
        version = result.stdout.strip() or result.stderr.strip()
        return {
            'name': 'QNT Status',
            'status': 'PASS',
            'message': f'gemini {version}, claude present',
            'critical': False
        }
    except Exception as e:
        return {
            'name': 'QNT Status',
            'status': 'WARN',
            'message': f'CLI check error: {str(e)[:100]}',
            'critical': False
        }

def check_nats_connection() -> dict:
    """
    Verify NATS connection M1 -> M2.
    """
    import subprocess
    try:
        result = subprocess.run(
            [str(BASE_DIR / 'venv/bin/python'), '-c',
             'import asyncio,nats,os;'
             'from dotenv import load_dotenv;'
             f'load_dotenv("{BASE_DIR / ".env"}");'
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

def check_m2_shadow_health() -> dict:
    """Verify M2 shadow process and resources are healthy."""
    m2_ip = M2_IP
    m2_user = M2_USER
    try:
        result = subprocess.run([
            "ssh", f"{m2_user}@{m2_ip}",
            f"/Users/{m2_user}/cipher/venv/bin/python", f"/Users/{m2_user}/cipher/qnt/shadow/resource_monitor.py"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {
                'name': 'M2 Shadow Health',
                'status': 'FAIL',
                'message': f'M2 resource monitor failed: {result.stderr[:100]}',
                'critical': False
            }
        
        data = json.loads(result.stdout)
        
        if data["pressure"] == "critical":
            return {
                'name': 'M2 Shadow Health',
                'status': 'FAIL',
                'message': f'CRITICAL: {data["ram_percent"]:.1f}% RAM, throttled={data["throttled"]}',
                'critical': False
            }
        
        status = 'PASS'
        if data["throttled"] or data["pressure"] == "medium":
            status = 'WARN'

        return {
            'name': 'M2 Shadow Health',
            'status': status,
            'message': f'{data["pressure"].upper()} pressure, RAM {data["ram_percent"]:.1f}%',
            'critical': False
        }
    except Exception as e:
        return {
            'name': 'M2 Shadow Health',
            'status': 'WARN',
            'message': f'M2 shadow check error: {str(e)[:100]}',
            'critical': False
        }

def check_thesis_freshness() -> dict:
    """Verify thesis files are not stale for all trading pairs."""
    pairs = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT", "XRP_USDT"]
    thesis_dir = BASE_DIR / "thesis"
    stale = []
    missing = []

    for slug in pairs:
        path = thesis_dir / f"{slug}.json"
        if not path.exists():
            missing.append(slug)
            continue
        try:
            import json as _json
            from datetime import datetime, timezone
            data = _json.loads(path.read_text())
            ts = datetime.fromisoformat(data["generated_at"])
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h > 6:
                stale.append(f"{slug}({age_h:.1f}h)")
        except Exception:
            stale.append(f"{slug}(unreadable)")

    if missing:
        return {"name": "Thesis Files", "status": "WARN",
                "message": f"Missing thesis for: {', '.join(missing)}", "critical": False}
    if stale:
        return {"name": "Thesis Files", "status": "WARN",
                "message": f"Stale thesis: {', '.join(stale)}", "critical": False}
    return {"name": "Thesis Files", "status": "PASS", "message": "All thesis files fresh"}

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
        check_nats_connection,
        check_m2_shadow_health,
        check_thesis_freshness,
    ]
    
    results = []
    for fn in checks:
        try:
            results.append(fn())
        except Exception as e:
            name = fn.__name__.replace('check_', '').replace('_', ' ').title()
            results.append({"name": name, "status": "FAIL", "message": f"Exception: {e}", "critical": True})

    critical_fails = [r for r in results if r['status'] == 'FAIL' and r['critical']]
    
    # Log to file
    with open(LOG, 'a') as f:
        f.write(json.dumps({"timestamp": timestamp, "results": results}) + '\n')

    # Send report to both Telegram bots
    send_telegram_health_report(results, timestamp)

    passed = sum(1 for r in results if r['status'] == 'PASS')
    print(f"[{timestamp}] Health: {passed}/{len(results)} PASS | Critical: {len(critical_fails)}")

if __name__ == '__main__':
    run_all()
