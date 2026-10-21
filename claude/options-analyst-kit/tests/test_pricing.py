# Unit tests for server/pricing.py: Black-Scholes, implied volatility, probability of profit. No network.
# Run: python3 -m unittest discover -s tests
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import pricing as p  # noqa: E402


class BlackScholesTest(unittest.TestCase):
    def test_textbook_value(self):
        # Hull's classic example: S=K=100, T=1, r=5%, sigma=20% -> put 5.5735
        self.assertAlmostEqual(p.bs_put(100, 100, 1, 0.05, 0.20), 5.5735, places=3)

    def test_put_call_parity(self):
        S, K, T, r, s = 50, 45, 0.25, 0.04, 0.35
        d1 = (math.log(S / K) + (r + s * s / 2) * T) / (s * math.sqrt(T))
        call = S * p.N(d1) - K * math.exp(-r * T) * p.N(d1 - s * math.sqrt(T))
        self.assertAlmostEqual(call - p.bs_put(S, K, T, r, s), S - K * math.exp(-r * T), places=8)

    def test_delta_range(self):
        self.assertTrue(-0.5 < p.put_delta(100, 90, 0.1, 0.04, 0.3) < 0)
        self.assertLess(p.put_delta(100, 110, 0.1, 0.04, 0.3), -0.5)


class ImpliedVolTest(unittest.TestCase):
    def test_round_trip(self):
        for sigma in (0.15, 0.4, 0.9):
            price = p.bs_put(30, 27, 28 / 365, 0.04, sigma)
            self.assertAlmostEqual(p.implied_vol(price, 30, 27, 28 / 365, 0.04), sigma, places=4)

    def test_impossible_prices(self):
        self.assertIsNone(p.implied_vol(0, 30, 27, 0.1, 0.04))
        self.assertIsNone(p.implied_vol(1.0, 20, 30, 0.1, 0.04))  # below intrinsic value (about 10)
        self.assertIsNone(p.implied_vol(29.0, 30, 27, 0.1, 0.04))  # more than any volatility can explain


class ProbabilityTest(unittest.TestCase):
    def test_prob_above_behaves(self):
        far, near = p.prob_above(100, 80, 28 / 365, 0.04, 0.3), p.prob_above(100, 98, 28 / 365, 0.04, 0.3)
        self.assertGreater(far, near)
        self.assertGreater(far, 0.95)
        self.assertAlmostEqual(p.prob_above(100, 100, 1e-9, 0.0, 0.3), 0.5, places=2)

    def test_touch_is_at_least_end_probability(self):
        end_below = 1 - p.prob_above(100, 90, 28 / 365, 0.04, 0.3)
        self.assertGreaterEqual(p.prob_touch_below(100, 90, 28 / 365, 0.04, 0.3), end_below)

    def test_historical_pop(self):
        rising = [100 * 1.001 ** i for i in range(300)]
        self.assertEqual(p.historical_pop(rising, 20, 0.95)[0], 1.0)
        falling = [100 * 0.99 ** i for i in range(300)]
        self.assertEqual(p.historical_pop(falling, 20, 0.95)[0], 0.0)


class EvaluateTest(unittest.TestCase):
    def test_evaluate_put_fields(self):
        credit = p.bs_put(50, 45, 28 / 365, 0.04, 0.30)
        e = p.evaluate_put(50, 45, 28, 0.04, credit, closes=[50 * 1.0005 ** i for i in range(800)])
        self.assertAlmostEqual(e["implied_vol"], 0.30, places=3)
        self.assertAlmostEqual(e["breakeven"], round(45 - credit, 2))
        self.assertGreater(e["pop_implied"], 0.85)
        self.assertEqual(e["pop_historical"], 1.0)
        self.assertEqual(e["collateral"], 4500)
        self.assertAlmostEqual(e["annualized_return"], round(credit / 45 * 365 / 28, 4))

    def test_unpriceable_put_is_skipped(self):
        self.assertIsNone(p.evaluate_put(50, 45, 28, 0.04, 0.0))


if __name__ == "__main__":
    unittest.main()
