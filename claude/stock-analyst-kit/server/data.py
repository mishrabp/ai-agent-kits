# Fetches market data: yfinance (prices, fundamentals, earnings, analysts, ETF holdings), ddgs and Google News
# (news), Stocktwits (retail sentiment) and BeautifulSoup (reading articles). Everything returned is plain,
# JSON-friendly data. Third-party imports happen inside functions, after deps.wait() has made them available.
import datetime as dt
import json
import math
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import analysis as an

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SECTORS = {
    "XLK": "Technology", "XLC": "Communication", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLF": "Financials", "XLV": "Health Care", "XLI": "Industrials", "XLE": "Energy", "XLU": "Utilities",
    "XLB": "Materials", "XLRE": "Real Estate",
}
_cache = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def clean(v):
    """Convert numpy/pandas values to plain JSON types."""
    if v is None:
        return None
    if hasattr(v, "item") and not isinstance(v, (list, dict, str)):
        try:
            v = v.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 4)
    if isinstance(v, (dt.date, dt.datetime)) or type(v).__name__ == "Timestamp":
        return str(v)[:10]
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    return v


def frame_records(df, limit=None):
    if df is None or getattr(df, "empty", True):
        return []
    df = df.head(limit) if limit else df
    return [clean({"index": str(i)[:10], **row}) for i, row in zip(df.index, df.to_dict("records"))]


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", errors="replace")


def safe(fn, default=None):
    try:
        return fn()
    except Exception as err:  # noqa: BLE001 - one missing source shouldn't sink the whole analysis
        return default if default is not None else {"error": f"{type(err).__name__}: {str(err)[:200]}"}


# ---------------------------------------------------------------- prices and holdings

def history(symbol, period="3y"):
    import yfinance as yf

    def fetch():
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if df.empty:
            raise ValueError(f"No price history for {symbol}")
        return {
            "dates": [str(i)[:10] for i in df.index],
            "open": [float(x) for x in df["Open"]], "high": [float(x) for x in df["High"]],
            "low": [float(x) for x in df["Low"]], "close": [float(x) for x in df["Close"]],
            "volume": [float(x) for x in df["Volume"]],
        }

    return cached(("hist", symbol, period), 900, fetch)


def top_holdings(etf, limit=10):
    import yfinance as yf

    df = cached(("holdings", etf), 3600, lambda: yf.Ticker(etf).funds_data.top_holdings)
    rows = []
    for sym, row in df.head(limit).iterrows():
        rows.append({"symbol": str(sym).replace(".", "-"), "name": row.get("Name"), "weight": clean(row.get("Holding Percent"))})
    return rows


# ---------------------------------------------------------------- fundamentals, analysts, earnings

INFO_FIELDS = {
    "valuation": ["marketCap", "trailingPE", "forwardPE", "pegRatio", "priceToSalesTrailing12Months", "enterpriseToEbitda", "priceToBook"],
    "growth_and_quality": ["revenueGrowth", "earningsGrowth", "earningsQuarterlyGrowth", "grossMargins", "operatingMargins",
                           "profitMargins", "returnOnEquity", "freeCashflow", "debtToEquity", "currentRatio"],
    "risk": ["beta", "shortPercentOfFloat", "shortRatio", "heldPercentInstitutions"],
    "analysts": ["recommendationKey", "recommendationMean", "numberOfAnalystOpinions", "targetMeanPrice",
                 "targetMedianPrice", "targetHighPrice", "targetLowPrice"],
}


def fundamentals(symbol):
    import yfinance as yf

    t = yf.Ticker(symbol)
    info = cached(("info", symbol), 1800, lambda: t.info) or {}
    out = {"name": info.get("shortName"), "sector": info.get("sector"), "industry": info.get("industry")}
    for group, keys in INFO_FIELDS.items():
        out[group] = {k: clean(info.get(k)) for k in keys}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price and info.get("targetMeanPrice"):
        out["analysts"]["upside_to_mean_target"] = round(info["targetMeanPrice"] / price - 1, 4)
    out["analysts"]["recommendation_trend"] = safe(lambda: [
        {k: v for k, v in rec.items() if k != "index"} for rec in frame_records(t.recommendations, 2)
    ], [])
    cutoff = (dt.datetime.now() - dt.timedelta(days=45)).strftime("%Y-%m-%d")
    out["analysts"]["rating_changes_last_45d"] = safe(lambda: [
        f"{rec['index']} {rec.get('Firm')}: {rec.get('FromGrade') or '-'} -> {rec.get('ToGrade')} ({rec.get('Action')})"
        + (f", target {rec.get('priorPriceTarget')} -> {rec.get('currentPriceTarget')}" if rec.get("currentPriceTarget") else "")
        for rec in frame_records(t.upgrades_downgrades, 25) if rec["index"] >= cutoff
    ][:10], [])
    return out


def earnings(symbol, hist=None):
    import yfinance as yf

    t = yf.Ticker(symbol)
    cal = safe(lambda: clean(t.calendar), {})
    next_dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
    next_date = next_dates[0] if next_dates else None
    days_until = (dt.date.fromisoformat(next_date) - dt.date.today()).days if next_date else None
    ed = safe(lambda: t.get_earnings_dates(limit=12), None)
    past = []
    if ed is not None and not isinstance(ed, dict) and not ed.empty:
        for idx, row in ed.iterrows():
            if row.get("Reported EPS") is not None and not math.isnan(row.get("Reported EPS")):
                past.append({"date": str(idx)[:10], "eps_estimate": clean(row.get("EPS Estimate")),
                             "eps_reported": clean(row.get("Reported EPS")), "surprise_pct": clean(row.get("Surprise(%)"))})
    out = {
        "next_earnings_date": next_date,
        "days_until_next_earnings": days_until,
        "within_next_month": days_until is not None and 0 <= days_until <= 31,
        "next_quarter_estimates": {k: cal.get(k) for k in ["Earnings Average", "Earnings Low", "Earnings High",
                                                         "Revenue Average", "Revenue Low", "Revenue High"]} if isinstance(cal, dict) else {},
        "eps_estimate_trend": safe(lambda: frame_records(t.eps_trend), []),
        "eps_revisions": safe(lambda: frame_records(t.eps_revisions), []),
        "recent_surprises": past[:4],
    }
    if hist and past:
        out["post_earnings_moves"] = an.post_earnings_moves(hist["dates"], hist["close"], [p["date"] for p in past])
    return out


# ---------------------------------------------------------------- news and sentiment

def _google_news(query, days):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(http_get(url))
    items = []
    for it in root.iter("item"):
        pub = it.findtext("pubDate")
        # Google News links are long JavaScript redirects that read_article can't follow, so they're left out.
        items.append({
            "title": it.findtext("title"), "source": it.findtext("source"),
            "date": parsedate_to_datetime(pub).strftime("%Y-%m-%d") if pub else None, "via": "google_news",
        })
    return items


def _ddgs_news(query, days):
    from ddgs import DDGS

    limit = "d" if days <= 1 else "w" if days <= 7 else "m"
    with DDGS() as d:
        rows = d.news(query, max_results=15, timelimit=limit) or []
    return [{"title": x.get("title"), "source": x.get("source"), "url": x.get("url"),
             "date": (x.get("date") or "")[:10] or None, "snippet": (x.get("body") or "")[:240], "via": "duckduckgo"}
            for x in rows]


def news(query, days=7, limit=10):
    """Recent headlines from DuckDuckGo news and Google News, de-duplicated, newest first."""
    seen, out, errors = set(), [], []
    for source in (_ddgs_news, _google_news):
        try:
            for item in source(query, days):
                key = (item["title"] or "").lower()[:80]
                if key and key not in seen:
                    seen.add(key)
                    out.append(item)
        except Exception as err:  # noqa: BLE001
            errors.append(f"{source.__name__}: {type(err).__name__}")
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return {"query": query, "items": out[:limit], **({"source_errors": errors} if errors else {})}


def stocktwits(symbol):
    data = json.loads(http_get(f"https://api.stocktwits.com/api/2/streams/symbol/{urllib.parse.quote(symbol)}.json"))
    msgs = data.get("messages", [])
    bull = sum(1 for m in msgs if ((m.get("entities") or {}).get("sentiment") or {}).get("basic") == "Bullish")
    bear = sum(1 for m in msgs if ((m.get("entities") or {}).get("sentiment") or {}).get("basic") == "Bearish")
    return {"messages_sampled": len(msgs), "bullish": bull, "bearish": bear,
            "bullish_share_of_tagged": round(bull / (bull + bear), 3) if bull + bear else None,
            "watchers": (data.get("symbol") or {}).get("watchlist_count")}


def read_article(url, max_chars=6000):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(http_get(url), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else None
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paras if len(p) > 40) or soup.get_text(" ", strip=True)
    return {"url": url, "title": title, "text": text[:max_chars], "truncated": len(text) > max_chars}


# ---------------------------------------------------------------- market overview

def market_overview():
    import yfinance as yf

    symbols = ["SPY", "QQQ", "^VIX", "^TNX", *SECTORS]
    df = cached(("overview",), 900, lambda: yf.download(symbols, period="1y", progress=False, auto_adjust=True)["Close"])
    out = {"as_of": str(df.index[-1])[:10], "indexes": {}, "sectors_1m": {}}
    for sym in ["SPY", "QQQ"]:
        c = [float(x) for x in df[sym].dropna()]
        s50, s200 = an.sma_series(c, 50)[-1], an.sma_series(c, 200)[-1]
        out["indexes"][sym] = {
            "price": an.r(c[-1]), "return_1w": an.r(an.pct_change(c, 5), 4), "return_1m": an.r(an.pct_change(c, 21), 4),
            "return_3m": an.r(an.pct_change(c, 63), 4), "above_sma50": c[-1] > s50, "above_sma200": c[-1] > s200,
            "rsi14": an.r(an.rsi_series(c)[-1], 1), "pct_below_52w_high": an.r(c[-1] / max(c) - 1, 4),
        }
    vix = [float(x) for x in df["^VIX"].dropna()]
    out["vix"] = {"level": an.r(vix[-1]), "change_1m": an.r(an.pct_change(vix, 21), 4),
                  "percentile_1y": an.r(sum(v <= vix[-1] for v in vix) / len(vix), 2)}
    tnx = [float(x) for x in df["^TNX"].dropna()]
    out["ten_year_yield_pct"] = {"level": an.r(tnx[-1]), "change_1m": an.r(tnx[-1] - tnx[-22], 2) if len(tnx) > 22 else None}
    for sym, name in SECTORS.items():
        c = [float(x) for x in df[sym].dropna()]
        out["sectors_1m"][name] = an.r(an.pct_change(c, 21), 4)
    spy = out["indexes"]["SPY"]
    regime = "risk-on" if spy["above_sma50"] and spy["above_sma200"] and vix[-1] < 20 else (
        "risk-off" if (not spy["above_sma200"]) or vix[-1] > 28 else "mixed")
    out["regime"] = regime
    out["headlines"] = safe(lambda: news("stock market", days=3, limit=10)["items"], [])
    return out


# ---------------------------------------------------------------- one-call stock bundle

def analyze(symbol, target=0.05, horizon=21):
    hist = history(symbol)
    spy = safe(lambda: history("SPY"), None)
    tech = an.technical_summary(hist["dates"], hist["open"], hist["high"], hist["low"], hist["close"], hist["volume"],
                                bench_closes=spy["close"] if isinstance(spy, dict) and "close" in spy else None,
                                target=target, horizon=horizon)
    fund = safe(lambda: fundamentals(symbol))
    name = fund.get("name") if isinstance(fund, dict) else None
    return {
        "symbol": symbol,
        "name": name,
        "technicals": tech,
        "fundamentals": fund,
        "earnings": safe(lambda: earnings(symbol, hist)),
        "sentiment": {
            "stocktwits": safe(lambda: stocktwits(symbol)),
            "news": safe(lambda: news(f"{name or symbol} stock", days=7, limit=8)["items"], []),
        },
    }
