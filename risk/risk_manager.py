import os
import json
import logging
import requests
import time
import fcntl
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Use home directory to make it machine-agnostic
HOME = Path.home()
BASE_DIR = HOME / 'masterbot'

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

def get_aggregated_balance():
    """Fetches total balance across all 5 Freqtrade instances."""
    user = os.getenv('FREQTRADE_UI_USERNAME')
    pwd = os.getenv('FREQTRADE_UI_PASSWORD')
    total = 0.0
    found = 0
    # Use localhost/127.0.0.1 for internal speed and reliability
    for port in [8080, 8081, 8082, 8083, 8084, 8085]:
        try:
            r = requests.get(
                f'http://127.0.0.1:{port}/api/v1/balance',
                auth=(user, pwd),
                timeout=5
            )
            if r.status_code == 200:
                total += float(r.json().get('total', 0))
                found += 1
        except:
            continue
    # If API fails, fall back to last seen in state file
    if found == 0:
        try:
            with open(BASE_DIR / 'risk/balance_state.json', 'r') as f:
                state = json.load(f)
                return state.get('last_seen_balance', 50000.0)
        except:
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
    except:
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

def check_daily_drawdown(current_balance: float, start_of_day_balance: float, limit_pct: float = 3.0) -> bool:
    if start_of_day_balance == 0: return True
    
    # CRITICAL FIX: If current_balance passed is a single instance ($10k) but baseline is global ($50k),
    # we MUST use the aggregated global balance to avoid false 80% drawdown alerts.
    if current_balance < (start_of_day_balance * 0.5):
        logging.info("Local balance detected, fetching aggregated global balance...")
        current_balance = get_aggregated_balance()

    drawdown_pct = ((start_of_day_balance - current_balance) / start_of_day_balance) * 100
    
    if drawdown_pct >= limit_pct:
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

def check_weekly_drawdown(current_balance: float, start_of_week_balance: float, limit_pct: float = 7.0) -> bool:
    if start_of_week_balance == 0: return True
    
    if current_balance < (start_of_week_balance * 0.5):
        current_balance = get_aggregated_balance()

    drawdown_pct = ((start_of_week_balance - current_balance) / start_of_week_balance) * 100
    
    if drawdown_pct >= limit_pct:
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
    
    if total_balance_usdt < 20000: # Heuristic for local balance
        total_balance_usdt = get_aggregated_balance()
        
    position_pct = (trade_amount_usdt / total_balance_usdt) * 100
    if position_pct > max_pct:
        logging.warning(f"Position size check failed: {position_pct:.2f}% (Max: {max_pct}%)")
        return False
    return True

def check_order_rate(trades_last_hour: int, max_trades_per_hour: int = 10) -> bool:
    if trades_last_hour > max_trades_per_hour:
        msg = (f"ORDER RATE CIRCUIT BREAKER\n"
               f"Trades in last hour: {trades_last_hour}\n"
               f"Maximum allowed: {max_trades_per_hour}\n"
               f"ACTION: Bot entering safe mode. Possible runaway loop detected.")
        logging.critical(msg.replace('\n', ' | '))
        send_telegram_alert(msg, 'CRITICAL')
        return False
    return True

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
    count = 0
    last_loss_time = None
    
    for trade in recent_trades:
        if trade.get('profit_ratio', 0) < 0:
            count += 1
            # First one in list is most recent
            if count == 1:
                last_loss_time = trade.get('close_date')
            
            if count >= max_consecutive:
                # Check cooldown if we have a timestamp
                if last_loss_time:
                    if isinstance(last_loss_time, str):
                        try:
                            last_loss_time = datetime.fromisoformat(last_loss_time.replace('Z', '+00:00'))
                        except ValueError:
                            pass # Fallback to blocking if date format is weird
                    
                    if isinstance(last_loss_time, datetime):
                        if last_loss_time.tzinfo is None:
                            last_loss_time = last_loss_time.replace(tzinfo=timezone.utc)
                        
                        now = datetime.now(timezone.utc)
                        if (now - last_loss_time) > timedelta(hours=1):
                            logging.info(f"Consecutive loss cooldown passed. Last loss was at {last_loss_time}")
                            return True

                msg = (f"CONSECUTIVE LOSS CIRCUIT BREAKER\n"
                       f"{count} losses in a row detected.\n"
                       f"Last loss at: {last_loss_time}\n"
                       f"ACTION: Entries paused for 1 hour from last loss.")
                logging.warning(msg.replace('\n', ' | '))
                send_telegram_alert(msg, 'WARNING')
                return False
        else:
            break
    return True

def run_all_checks(current_balance, start_of_day_balance, start_of_week_balance, 
                   trade_amount_usdt, trades_last_hour, recent_trades,
                   min_sentiment: str = 'NEUTRAL') -> dict:
    
    # Auto-aggregate if current_balance looks like a local instance balance
    if current_balance < (start_of_day_balance * 0.5):
         current_balance = get_aggregated_balance()

    checks = {
        "macro_headwinds": check_macro_headwinds(),
        "daily_drawdown": check_daily_drawdown(current_balance, start_of_day_balance),
        "weekly_drawdown": check_weekly_drawdown(current_balance, start_of_week_balance),
        "position_size": check_position_size(trade_amount_usdt, current_balance),
        "order_rate": check_order_rate(trades_last_hour),
        "consecutive_losses": check_consecutive_losses(recent_trades),
        "sentiment": check_sentiment(min_sentiment)
    }
    
    blocking_reasons = [k for k, v in checks.items() if not v]
    safe = len(blocking_reasons) == 0
    
    if not safe:
        logging.error(f"Risk checks blocked trading: {', '.join(blocking_reasons)}")
        
    return {
        "safe_to_trade": safe,
        "checks": checks,
        "blocking_reasons": blocking_reasons,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

