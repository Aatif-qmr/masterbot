# qnt/data/data_pipeline.py
# Master runner: pulls all external data sources then retrains HMM.
# Run once manually to bootstrap, then weekly via cron.
import sys
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
LOG_PATH = BASE_DIR / 'logs/data_pipeline.log'
sys.path.insert(0, str(BASE_DIR / 'qnt/data'))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT  = os.getenv('TELEGRAM_CHAT_ID')


def _log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    line = f'[{ts}] {msg}'
    print(line)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')


def _send_telegram(text: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
                json={'chat_id': TELEGRAM_CHAT, 'text': text, 'parse_mode': 'HTML'},
                timeout=10,
            )
        except Exception:
            pass


def run(skip_hf: bool = False, skip_cdd: bool = False, skip_retrain: bool = False, skip_calibrate: bool = False):
    start = datetime.now(timezone.utc)
    _log('=== Data pipeline started ===')
    results = {}

    # Step 1 — Extended Binance history via freqtrade download-data
    _log('Step 1: Extending candle history from Binance (2018→now)...')
    try:
        from historical_ingestor import run as run_historical
        ok = run_historical(timeframes=['1h', '4h', '1d'])
        results['historical'] = 'ok' if ok else 'failed'
        _log(f'Step 1 done: {results["historical"]}')
    except Exception as e:
        _log(f'Step 1 FAILED: {e}')
        results['historical'] = f'error: {e}'

    # Step 2 — CryptoDataDownload supplementary data
    if not skip_cdd:
        _log('Step 2: CryptoDataDownload OHLCV + funding merge...')
        try:
            from cdd_ingestor import run as run_cdd
            cdd_results = run_cdd()
            results['cdd'] = cdd_results
            _log(f'Step 2 done: {len(cdd_results.get("ohlcv", {}))} pairs merged')
        except Exception as e:
            _log(f'Step 2 FAILED: {e}')
            results['cdd'] = f'error: {e}'

    # Step 3 — HuggingFace supplementary signals
    if not skip_hf:
        _log('Step 3: HuggingFace signals (news, trading dataset)...')
        try:
            from hf_signals_ingestor import run as run_hf
            hf_results = run_hf()
            results['hf'] = hf_results
            _log(f'Step 3 done: {hf_results}')
        except Exception as e:
            _log(f'Step 3 FAILED: {e}')
            results['hf'] = f'error: {e}'

    # Step 4 — Retrain HMM with extended data
    if not skip_retrain:
        _log('Step 4: Retraining HMM with extended history...')
        try:
            from retrain_hmm_extended import run as run_retrain
            ok = run_retrain()
            results['hmm_retrain'] = 'ok' if ok else 'no_data'
            _log(f'Step 4 done: {results["hmm_retrain"]}')
        except Exception as e:
            _log(f'Step 4 FAILED: {e}')
            results['hmm_retrain'] = f'error: {e}'

    # Step 5 — Backtest calibration: pre-seed dynamic_params.json with walk-forward results
    if not skip_calibrate:
        _log('Step 5: Walk-forward backtest calibration (3 eras × 8y history)...')
        try:
            from backtest_calibrator import run as run_calibrate
            cal_results = run_calibrate()
            results['calibration'] = {s: list(p.keys()) for s, p in cal_results.items()}
            _log(f'Step 5 done: calibrated {list(cal_results.keys())}')
        except Exception as e:
            _log(f'Step 5 FAILED: {e}')
            results['calibration'] = f'error: {e}'

    elapsed = (datetime.now(timezone.utc) - start).seconds
    _log(f'=== Data pipeline done ({elapsed}s) ===')

    _send_telegram(
        f'📦 <b>Data Pipeline Complete</b>\n'
        f'━━━━━━━━━━━━━━━━━━━━━━\n'
        f'• Binance history: {results.get("historical", "skipped")}\n'
        f'• CDD merge: {len(results.get("cdd", {}).get("ohlcv", {})) if isinstance(results.get("cdd"), dict) else results.get("cdd", "skipped")} pairs\n'
        f'• HF signals: {results.get("hf", "skipped")}\n'
        f'• HMM retrain: {results.get("hmm_retrain", "skipped")}\n'
        f'• Backtest calibration: {results.get("calibration", "skipped")}\n'
        f'<i>⏱ {elapsed}s</i>'
    )

    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-hf', action='store_true')
    parser.add_argument('--skip-cdd', action='store_true')
    parser.add_argument('--skip-retrain', action='store_true')
    parser.add_argument('--skip-calibrate', action='store_true')
    args = parser.parse_args()
    run(skip_hf=args.skip_hf, skip_cdd=args.skip_cdd, skip_retrain=args.skip_retrain, skip_calibrate=args.skip_calibrate)
