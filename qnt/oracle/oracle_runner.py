import os
import sys

# Add paths
from pathlib import Path as _Path

BASE_DIR = str(_Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/memory"))
sys.path.insert(0, os.path.join(BASE_DIR, "qnt/oracle"))
from pathlib import Path

import freqtrade.data.history as history
from hmm_regime import detect_regime
from memory_manager import get_device_identity, log_action
from oracle_anomaly import run_all_anomaly_checks
from oracle_calendar import check_and_act as calendar_check
from oracle_sentiment import check_and_act as sentiment_check


def run(mode="all"):
    device = get_device_identity()

    if mode == "hmm" or mode == "all":
        try:
            # HMM requires some data context
            data_dir = Path(BASE_DIR) / "data"
            # If on M2, data is in data/
            # If on M1, data is in user_data/data/binance or synced
            # For the runner, we'll try to load recent BTC history
            data = history.load_pair_history(pair="BTC/USDT", timeframe="1h", datadir=data_dir)
            regime = detect_regime(data.tail(200))
            log_action(
                "oracle_hmm_regime",
                f"Current: {regime['regime']} (Conf: {regime['confidence']:.2f})",
                device["device"],
            )
        except Exception as e:
            print(f"Error in HMM regime check: {e}")

    if mode == "calendar" or mode == "all":
        try:
            calendar_check()
            log_action("oracle_calendar_check", "completed", device["device"])
        except Exception as e:
            print(f"Error in calendar check: {e}")

    if mode == "sentiment" or mode == "all":
        try:
            import importlib.util

            pipeline_path = os.path.join(BASE_DIR, "sentiment", "pipeline.py")
            spec = importlib.util.spec_from_file_location("sentiment_pipeline", pipeline_path)
            sentiment_pipeline = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sentiment_pipeline)
            sentiment_pipeline.run_pipeline()
            sentiment_check()
            log_action("oracle_sentiment_check", "completed", device["device"])
        except Exception as e:
            print(f"Error in sentiment check: {e}")

    if mode == "anomaly" or mode == "all":
        try:
            run_all_anomaly_checks()
            log_action("oracle_anomaly_check", "completed", device["device"])
        except Exception as e:
            print(f"Error in anomaly check: {e}")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    run(mode)
