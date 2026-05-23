# qnt/oracle/test_hmm_regime.py
import unittest
import numpy as np
import polars as pl
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def _make_dataframe(n=150):
    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(n) * 100)
    return pl.DataFrame({
        "open": close * 0.999,
        "high": close * 1.001,
        "low": close * 0.998,
        "close": close,
        "volume": np.random.uniform(100, 500, n),
    })

class TestHMMRegime(unittest.TestCase):

    def test_detect_regime_returns_valid_string(self):
        from qnt.oracle.hmm_regime import detect_regime
        df = _make_dataframe()
        result = detect_regime(df, "BTC/USDT")
        self.assertIn(result, ("BULL", "BEAR", "RANGING"))

    def test_detect_regime_full_returns_dict(self):
        from qnt.oracle.hmm_regime import detect_regime_full
        df = _make_dataframe()
        result = detect_regime_full(df, "BTC/USDT")
        self.assertIn("current_regime", result)
        self.assertIn("next_regime", result)
        self.assertIn("confidence", result)
        self.assertIn(result["current_regime"], ("BULL", "BEAR", "RANGING"))
        self.assertIn(result["next_regime"], ("BULL", "BEAR", "RANGING"))
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_detect_regime_full_graceful_on_short_data(self):
        from qnt.oracle.hmm_regime import detect_regime_full
        df = _make_dataframe(n=5)
        result = detect_regime_full(df, "BTC/USDT")
        self.assertEqual(result["current_regime"], "RANGING")
        self.assertEqual(result["next_regime"], "RANGING")

if __name__ == "__main__":
    unittest.main()
