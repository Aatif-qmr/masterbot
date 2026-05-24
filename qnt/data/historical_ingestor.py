# qnt/data/historical_ingestor.py
# Extends existing feather files by downloading full Binance history via freqtrade.
# Pulls from 2018-01-01 for all pairs and all timeframes already on disk.
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
BASE_DIR = HOME / 'cipher'
FT_BIN = str(BASE_DIR / 'venv/bin/freqtrade')
CONFIG = str(BASE_DIR / 'config/config_daily.json')
DATA_DIR = str(BASE_DIR / 'user_data/data/binance')

PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT',
]
TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']
TIMERANGE = '20180101-'


def run(timeframes: list = None, timerange: str = TIMERANGE):
    tfs = timeframes or TIMEFRAMES
    print(f'[historical_ingestor] Downloading {len(PAIRS)} pairs × {len(tfs)} timeframes '
          f'from {timerange[:8]} via Binance...')

    cmd = [
        FT_BIN, 'download-data',
        '--config', CONFIG,
        '--pairs', *PAIRS,
        '--timeframes', *tfs,
        '--timerange', timerange,
        '--datadir', DATA_DIR,
        '--exchange', 'binance',
        '--prepend',
    ]

    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode == 0:
        print(f'[historical_ingestor] Download complete.')
    else:
        print(f'[historical_ingestor] Download failed (exit {result.returncode})')
    return result.returncode == 0


if __name__ == '__main__':
    # Allow passing specific timeframes: python historical_ingestor.py 1h 4h
    tfs = sys.argv[1:] if len(sys.argv) > 1 else None
    run(timeframes=tfs)
