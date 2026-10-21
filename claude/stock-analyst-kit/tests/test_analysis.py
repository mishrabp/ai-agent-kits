# Unit tests for the indicator and backtest math in server/analysis.py. No network and no third-party packages.
# Run: python3 -m unittest discover -s tests
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import analysis as an  # noqa: E402


class IndicatorTest(unittest.TestCase):
    def test_sma_and_ema(self):
        self.assertEqual(an.sma_series([1, 2, 3, 4, 5], 3), [None, None, 2, 3, 4])
        ema = an.ema_series([1, 2, 3, 4, 5], 3)
        self.assertEqual(ema[2], 2)  # seeded with the SMA
        self.assertAlmostEqual(ema[3], 3)  # 4*0.5 + 2*0.5
        self.assertAlmostEqual(ema[4], 4)

    def test_rsi_extremes(self):
        self.assertEqual(an.rsi_series(list(range(1, 30)))[-1], 100.0)  # only gains
        self.assertAlmostEqual(an.rsi_series(list(range(30, 1, -1)))[-1], 0.0)  # only losses
        zigzag = [10 + (i % 2) for i in range(40)]
        self.assertAlmostEqual(an.rsi_series(zigzag)[-1], 50, delta=5)

    def test_atr_of_constant_range(self):
        closes = [100.0] * 30
        highs, lows = [101.0] * 30, [99.0] * 30
        self.assertAlmostEqual(an.atr_series(highs, lows, closes)[-1], 2.0)

    def test_pct_change_and_volatility(self):
        self.assertAlmostEqual(an.pct_change([100, 105, 110], 2), 0.10)
        self.assertIsNone(an.pct_change([100], 5))
        self.assertAlmostEqual(an.annual_volatility([100.0] * 70), 0.0)

    def test_prob_touch_grows_with_volatility(self):
        low, high = an.prob_touch(0.05, 0.15, 21), an.prob_touch(0.05, 0.60, 21)
        self.assertLess(low, high)
        self.assertTrue(0 < low < 1 and 0 < high <= 1)
        # Reflection principle: 2 * (1 - Phi(z)) with z = ln(1.05) / (0.30 * sqrt(21/252))
        z = math.log(1.05) / (0.30 * math.sqrt(21 / 252))
        expected = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
        self.assertAlmostEqual(an.prob_touch(0.05, 0.30, 21), expected, places=6)

    def test_swing_levels(self):
        lows = [10, 9, 8, 7, 6, 5, 6, 7, 8, 9, 10, 11, 12] + [12] * 5
        highs = [x + 1 for x in lows]
        support, _ = an.swing_levels(highs, lows, price=11.5, lookback=50, width=3)
        self.assertEqual(support, 5)


class BacktestTest(unittest.TestCase):
    def test_steady_uptrend_always_wins(self):
        closes = [100 * 1.01 ** i for i in range(80)]
        highs, lows = [c * 1.002 for c in closes], [c * 0.998 for c in closes]
        atrs = [1.0] * 80
        res = an.backtest_target_before_stop(highs, lows, closes, atrs, target=0.05, horizon=21)
        self.assertEqual(res["target_before_stop"], 1.0)
        self.assertEqual(res["closed_above_target_at_horizon"], 1.0)

    def test_steady_downtrend_never_wins(self):
        closes = [100 * 0.99 ** i for i in range(80)]
        highs, lows = [c * 1.002 for c in closes], [c * 0.998 for c in closes]
        res = an.backtest_target_before_stop(highs, lows, closes, [1.0] * 80, target=0.05, horizon=21)
        self.assertEqual(res["target_before_stop"], 0.0)

    def test_day_touching_both_counts_as_stop(self):
        closes = [100.0] * 30
        highs, lows = [100.0] * 30, [100.0] * 30
        highs[1], lows[1] = 106.0, 90.0  # one wild day hits target and stop
        res = an.backtest_target_before_stop(highs, lows, closes, [2.0] * 30, target=0.05, horizon=5,
                                             mask=[i == 0 for i in range(30)])
        self.assertEqual(res["samples"], 1)
        self.assertEqual(res["target_before_stop"], 0.0)
        self.assertEqual(res["touched_target"], 1.0)

    def test_post_earnings_moves(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"]
        closes = [100, 100, 110, 110]
        res = an.post_earnings_moves(dates, closes, ["2026-01-02"])
        self.assertEqual(res["count"], 1)
        self.assertAlmostEqual(res["average_abs_move"], 0.10)


class SummaryTest(unittest.TestCase):
    def test_technical_summary_on_synthetic_series(self):
        n = 400
        closes = [100 + 10 * math.sin(i / 15) + i * 0.05 for i in range(n)]
        highs, lows = [c + 1 for c in closes], [c - 1 for c in closes]
        dates = [f"day{i}" for i in range(n)]
        s = an.technical_summary(dates, closes, highs, lows, closes, [1e6] * n, bench_closes=closes)
        self.assertEqual(s["price"], round(closes[-1], 2))
        self.assertGreater(s["probability_anchors"]["all_windows_3y"]["samples"], 300)
        plan = s["suggested_plan"]
        self.assertLess(plan["stop_price"], s["price"])
        self.assertAlmostEqual(plan["target_price_for_5pct_from_last_close"], round(closes[-1] * 1.05, 2), places=1)
        self.assertTrue(0.03 <= plan["stop_pct"] <= 0.10)


if __name__ == "__main__":
    unittest.main()
