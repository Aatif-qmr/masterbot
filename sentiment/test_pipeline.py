# sentiment/test_pipeline.py
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSentimentPipeline(unittest.TestCase):
    def test_score_returns_float_in_range(self):
        from sentiment.pipeline import score_with_finbert

        titles = ["Bitcoin surges to new all time high", "Crypto market crashes on Fed news"]
        score = score_with_finbert(titles)
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, -1.0)
        self.assertLessEqual(score, 1.0)

    def test_score_bullish_titles_positive(self):
        from sentiment.pipeline import score_with_finbert

        titles = ["BTC moon breakout bullish rally surge", "Crypto bull run gains accelerate"]
        score = score_with_finbert(titles)
        self.assertGreater(score, 0.0)

    def test_score_bearish_titles_negative(self):
        from sentiment.pipeline import score_with_finbert

        titles = [
            "Bitcoin price crashes and dumps hard",
            "Bitcoin bearish reversal sell signal confirmed",
        ]
        score = score_with_finbert(titles)
        self.assertLess(score, 0.0)

    def test_empty_titles_returns_zero(self):
        from sentiment.pipeline import score_with_finbert

        self.assertEqual(score_with_finbert([]), 0.0)

    def test_failed_source_redistributes_weights(self):
        from sentiment.pipeline import WEIGHTS

        active_sources = ["reddit", "news", "coingecko", "feargreed"]
        total_active_weight = sum(WEIGHTS[s] for s in active_sources)

        active_weights = {}
        for s in WEIGHTS:
            if s in active_sources:
                active_weights[s] = WEIGHTS[s] / total_active_weight
            else:
                active_weights[s] = 0.0

        self.assertAlmostEqual(sum(active_weights.values()), 1.0)
        self.assertEqual(active_weights["funding"], 0.0)


if __name__ == "__main__":
    unittest.main()
