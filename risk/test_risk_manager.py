import unittest
from risk.risk_manager import (
    check_daily_drawdown, check_weekly_drawdown, 
    check_position_size, check_order_rate, 
    check_consecutive_losses, run_all_checks
)

class TestRiskManager(unittest.TestCase):

    def test_daily_drawdown_blocks_at_limit(self):
        # current=48.50, start=50.00 -> 3% loss -> False
        self.assertFalse(check_daily_drawdown(48.50, 50.00))

    def test_daily_drawdown_allows_below_limit(self):
        # current=49.00, start=50.00 -> 2% loss -> True
        self.assertTrue(check_daily_drawdown(49.00, 50.00))

    def test_daily_drawdown_warns_at_75pct(self):
        # current=48.88, start=50.00 -> 2.24% loss (threshold 2.25%) -> True
        # 48.87 would be 2.26%
        self.assertTrue(check_daily_drawdown(48.88, 50.00))

    def test_weekly_drawdown_blocks_at_limit(self):
        # current=46.50, start=50.00 -> 7% loss -> False
        self.assertFalse(check_weekly_drawdown(46.50, 50.00))

    def test_weekly_drawdown_allows_below_limit(self):
        # current=47.00, start=50.00 -> 6% loss -> True
        self.assertTrue(check_weekly_drawdown(47.00, 50.00))

    def test_position_size_blocks_over_limit(self):
        # trade=6.00, balance=50.00 -> 12% -> False
        self.assertFalse(check_position_size(6.00, 50.00))

    def test_position_size_allows_under_limit(self):
        # trade=4.00, balance=50.00 -> 8% -> True
        self.assertTrue(check_position_size(4.00, 50.00))

    def test_order_rate_blocks_runaway(self):
        # trades_last_hour=15, max=10 -> False
        self.assertFalse(check_order_rate(15, 10))

    def test_order_rate_allows_normal(self):
        # trades_last_hour=5, max=10 -> True
        self.assertTrue(check_order_rate(5, 10))

    def test_consecutive_losses_blocks_at_three(self):
        recent_trades = [
            {'profit_ratio': -0.02},
            {'profit_ratio': -0.03},
            {'profit_ratio': -0.015}
        ]
        self.assertFalse(check_consecutive_losses(recent_trades))

    def test_consecutive_losses_allows_with_win(self):
        recent_trades = [
            {'profit_ratio': -0.02},
            {'profit_ratio': 0.03},
            {'profit_ratio': -0.015}
        ]
        self.assertTrue(check_consecutive_losses(recent_trades))

    def test_run_all_checks_returns_correct_structure(self):
        result = run_all_checks(50.0, 50.0, 50.0, 4.0, 2, [])
        self.assertIsInstance(result, dict)
        self.assertTrue(result['safe_to_trade'])
        self.assertEqual(len(result['blocking_reasons']), 0)
        self.assertIn('checks', result)
        self.assertIn('timestamp', result)

if __name__ == '__main__':
    unittest.main()
