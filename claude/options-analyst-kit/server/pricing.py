# Option pricing and probability math for cash-secured puts, in plain Python (no numpy), so it is easy to test.
# Black-Scholes (1973) for European options; probability of profit is the risk-neutral chance that the stock ends
# above the breakeven at expiration, the same definition brokers use. Dividends are ignored (q = 0).
import math
from statistics import NormalDist

N = NormalDist().cdf


def _d1_d2(S, K, T, r, sigma):
    d1 = (math.log(S / K) + (r + sigma * sigma / 2) * T) / (sigma * math.sqrt(T))
    return d1, d1 - sigma * math.sqrt(T)


def bs_put(S, K, T, r, sigma):
    """Black-Scholes price of a European put."""
    if T <= 0 or sigma <= 0:
        return max(K - S, 0.0)
    d1, d2 = _d1_d2(S, K, T, r, sigma)
    return K * math.exp(-r * T) * N(-d2) - S * N(-d1)


def put_delta(S, K, T, r, sigma):
    d1, _ = _d1_d2(S, K, T, r, sigma)
    return N(d1) - 1


def implied_vol(price, S, K, T, r, lo=0.01, hi=5.0, tol=1e-6):
    """Volatility that makes the Black-Scholes put price equal `price` (bisection). None if no solution exists,
    for example a price below intrinsic value or above what any volatility up to 500% gives."""
    if price is None or price <= 0 or T <= 0:
        return None
    if price < max(K * math.exp(-r * T) - S, 0) - 1e-9 or price > bs_put(S, K, T, r, hi):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if bs_put(S, K, T, r, mid) > price:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2


def prob_above(S, level, T, r, sigma):
    """Risk-neutral probability that the stock ends above `level` at T: N(d2) with K = level."""
    _, d2 = _d1_d2(S, level, T, r, sigma)
    return N(d2)


def prob_touch_below(S, level, T, r, sigma):
    """Approximate chance the stock trades at or below `level` at any time before T (reflection principle:
    about twice the chance of ending below it). Useful as an early-assignment / stress indicator."""
    return min(1.0, 2 * (1 - prob_above(S, level, T, r, sigma)))


def historical_pop(closes, horizon_days, breakeven_ratio):
    """Share of past windows of `horizon_days` trading days in which the stock ended at or above
    breakeven_ratio x its starting price (the same % cushion as the trade). Returns (rate, samples)."""
    n = wins = 0
    for i in range(len(closes) - horizon_days):
        n += 1
        wins += closes[i + horizon_days] >= closes[i] * breakeven_ratio
    return (wins / n if n else None), n


def evaluate_put(S, K, days, r, credit, closes=None):
    """Everything about selling one cash-secured put at `credit` per share, `days` calendar days to expiration."""
    T = days / 365
    sigma = implied_vol(credit, S, K, T, r)
    if sigma is None:
        return None
    breakeven = K - credit
    trading_days = max(1, round(days * 252 / 365))
    hist, samples = historical_pop(closes, trading_days, breakeven / S) if closes else (None, 0)
    ret = credit / K
    return {
        "implied_vol": round(sigma, 4),
        "delta": round(put_delta(S, K, T, r, sigma), 3),
        "breakeven": round(breakeven, 2),
        "cushion_pct": round(1 - breakeven / S, 4),
        "pop_implied": round(prob_above(S, breakeven, T, r, sigma), 4),
        "pop_historical": None if hist is None else round(hist, 4),
        "historical_samples": samples,
        "prob_touch_strike": round(prob_touch_below(S, K, T, r, sigma), 4),
        "expected_move_1sd": round(S * sigma * math.sqrt(T), 2),
        "return_on_collateral": round(ret, 4),
        "annualized_return": round(ret * 365 / days, 4),
        "collateral": round(K * 100, 2),
        "premium_received": round(credit * 100, 2),
        "max_loss": round((K - credit) * 100, 2),
        "trading_days": trading_days,
    }
