# Rule-based confidence adjustments. The same data always produces the same points, so two runs on the same
# prices agree. Every rule is a published, widely used signal; the references are in the README
# ("How the confidence is computed"). Only the news-and-sentiment adjustment is left to the analyst's judgment.
# Inputs are the plain dictionaries that data.analyze() builds; nothing here touches the network.

TOTAL_CAP = 15
CONFIDENCE_FLOOR, CONFIDENCE_CAP = 5, 90
NEWS_RANGE = (-5, 5)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _component(points, lo, hi, reasons):
    return {"points": clamp(points, lo, hi), "range": [lo, hi], "rules": reasons}


def trend_score(tech):
    """Trend and momentum, -5..+5: one point per rule, for or against."""
    t, m, price = tech["trend"], tech["momentum"], tech["price"]
    pts, why = 0, []

    def rule(cond_up, cond_down, up, down):
        nonlocal pts
        if cond_up:
            pts += 1
            why.append(f"+1 {up}")
        elif cond_down:
            pts -= 1
            why.append(f"-1 {down}")

    # Price vs the 50-day SMA is not scored here: the backtest anchor already uses only past days on the same side
    # of the 50-day SMA as today, so scoring it again would count it twice.
    sma50, sma200 = t.get("sma50"), t.get("sma200")
    if sma200 is not None:  # Faber (2007): long-term trend filter
        rule(price > sma200, price <= sma200, f"price above 200-day SMA ({sma200})", f"price below 200-day SMA ({sma200})")
    if sma50 is not None and sma200 is not None:  # golden cross / death cross
        rule(sma50 > sma200, sma50 <= sma200, "50-day SMA above 200-day (golden cross)", "50-day SMA below 200-day (death cross)")
    mom = m.get("return_12m_ex_1m")
    if mom is not None:  # Moskowitz, Ooi & Pedersen (2012): time-series momentum
        rule(mom > 0, mom <= 0, f"12-1 month return {mom:+.1%} (time-series momentum)", f"12-1 month return {mom:+.1%} (time-series momentum)")
    rs = m.get("relative_strength_vs_spy_3m")
    if rs is not None:  # Jegadeesh & Titman (1993): relative momentum
        rule(rs > 0, rs <= 0, f"3-month return beats SPY by {rs:+.1%}", f"3-month return trails SPY by {rs:+.1%}")
    rsi = m.get("rsi14")
    if rsi is not None and rsi > 70:  # Wilder (1978): overbought
        pts -= 1
        why.append(f"-1 RSI {rsi} above 70 (overbought)")
    return _component(pts, -5, 5, why)


def fundamentals_score(fund, earn):
    """Fundamentals and analysts, -5..+5: estimate revisions, rating changes, last surprise, target upside."""
    pts, why = 0, []
    an = (fund or {}).get("analysts") or {}

    # Chan, Jegadeesh & Lakonishok (1996): analyst estimate revisions predict returns. Current fiscal year
    # and next quarter, last 30 days. +-2 when clearly one-sided, +-1 when tilted.
    up = down = 0
    for row in (earn or {}).get("eps_revisions") or []:
        if row.get("index") in ("0q", "+1q", "0y"):
            up += row.get("upLast30days") or 0
            down += row.get("downLast30days") or 0
    if up + down:
        share = up / (up + down)
        p = 2 if share >= 0.75 else 1 if share > 0.5 else -2 if share <= 0.25 else -1 if share < 0.5 else 0
        if p:
            pts += p
            why.append(f"{p:+d} EPS revisions in 30 days: {up} up, {down} down")

    # Womack (1996): recommendation changes carry information.
    ups, downs = an.get("upgrades_45d") or 0, an.get("downgrades_45d") or 0
    if ups != downs:
        p = 1 if ups > downs else -1
        pts += p
        why.append(f"{p:+d} {ups} upgrades vs {downs} downgrades in 45 days")

    # Bernard & Thomas (1989): post-earnings-announcement drift follows the last surprise.
    surprises = [s.get("surprise_pct") for s in (earn or {}).get("recent_surprises") or [] if s.get("surprise_pct") is not None]
    if surprises:
        last = surprises[0]
        if abs(last) >= 2:
            p = 1 if last > 0 else -1
            pts += p
            why.append(f"{p:+d} last EPS surprise {last:+.1f}% (post-earnings drift)")

    # Brav & Lehavy (2003): price targets carry modest information.
    upside = an.get("upside_to_mean_target")
    if upside is not None:
        if upside >= 0.15:
            pts += 1
            why.append(f"+1 mean analyst target {upside:+.0%} above price")
        elif upside < 0:
            pts -= 1
            why.append(f"-1 mean analyst target {upside:+.0%} below price")
    return _component(pts, -5, 5, why)


def market_score(market):
    """Market regime, -5..+3: SPY trend (Faber 2007) and the VIX band."""
    pts, why = 0, []
    spy = (market or {}).get("spy") or {}
    if spy.get("above_sma200") is not None:
        if spy["above_sma200"]:
            pts += 1
            why.append("+1 SPY above its 200-day SMA")
        else:
            pts -= 2
            why.append("-2 SPY below its 200-day SMA")
    if spy.get("above_sma50") is not None:
        if spy["above_sma50"]:
            pts += 1
            why.append("+1 SPY above its 50-day SMA")
        else:
            pts -= 1
            why.append("-1 SPY below its 50-day SMA")
    vix = (market or {}).get("vix")
    if vix is not None:
        p = 1 if vix < 20 else 0 if vix < 25 else -1 if vix < 30 else -2
        if p:
            pts += p
        why.append(f"{p:+d} VIX {vix:.1f}" + (" (calm)" if p > 0 else " (elevated)" if p < 0 else " (normal)"))
    return _component(pts, -5, 3, why)


def earnings_score(earn, stop_pct, horizon_days):
    """Earnings inside the horizon, -10..+3: event risk measured against the stop, eased by a beat streak."""
    days = (earn or {}).get("days_until_next_earnings")
    horizon_calendar = round(horizon_days * 7 / 5)
    if days is None:
        return _component(0, -10, 3, ["0 next earnings date unknown"])
    if days < 0 or days > horizon_calendar:
        return _component(0, -10, 3, [f"0 next report in {days} days, outside the horizon"])
    pts, why = -2, [f"-2 earnings report in {days} days, inside the horizon"]
    move = ((earn or {}).get("post_earnings_moves") or {}).get("average_abs_move")
    if move is not None and stop_pct:
        if move >= 1.5 * stop_pct:
            pts -= 6
            why.append(f"-6 typical earnings move {move:.1%} is at least 1.5x the {stop_pct:.1%} stop")
        elif move >= stop_pct:
            pts -= 3
            why.append(f"-3 typical earnings move {move:.1%} is at least the {stop_pct:.1%} stop")
    surprises = [s.get("surprise_pct") for s in (earn or {}).get("recent_surprises") or [] if s.get("surprise_pct") is not None]
    if len(surprises) >= 4 and all(s > 0 for s in surprises[:4]):
        pts += 2
        why.append("+2 beat estimates in each of the last 4 quarters")
    return _component(pts, -10, 3, why)


def score(tech, fund, earn, market, horizon_days=21):
    """Anchor plus the rule-based adjustments. The analyst adds only the news-and-sentiment points."""
    pa = tech["probability_anchors"]
    similar, everything = pa["similar_setups_3y"], pa["all_windows_3y"]
    use_similar = (similar.get("samples") or 0) >= 60
    source = similar if use_similar else everything
    anchor = round(100 * (source.get("target_before_stop") or 0))

    parts = {
        "trend_and_momentum": trend_score(tech),
        "fundamentals_and_analysts": fundamentals_score(fund, earn),
        "market_regime": market_score(market),
        "earnings_inside_horizon": earnings_score(earn, tech["suggested_plan"]["stop_pct"], horizon_days),
    }
    rules_total = sum(p["points"] for p in parts.values())
    return {
        "anchor": anchor,
        "anchor_source": f"{'similar setups' if use_similar else 'all windows'}, n={source.get('samples')}",
        "components": parts,
        "rules_total": rules_total,
        "confidence_before_news": clamp(anchor + clamp(rules_total, -TOTAL_CAP, TOTAL_CAP), CONFIDENCE_FLOOR, CONFIDENCE_CAP),
        "news_points_allowed": list(NEWS_RANGE),
        "how_to_finish": (
            "confidence = anchor + clamp(rules_total + news_points, -15, +15), then kept between 5 and 90. "
            "news_points is the only judgment: 0 unless a dated headline from the last 7 days is material."
        ),
    }


def finish(scored, news_points):
    """Final confidence once the analyst has chosen the news-and-sentiment points."""
    news_points = clamp(news_points, *NEWS_RANGE)
    total = clamp(scored["rules_total"] + news_points, -TOTAL_CAP, TOTAL_CAP)
    return clamp(scored["anchor"] + total, CONFIDENCE_FLOOR, CONFIDENCE_CAP)
