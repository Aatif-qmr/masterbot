import os, json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

BASE_DIR = Path('/Users/azmatsaif/cipher')
DATA_DIR = BASE_DIR / 'user_data/data/binance'
PARQUET_DIR = BASE_DIR / 'data_parquet'
PARQUET_DIR.mkdir(exist_ok=True)

def convert_pair_to_parquet(pair, timeframe):
    pair_safe = pair.replace('/', '_')
    # Freqtrade feather naming: BTC_USDT-1h.feather
    file_pattern = f"{pair_safe}-{timeframe}.feather"
    
    source_files = list(DATA_DIR.rglob(file_pattern))
    if not source_files:
        # Try JSON
        file_pattern = f"{pair_safe}-{timeframe}.json"
        source_files = list(DATA_DIR.rglob(file_pattern))
        
    if not source_files:
        return False
    
    source_file = source_files[0]
    print(f"Converting: {source_file.name}")
    
    if source_file.suffix == '.feather':
        df = pd.read_feather(source_file)
    else:
        with open(source_file) as f:
            raw = json.load(f)
        df = pd.DataFrame(raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.drop('timestamp', axis=1)

    df['pair'] = pair
    df['timeframe'] = timeframe
    
    # Save as partitioned Parquet
    out_dir = PARQUET_DIR / pair_safe / timeframe
    out_dir.mkdir(parents=True, exist_ok=True)
    
    table = pa.Table.from_pandas(df)
    pq.write_to_dataset(
        table,
        root_path=str(out_dir),
        partition_cols=['pair', 'timeframe'],
        compression='snappy'
    )
    
    original_size = os.path.getsize(source_file)
    parquet_size = sum(f.stat().st_size for f in out_dir.rglob('*.parquet'))
    
    compression = (1 - parquet_size/original_size) * 100
    print(f"  Original: {original_size/1024/1024:.1f}MB")
    print(f"  Parquet:  {parquet_size/1024/1024:.1f}MB")
    print(f"  Saved:    {compression:.0f}%")
    return True

if __name__ == '__main__':
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
    
    print("Converting all data to Parquet format...")
    success = 0
    for pair in pairs:
        for tf in timeframes:
            try:
                if convert_pair_to_parquet(pair, tf):
                    success += 1
            except Exception as e:
                print(f"Error {pair} {tf}: {e}")
    
    print(f"\nConverted {success} datasets to Parquet")
    print(f"Parquet data at: {PARQUET_DIR}")
