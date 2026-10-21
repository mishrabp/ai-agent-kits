# Technical indicators, trade levels and probability anchors, in plain Python (no pandas), so they are easy to
# test and to read. Every series is a list of floats, oldest first.
import math
from statistics import NormalDist, mean, median, pstdev

TRADING_DAYS = 252


def _ok(values):
    return [v for v in values if v is not None and not math.isnan(v)]


def sma_series(values, n):
    out, total = [None] * len(values), 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        if i >= n - 1:
            out[i] = total / n
    return out


def ema_series(values, n):
    out, k, prev = [None] * len(values), 2 / (n + 1), None
    for i, v in enumerate(values):
        if i == n - 1:
            prev = sum(values[:n]) / n
        elif i >= n:
            prev = v * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi_series(closes, n=14):
    """Wilder's RSI."""
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_g, avg_l = sum(gains[:n]) / n, sum(losses[:n]) / n
    for i in range(n, len(closes)):
        if i > n:
            avg_g = (avg_g * (n - 1) + gains[i - 1]) / n
            avg_l = (avg_l * (n - 1) + losses[i - 1]) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def atr_series(highs, lows, closes, n=14):
    """Wilder's average true range."""
    out = [None] * len(closes)
    trs = [highs[0] - lows[0]] + [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])) for i in range(1, len(closes))
    ]
    if len(trs) < n:
        return out
    prev = sum(trs[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(trs)):
        prev = (prev * (n - 1) + trs[i]) / n
        out[i] = prev
    return out


def macd(closes, fast=12, slow=26, signal=9):
    fast_e, slow_e = ema_series(closes, fast), ema_series(closes, slow)
    line = [f - s if f is not None and s is not None else None for f, s in zip(fast_e, slow_e)]
    valid = [v for v in line if v is not None]
    sig = ema_series(valid, signal) if len(valid) >= signal else [None] * len(valid)
    m, s = line[-1], sig[-1] if sig else None
    prev_hist = (valid[-2] - sig[-2]) if len(valid) >= 2 and len(sig) >= 2 and sig[-2] is not None else None
    hist = m - s if m is not None and s is not None else None
    return {"macd": m, "signal": s, "histogram": hist, "histogram_rising": None if prev_hist is None or hist is None else hist > prev_hist}


def pct_change(values, n):
    if len(values) <= n or not values[-n - 1]:
        return None
    return values[-1] / values[-n - 1] - 1


def annual_volatility(closes, days=63):
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(max(1, len(closes) - days), len(closes))]
    return pstdev(rets) * math.sqrt(TRADING_DAYS) if len(rets) > 1 else None


def prob_touch(target_return, sigma_annual, horizon_days):
    """Driftless random-walk chance that price touches +target_return at least once within horizon_days
    (reflection principle). A volatility-only anchor: it ignores trend, news and stops."""
    if not sigma_annual:
        return None
    s = sigma_annual * math.sqrt(horizon_days / TRADING_DAYS)
    return min(1.0, 2 * (1 - NormalDist().cdf(math.log(1 + target_return) / s)))


def swing_levels(highs, lows, price, lookback=120, width=5):
    """Nearest swing low below price (support) and swing high above price (resistance) in the lookback window."""
    start = max(width, len(lows) - lookback)
    sup, res = [], []
    for i in range(start, len(lows) - width):
        window_l, window_h = lows[i - width:i + width + 1], highs[i - width:i + width + 1]
        if lows[i] == min(window_l) and lows[i] < price:
            sup.append(lows[i])
        if highs[i] == max(window_h) and highs[i] > price:
            res.append(highs[i])
    return (max(sup) if sup else None), (min(res) if res else None)


def backtest_target_before_stop(highs, lows, closes, atrs, target=0.05, horizon=21, stop_atr=1.5,
                                stop_floor=0.03, stop_cap=0.10, mask=None):
    """For every past day (optionally only where mask[i] is True), buy at the close and see what happened over the
    next `horizon` days: did the high reach close*(1+target) before the low hit the stop? A day that touches both
    counts as a stop (conservative). Returns the win rate and how often the target was merely touched."""
    wins = touches = closes_above = n = 0
    drawdowns = []
    for i in range(len(closes) - horizon - 1):
        if atrs[i] is None or (mask is not None and not mask[i]):
            continue
        entry = closes[i]
        stop_pct = min(max(stop_atr * atrs[i] / entry, stop_floor), stop_cap)
        tgt, stp = entry * (1 + target), entry * (1 - stop_pct)
        outcome, touched, worst = None, False, entry
        for j in range(i + 1, i + horizon + 1):
            worst = min(worst, lows[j])
            if highs[j] >= tgt:
                touched = True
            if outcome is None:
                if lows[j] <= stp:
                    outcome = "stop"
                elif highs[j] >= tgt:
                    outcome = "win"
        n += 1
        wins += outcome == "win"
        touches += touched
        closes_above += closes[i + horizon] >= tgt
        drawdowns.append(worst / entry - 1)
    if not n:
        return {"samples": 0}
    return {
        "samples": n,
        "target_before_stop": wins / n,
        "touched_target": touches / n,
        "closed_above_target_at_horizon": closes_above / n,
        "median_max_drawdown": median(drawdowns),
    }


def r(x, nd=2):
    return None if x is None else round(x, nd)


def technical_summary(dates, opens, highs, lows, closes, volumes, bench_closes=None, target=0.05, horizon=21):
    """Everything the analyst needs from price history, plus probability anchors for `target` within `horizon`."""
    price = closes[-1]
    sma20, sma50, sma200 = sma_series(closes, 20), sma_series(closes, 50), sma_series(closes, 200)
    rsi = rsi_series(closes)
    atr = atr_series(highs, lows, closes)
    m = macd(closes)
    sd20 = pstdev(closes[-20:]) if len(closes) >= 20 else None
    bb_pct_b = (price - (sma20[-1] - 2 * sd20)) / (4 * sd20) if sd20 else None
    vol = annual_volatility(closes)
    support, resistance = swing_levels(highs, lows, price)
    hi52, lo52 = max(highs[-TRADING_DAYS:]), min(lows[-TRADING_DAYS:])
    vol20, vol50 = mean(volumes[-20:]), mean(volumes[-50:])

    # Probability anchors: all past windows, and only windows that started in a state like today's.
    above50_now, rsi_now = price > (sma50[-1] or 0), rsi[-1]
    mask = [
        sma50[i] is not None and rsi[i] is not None and (closes[i] > sma50[i]) == above50_now and abs(rsi[i] - rsi_now) <= 10
        for i in range(len(closes))
    ]
    all_windows = backtest_target_before_stop(highs, lows, closes, atr, target, horizon)
    similar = backtest_target_before_stop(highs, lows, closes, atr, target, horizon, mask=mask)

    stop_pct = min(max(1.5 * atr[-1] / price, 0.03), 0.10)
    rel_strength = None
    if bench_closes and len(bench_closes) > 63:
        rel_strength = (pct_change(closes, 63) or 0) - (pct_change(bench_closes, 63) or 0)

    return {
        "as_of": dates[-1],
        "price": r(price),
        "trend": {
            "sma20": r(sma20[-1]), "sma50": r(sma50[-1]), "sma200": r(sma200[-1]),
            "above_sma20": price > sma20[-1], "above_sma50": above50_now,
            "above_sma200": sma200[-1] is not None and price > sma200[-1],
            "sma50_above_sma200": sma200[-1] is not None and sma50[-1] > sma200[-1],
        },
        "momentum": {
            "rsi14": r(rsi_now, 1),
            "macd_histogram": r(m["histogram"], 3), "macd_histogram_rising": m["histogram_rising"],
            "bollinger_pct_b": r(bb_pct_b),
            "return_1w": r(pct_change(closes, 5), 4), "return_1m": r(pct_change(closes, 21), 4),
            "return_3m": r(pct_change(closes, 63), 4), "return_6m": r(pct_change(closes, 126), 4),
            "relative_strength_vs_spy_3m": r(rel_strength, 4),
        },
        "volatility": {
            "atr14": r(atr[-1]), "atr14_pct": r(atr[-1] / price, 4), "annualized_vol_3m": r(vol, 4),
            "volume_20d_vs_50d": r(vol20 / vol50 if vol50 else None),
        },
        "levels": {
            "support_swing_low": r(support), "resistance_swing_high": r(resistance),
            "low_20d": r(min(lows[-20:])), "high_20d": r(max(highs[-20:])),
            "high_52w": r(hi52), "low_52w": r(lo52), "pct_below_52w_high": r(price / hi52 - 1, 4),
        },
        "suggested_plan": {
            "entry_zone": [r(max(price - 0.5 * atr[-1], support or 0)), r(price)],
            "target_price_for_5pct_from_last_close": r(price * (1 + target)),
            "stop_price": r(price * (1 - stop_pct)), "stop_pct": r(stop_pct, 4),
            "note": "Stop = 1.5 x ATR14, kept between 3% and 10%. The backtests below use the same rule.",
        },
        "probability_anchors": {
            "definition": f"Buy at the close; win = high reaches +{target:.0%} before the low hits the stop, within {horizon} trading days.",
            "volatility_model_touch": r(prob_touch(target, vol, horizon), 3),
            "all_windows_3y": {k: r(v, 3) for k, v in all_windows.items()},
            "similar_setups_3y": {k: r(v, 3) for k, v in similar.items()},
            "similar_setup_rule": f"same side of SMA50 as today and RSI14 within +/-10 of {rsi_now:.0f}",
        },
    }


def post_earnings_moves(dates, closes, earnings_dates, limit=8):
    """Absolute close-to-close move across each past earnings date, using the date strings (YYYY-MM-DD)."""
    moves = []
    for ed in sorted(earnings_dates, reverse=True):
        idx = next((i for i, d in enumerate(dates) if d >= ed), None)
        if idx is None or idx < 1 or idx + 1 >= len(dates):
            continue
        # Report after the close moves the next session; before the open moves the same session. Take the larger.
        move = max(abs(closes[idx] / closes[idx - 1] - 1), abs(closes[idx + 1] / closes[idx] - 1))
        moves.append(move)
        if len(moves) >= limit:
            break
    return {"count": len(moves), "average_abs_move": r(mean(moves), 4) if moves else None,
            "max_abs_move": r(max(moves), 4) if moves else None}
