# Unit tests for the rule-based confidence adjustments in server/scoring.py. No network.
# Run: python3 -m unittest discover -s tests
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
import scoring as sc  # noqa: E402


def tech(price=100, sma50=95, sma200=90, mom=0.2, rs=0.03, rsi=55, stop_pct=0.05, similar=(0.60, 200), allw=(0.55, 700)):
    return {
        "price": price,
        "trend": {"sma50": sma50, "sma200": sma200},
        "momentum": {"return_12m_ex_1m": mom, "relative_strength_vs_spy_3m": rs, "rsi14": rsi},
        "suggested_plan": {"stop_pct": stop_pct},
        "probability_anchors": {
            "similar_setups_3y": {"target_before_stop": similar[0], "samples": similar[1]},
            "all_windows_3y": {"target_before_stop": allw[0], "samples": allw[1]},
        },
    }


def earn(days=40, move=0.03, surprises=(5, 4, 3, 2), revisions=((3, 0),)):
    return {
        "days_until_next_earnings": days,
        "post_earnings_moves": {"average_abs_move": move},
        "recent_surprises": [{"surprise_pct": s} for s in surprises],
        "eps_revisions": [{"index": "0y", "upLast30days": u, "downLast30days": d} for u, d in revisions],
    }


MARKET_UP = {"spy": {"above_sma50": True, "above_sma200": True}, "vix": 15.0}


class TrendTest(unittest.TestCase):
    def test_full_uptrend_scores_plus_four(self):
        # price vs the 50-day SMA isn't scored: the anchor already conditions on it
        self.assertEqual(sc.trend_score(tech())["points"], 4)

    def test_full_downtrend_scores_minus_four_or_five(self):
        t = tech(price=80, sma50=90, sma200=95, mom=-0.1, rs=-0.05)
        self.assertEqual(sc.trend_score(t)["points"], -4)
        self.assertEqual(sc.trend_score(tech(price=80, sma50=90, sma200=95, mom=-0.1, rs=-0.05, rsi=75))["points"], -5)

    def test_overbought_rsi_costs_a_point(self):
        self.assertEqual(sc.trend_score(tech(rsi=75))["points"], 3)

    def test_missing_inputs_score_nothing(self):
        t = tech(sma50=None, sma200=None, mom=None, rs=None, rsi=None)
        self.assertEqual(sc.trend_score(t)["points"], 0)


class FundamentalsTest(unittest.TestCase):
    def test_strong_revisions_upgrades_surprise_and_upside(self):
        fund = {"analysts": {"upgrades_45d": 2, "downgrades_45d": 0, "upside_to_mean_target": 0.30}}
        s = sc.fundamentals_score(fund, earn(revisions=((9, 1),)))
        self.assertEqual(s["points"], 5)  # +2 revisions, +1 upgrades, +1 surprise, +1 upside

    def test_negative_side(self):
        fund = {"analysts": {"upgrades_45d": 0, "downgrades_45d": 3, "upside_to_mean_target": -0.05}}
        s = sc.fundamentals_score(fund, earn(surprises=(-6,), revisions=((1, 9),)))
        self.assertEqual(s["points"], -5)

    def test_tilted_revisions_score_one(self):
        s = sc.fundamentals_score({"analysts": {}}, earn(surprises=(), revisions=((3, 2),)))
        self.assertEqual(s["points"], 1)

    def test_small_surprise_is_ignored(self):
        s = sc.fundamentals_score({"analysts": {}}, earn(surprises=(1.0,), revisions=()))
        self.assertEqual(s["points"], 0)


class MarketTest(unittest.TestCase):
    def test_calm_uptrend_hits_the_cap(self):
        self.assertEqual(sc.market_score(MARKET_UP)["points"], 3)

    def test_bear_market_with_high_vix(self):
        m = {"spy": {"above_sma50": False, "above_sma200": False}, "vix": 35}
        self.assertEqual(sc.market_score(m)["points"], -5)

    def test_vix_bands(self):
        for vix, expected in [(19.9, 3), (22, 2), (27, 1), (31, 0)]:
            m = {"spy": {"above_sma50": True, "above_sma200": True}, "vix": vix}
            self.assertEqual(sc.market_score(m)["points"], expected, vix)


class EarningsTest(unittest.TestCase):
    def test_outside_horizon_is_zero(self):
        self.assertEqual(sc.earnings_score(earn(days=45), 0.05, 21)["points"], 0)

    def test_inside_with_big_move_and_no_streak(self):
        s = sc.earnings_score(earn(days=10, move=0.09, surprises=(3, -1, 2, 4)), 0.05, 21)
        self.assertEqual(s["points"], -8)  # -2 event, -6 move >= 1.5x stop

    def test_inside_with_move_near_stop_and_beat_streak(self):
        s = sc.earnings_score(earn(days=10, move=0.05, surprises=(3, 1, 2, 4)), 0.05, 21)
        self.assertEqual(s["points"], -3)  # -2 event, -3 move >= stop, +2 streak

    def test_small_move_with_streak(self):
        self.assertEqual(sc.earnings_score(earn(days=5, move=0.02), 0.05, 21)["points"], 0)  # -2 + 2


class TotalTest(unittest.TestCase):
    def test_anchor_uses_similar_setups_when_enough_samples(self):
        s = sc.score(tech(similar=(0.62, 120)), {"analysts": {}}, earn(revisions=()), MARKET_UP)
        self.assertEqual(s["anchor"], 62)
        s = sc.score(tech(similar=(0.80, 30), allw=(0.51, 700)), {"analysts": {}}, earn(revisions=()), MARKET_UP)
        self.assertEqual(s["anchor"], 51)

    def test_same_inputs_same_output(self):
        args = (tech(), {"analysts": {"upgrades_45d": 1}}, earn(days=10), MARKET_UP)
        self.assertEqual(sc.score(*args), sc.score(*args))

    def test_caps(self):
        s = sc.score(tech(similar=(0.85, 200)), {"analysts": {"upgrades_45d": 3, "upside_to_mean_target": 0.5}},
                     earn(revisions=((9, 0),)), MARKET_UP)
        self.assertLessEqual(s["confidence_before_news"], 90)
        self.assertEqual(sc.finish(s, 5), 90)
        low = sc.score(tech(similar=(0.08, 200), price=80, sma50=90, sma200=95, mom=-0.1, rs=-0.05),
                       {"analysts": {"downgrades_45d": 2, "upside_to_mean_target": -0.1}},
                       earn(days=3, move=0.2, surprises=(-5,), revisions=((0, 9),)),
                       {"spy": {"above_sma50": False, "above_sma200": False}, "vix": 40})
        self.assertEqual(low["confidence_before_news"], 5)

    def test_total_adjustment_capped_at_15(self):
        s = {"anchor": 50, "rules_total": 14}
        self.assertEqual(sc.finish(s, 5), 65)  # 14 + 5 = 19, capped to 15
        self.assertEqual(sc.finish(s, 9), 65)  # news points capped to 5 first
        self.assertEqual(sc.finish({"anchor": 50, "rules_total": -14}, -5), 35)


if __name__ == "__main__":
    unittest.main()
