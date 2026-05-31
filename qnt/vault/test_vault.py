# qnt/vault/test_vault.py
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestVault(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        # Reset module-level client/encoder so each test gets a fresh isolated instance
        import qnt.vault.vault as vault_mod

        vault_mod._client = None
        vault_mod._encoder = None
        self._patch = patch("qnt.vault.vault.QDRANT_PATH", self._tmpdir)
        self._patch.start()

    def tearDown(self):
        import qnt.vault.vault as vault_mod

        if vault_mod._client is not None:
            try:
                vault_mod._client.close()
            except Exception:
                pass
            vault_mod._client = None
        vault_mod._encoder = None
        self._patch.stop()

    def test_store_and_recall_lesson(self):
        from qnt.vault.vault import recall_lessons, store_lesson

        ok = store_lesson(
            "test_001",
            "BTC/USDT trade closed at +2.3% profit after RSI divergence",
            {
                "pair": "BTC/USDT",
                "profit_ratio": 0.023,
                "strategy": "MeanReversionV1",
                "type": "trade_result",
            },
        )
        self.assertTrue(ok)
        results = recall_lessons("RSI divergence BTC profit")
        self.assertIsNotNone(results)
        self.assertGreater(len(results), 0)

    def test_get_collection_stats(self):
        from qnt.vault.vault import get_collection_stats

        stats = get_collection_stats()
        self.assertIn("entry_count", stats)
        self.assertIsInstance(stats["entry_count"], int)

    def test_add_trade_memory(self):
        from qnt.vault.vault import add_trade_memory

        trade = {"id": 42, "pair": "ETH/USDT", "strategy": "TrendFollowV1"}
        ok = add_trade_memory(trade, "Strong uptrend confirmed by EMA crossover.")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
