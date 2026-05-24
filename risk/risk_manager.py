import os
import json
import logging
import requests
import time
import fcntl
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ── Risk Checks Backend Selection ──────────────────────────
# Priority: Rust (PyO3) > Cython (.so) > Pure Python fallback
# The Rust module is compiled via maturin from risk/risk_checks_rs/
# and provides thread-safe, zero-allocation arithmetic.
_BACKEND = 'python'  # tracks which implementation is active

try:
    # Priority 1: Rust module (compiled via maturin develop)
    from risk_checks import (
        compute_drawdown_pct as _compute_drawdown_pct,
        compute_position_pct as _compute_position_pct,
        check_rate_exceeded as _check_rate_exceeded,
        count_consecutive_losses as _count_consecutive_losses,
        batch_compute_drawdowns as _batch_compute_drawdowns,
    )
    # Verify it's the Rust version (has `version()` function)
    from risk_checks import version as _rc_version
    _BACKEND = 'rust'
except ImportError:
    try:
        # Priority 2: Cython module (legacy .so)
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from risk_checks import (
            compute_drawdown_pct as _compute_drawdown_pct,
            compute_position_pct as _compute_position_pct,
            check_rate_exceeded as _check_rate_exceeded,
            count_consecutive_losses as _count_consecutive_losses,
        )
        def _batch_compute_drawdowns(current_balances, start_balances):
            return [_compute_drawdown_pct(c, s) for c, s in zip(current_balances, start_balances)]
        _BACKEND = 'cython'
    except ImportError:
        # Priority 3: Pure Python fallback (always works)
        def _compute_drawdown_pct(current, start):
            return 0.0 if start == 0.0 else ((start - current) / start) * 100.0
        def _compute_position_pct(trade_amount, balance):
            return 0.0 if balance == 0.0 else (trade_amount / balance) * 100.0
        def _check_rate_exceeded(trades_last_hour, max_trades_per_hour):
            return trades_last_hour > max_trades_per_hour
        def _count_consecutive_losses(profits):
            count = 0
            for p in profits:
                if p < 0.0:
                    count += 1
                else:
                    break
            return count
        def _batch_compute_drawdowns(current_balances, start_balances):
            return [_compute_drawdown_pct(c, s) for c, s in zip(current_balances, start_balances)]
        _BACKEND = 'python'

# Backward compat alias
_USE_CYTHON = _BACKEND in ('rust', 'cython')

# Use home directory to make it machine-agnostic
HOME = Path.home()
BASE_DIR = HOME / 'cipher'

load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

LOG_PATH = BASE_DIR / 'logs' / 'risk_manager.log'
os.makedirs(LOG_PATH.parent, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

COOLDOWN_FILE = '/tmp/risk_alert_cooldown'
COOLDOWN_SECONDS = 3600  # 1 hour between alerts

_SENTIMENT_WARN_FILE = '/tmp/qnt_sentiment_warn_ts'
_SENTIMENT_WARN_INTERVAL = 600  # 10 minutes between sentiment log entries
_sentiment_warn_proc_lock = threading.Lock()  # in-process guard for multi-pair threads

def _can_send_alert():
    """Checks cooldown with file locking to prevent race conditions."""
    try:
        # Open file for reading/writing, create if doesn't exist
        f = open(COOLDOWN_FILE, 'a+')
        # Exclusive lock, non-blocking
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another process has the lock, we shouldn't alert
            f.close()
            return False
            
        f.seek(0)
        content = f.read().strip()
        now = time.time()
        
        if content:
            last = float(content)
            if now - last < COOLDOWN_SECONDS:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
                return False
        
        # Update timestamp
        f.truncate(0)
        f.write(str(now))
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()
        return True
    except Exception as e:
        logging.error(f"Error in cooldown check: {e}")
        return True # Default to True to not swallow critical errors

ALERT_LOCK_FILE = '/tmp/qnt_risk_alert.lock'
ALERT_COOLDOWN_SECONDS = 3600  # 1 hour minimum

def _is_alert_allowed() -> bool:
    """Hard 1-hour cooldown that cannot be bypassed."""
    try:
        ts_file = '/tmp/qnt_risk_alert_ts'
        if os.path.exists(ts_file):
            with open(ts_file) as f:
                content = f.read().strip()
                if content:
                    last_ts = float(content)
                    if time.time() - last_ts < ALERT_COOLDOWN_SECONDS:
                        return False
        
        # Update timestamp
        with open(ts_file, 'w') as f:
            f.write(str(time.time()))
        return True
    except Exception as e:
        return True  # If check fails, allow alert to be safe

from concurrent.futures import ThreadPoolExecutor, as_completed

def _fetch_balance(port, ip, user, pwd):
    try:
        r = requests.get(
            f'http://{ip}:{port}/api/v1/balance',
            auth=(user, pwd),
            timeout=1.5
        )
        if r.status_code == 200:
            return float(r.json().get('total', 0))
    except Exception:
        pass
    return None

def _get_cluster_balance() -> float:
    """
    Queries ALL 6 bot instances on the cluster IP concurrently.
    Returns combined USDT total.
    """
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    ip = os.getenv("M1_TAILSCALE_IP", "127.0.0.1")
    total = 0.0
    found = 0
    ports = [8080, 8081, 8082, 8083, 8084, 8085]

    with ThreadPoolExecutor(max_workers=len(ports)) as executor:
        futures = {executor.submit(_fetch_balance, port, ip, user, pwd): port for port in ports}
        for future in as_completed(futures):
            res = future.result()
            if res is not None:
                total += res
                found += 1

    # If any API fails, fall back to last seen in state file to prevent false drawdown alerts
    if found < 6:
        try:
            with open(BASE_DIR / 'risk/balance_state.json', 'r') as f:
                state = json.load(f)
                return state.get('last_seen_balance', 50000.0)
        except Exception:
            return 50000.0

    return total
def send_telegram_alert(message: str, level: str = 'WARNING') -> bool:
    if level == 'CRITICAL':
        if not _can_send_alert():
            return False
            
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    
    prefixes = {'INFO': 'ℹ️', 'WARNING': '⚠️', 'CRITICAL': '🚨'}
    prefix = prefixes.get(level, '⚠️')
    full_message = f"{prefix} {message}"
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': full_message}, timeout=5)
        return res.status_code == 200
    except Exception as e:
        return False

def check_macro_headwinds() -> bool:
    """Blocks new long entries if DXY is pumping aggressively."""
    try:
        macro_file = BASE_DIR / 'risk/macro_state.json'
        if not macro_file.exists():
            return True
            
        with open(macro_file, 'r') as f:
            state = json.load(f)
            
        dxy_change = state.get('dxy_24h_change', 0.0)
        threshold = float(os.getenv('DXY_THRESHOLD_PCT', '1.0'))
        
        if dxy_change >= threshold:
            msg = (f"MACRO HEADWINDS DETECTED\n"
                   f"DXY 24h Change: {dxy_change:+.2f}%\n"
                   f"Threshold: {threshold:.2f}%\n"
                   f"ACTION: New entries blocked (US Dollar strength).")
            logging.warning(msg.replace('\n', ' | '))
            send_telegram_alert(msg, 'WARNING')
            return False
        return True
    except Exception as e:
        logging.error(f"Error in macro check: {e}")
        return True

def check_daily_drawdown(current_balance: float, start_of_day_balance: float, limit_pct: float = 3.0, precomputed_dd: float = None) -> bool:
    if start_of_day_balance == 0: return True
    
    # CRITICAL FIX: Ensure we use aggregated cluster balance
    if current_balance < (start_of_day_balance * 0.5):
        current_balance = _get_cluster_balance()

    drawdown_pct = precomputed_dd if precomputed_dd is not None else _compute_drawdown_pct(current_balance, start_of_day_balance)

    # SANITY CHECK: If drawdown > 50% something is wrong with reading, not actual loss
    if drawdown_pct > 50.0:
        logging.warning(f"Impossible daily drawdown {drawdown_pct:.1f}% detected. Skipping alert/block.")
        return True

    if drawdown_pct >= limit_pct:
        if not _is_alert_allowed():
            return True # Silently skip, cooldown active

        msg = (f"DAILY DRAWDOWN LIMIT HIT\n"
               f"Start of day: ${start_of_day_balance:,.2f}\n"
               f"Current: ${current_balance:,.2f}\n"
               f"Drawdown: {drawdown_pct:.2f}%\n"
               f"Limit: {limit_pct:.2f}%\n"
               f"ACTION: All new entries blocked until tomorrow.")
        logging.critical(msg.replace('\n', ' | '))
        send_telegram_alert(msg, 'CRITICAL')
        return False
    
    if drawdown_pct >= (limit_pct * 0.75):
        msg = f"Approaching daily drawdown limit: {drawdown_pct:.2f}%"
        logging.warning(msg)
        send_telegram_alert(msg, 'WARNING')
        
    return True

def check_weekly_drawdown(current_balance: float, start_of_week_balance: float, limit_pct: float = 7.0, precomputed_dd: float = None) -> bool:
    if start_of_week_balance == 0: return True
    
    # Ensure we use aggregated cluster balance
    if current_balance < (start_of_week_balance * 0.5):
        current_balance = _get_cluster_balance()

    drawdown_pct = precomputed_dd if precomputed_dd is not None else _compute_drawdown_pct(current_balance, start_of_week_balance)

    # SANITY CHECK: If drawdown > 50% something is wrong with reading
    if drawdown_pct > 50.0:
        logging.warning(f"Impossible weekly drawdown {drawdown_pct:.1f}% detected. Skipping alert/block.")
        return True

    if drawdown_pct >= limit_pct:
        if not _is_alert_allowed():
            return True

        msg = (f"WEEKLY DRAWDOWN LIMIT HIT\n"
               f"Start of week: ${start_of_week_balance:,.2f}\n"
               f"Current: ${current_balance:,.2f}\n"
               f"Drawdown: {drawdown_pct:.2f}%\n"
               f"ACTION: All new entries blocked. Manual review required before resuming.")
        logging.critical(msg.replace('\n', ' | '))
        send_telegram_alert(msg, 'CRITICAL')
        return False
    
    if drawdown_pct >= (limit_pct * 0.75):
        msg = f"Approaching weekly drawdown limit: {drawdown_pct:.2f}%"
        logging.warning(msg)
        send_telegram_alert(msg, 'WARNING')
        
    return True

def check_position_size(trade_amount_usdt: float, total_balance_usdt: float, max_pct: float = 10.0) -> bool:
    if total_balance_usdt == 0: return True
    
    # Ensure we use aggregated cluster balance
    if total_balance_usdt < 20000: # Heuristic for local balance
        total_balance_usdt = _get_cluster_balance()
        
    position_pct = _compute_position_pct(trade_amount_usdt, total_balance_usdt)
    if position_pct > max_pct:
        logging.warning(f"Position size check failed: {position_pct:.2f}% (Max: {max_pct}%)")
        return False
    return True

def check_order_rate(trades_last_hour: int, max_trades_per_hour: int = 10) -> bool:
    if _check_rate_exceeded(trades_last_hour, max_trades_per_hour):
        msg = (f"ORDER RATE CIRCUIT BREAKER\n"
               f"Trades in last hour: {trades_last_hour}\n"
               f"Maximum allowed: {max_trades_per_hour}\n"
               f"ACTION: Bot entering safe mode. Possible runaway loop detected.")
        logging.critical(msg.replace('\n', ' | '))
        send_telegram_alert(msg, 'CRITICAL')
        return False
    return True

def _can_log_sentiment_warn() -> bool:
    """Rate-limits sentiment warning logs to once per 10 minutes (thread + file-locked)."""
    if not _sentiment_warn_proc_lock.acquire(blocking=False):
        return False
    try:
        lock_path = _SENTIMENT_WARN_FILE + '.lock'
        try:
            with open(lock_path, 'w') as lf:
                try:
                    fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return False

                now = time.time()
                try:
                    with open(_SENTIMENT_WARN_FILE, 'r') as rf:
                        content = rf.read().strip()
                    if content and now - float(content) < _SENTIMENT_WARN_INTERVAL:
                        return False
                except (FileNotFoundError, ValueError):
                    pass

                with open(_SENTIMENT_WARN_FILE, 'w') as wf:
                    wf.write(str(now))
                return True
        except Exception:
            return True
    finally:
        _sentiment_warn_proc_lock.release()


def check_sentiment(min_signal: str = 'NEUTRAL') -> bool:
    """Blocks entries based on global sentiment score."""
    try:
        from sentiment.reader import get_current_sentiment, get_sentiment_signal

        sentiment = get_current_sentiment()
        signal = get_sentiment_signal()

        # Mapping signals to numeric ranks for comparison
        # Fail closed on UNAVAILABLE (rank 0)
        ranks = {'BEARISH': 0, 'NEUTRAL': 1, 'BULLISH': 2, 'UNAVAILABLE': 0}

        current_rank = ranks.get(signal, 0)
        required_rank = ranks.get(min_signal, 1)

        if current_rank < required_rank:
            if _can_log_sentiment_warn():
                msg = (f"SENTIMENT BLOCK\n"
                       f"Current Signal: {signal} ({sentiment.get('score', 0.0):.3f})\n"
                       f"Required: {min_signal}\n"
                       f"ACTION: New entries blocked.")
                logging.warning(msg.replace('\n', ' | '))
            return False
        return True
    except Exception as e:
        logging.error(f"Error in sentiment check: {e}")
        return True # Default to True to avoid total halt if reader code has a bug

def check_consecutive_losses(recent_trades: list, max_consecutive: int = 3) -> bool:
    def _profit(t):
        if isinstance(t, dict):
            return float(t.get('profit_ratio', 0) or 0.0)
        # Trade ORM object: try close_profit (current), fall back to profit_ratio (legacy)
        val = getattr(t, 'close_profit', None) or getattr(t, 'profit_ratio', None)
        return float(val or 0.0)
    profits = [_profit(t) for t in recent_trades]
    count = _count_consecutive_losses(profits)
    first = recent_trades[0] if count > 0 and recent_trades else None
    if first is None:
        last_loss_time = None
    elif isinstance(first, dict):
        last_loss_time = first.get('close_date')
    else:
        last_loss_time = getattr(first, 'close_date', None)

    if count >= max_consecutive:
        if last_loss_time:
            if isinstance(last_loss_time, str):
                try:
                    last_loss_time = datetime.fromisoformat(last_loss_time.replace('Z', '+00:00'))
                except ValueError:
                    pass
            if isinstance(last_loss_time, datetime):
                if last_loss_time.tzinfo is None:
                    last_loss_time = last_loss_time.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_loss_time) > timedelta(hours=1):
                    logging.info(f"Consecutive loss cooldown passed. Last loss was at {last_loss_time}")
                    return True

        msg = (f"CONSECUTIVE LOSS CIRCUIT BREAKER\n"
               f"{count} losses in a row detected.\n"
               f"Last loss at: {last_loss_time}\n"
               f"ACTION: Entries paused for 1 hour from last loss.")
        logging.warning(msg.replace('\n', ' | '))
        send_telegram_alert(msg, 'WARNING')
        return False
    return True

def run_all_checks(current_balance=None, start_of_day_balance=None, start_of_week_balance=None, 
                   trade_amount_usdt=None, trades_last_hour=None, recent_trades=None,
                   min_sentiment: str = 'NEUTRAL') -> dict:
    
    # Handle case where first arg is a pair name (string) from legacy strategy calls
    if isinstance(current_balance, str):
        current_balance = None

    # Fetch defaults if not provided
    if current_balance is None:
        current_balance = _get_cluster_balance()
    if start_of_day_balance is None or start_of_week_balance is None:
        try:
            with open(BASE_DIR / 'risk/balance_state.json') as f:
                state = json.load(f)
            start_of_day_balance = start_of_day_balance or state.get('start_of_day', current_balance)
            start_of_week_balance = start_of_week_balance or state.get('start_of_week', current_balance)
        except Exception as e:
            start_of_day_balance = start_of_day_balance or current_balance
            start_of_week_balance = start_of_week_balance or current_balance

    if trade_amount_usdt is None: trade_amount_usdt = 0
    if trades_last_hour is None: trades_last_hour = 0
    if recent_trades is None: recent_trades = []

    # Auto-aggregate if current_balance looks like a local instance balance
    if current_balance < (start_of_day_balance * 0.5):
         current_balance = _get_cluster_balance()

    # Vectorized FFI call to compute drawdowns
    drawdowns = _batch_compute_drawdowns(
        [current_balance, current_balance],
        [start_of_day_balance, start_of_week_balance]
    )
    daily_dd, weekly_dd = drawdowns[0], drawdowns[1]

    checks = {
        "macro_headwinds": check_macro_headwinds(),
        "daily_drawdown": check_daily_drawdown(current_balance, start_of_day_balance, precomputed_dd=daily_dd),
        "weekly_drawdown": check_weekly_drawdown(current_balance, start_of_week_balance, precomputed_dd=weekly_dd),
        "position_size": check_position_size(trade_amount_usdt, current_balance),
        "order_rate": check_order_rate(trades_last_hour),
        "consecutive_losses": check_consecutive_losses(recent_trades),
        "sentiment": check_sentiment(min_sentiment)
    }
    
    blocking_reasons = [k for k, v in checks.items() if not v]
    safe = len(blocking_reasons) == 0
    
    if not safe:
        sentiment_only = len(blocking_reasons) == 1 and blocking_reasons[0] == 'sentiment'
        if not sentiment_only:
            logging.error(f"Risk checks blocked trading: {', '.join(blocking_reasons)}")
        
    return {
        "safe_to_trade": safe,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

