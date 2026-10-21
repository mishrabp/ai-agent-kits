# Data for the options-analyst-kit: index membership (Wikipedia via BeautifulSoup, Nasdaq's API, State Street's
# SPY file as a fallback), prices and option chains (yfinance), news (ddgs and Google News), Stocktwits, and the
# cash-secured-put scan. Everything returned is plain, JSON-friendly data. Third-party imports happen inside
# functions, after deps.wait() has made the packages available.
import datetime as dt
import io
import json
import math
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

import analysis as an
import pricing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SECTORS = {
    "XLK": "Technology", "XLC": "Communication", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLF": "Financials", "XLV": "Health Care", "XLI": "Industrials", "XLE": "Energy", "XLU": "Utilities",
    "XLB": "Materials", "XLRE": "Real Estate",
}
HORIZONS = {"2 weeks": (14, 10, 18), "4 weeks": (28, 24, 35)}  # target, min and max calendar days to expiration
_cache = {}


def cached(key, ttl, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = fn()
    _cache[key] = (time.time(), value)
    return value


def http_get(url, timeout=30, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        data = res.read()
    return data if raw else data.decode("utf-8", errors="replace")


def safe(fn, default=None):
    try:
        return fn()
    except Exception as err:  # noqa: BLE001 - one missing source shouldn't sink the whole analysis
        return default if default is not None else {"error": f"{type(err).__name__}: {str(err)[:200]}"}


def clean(v):
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


def new_york_now():
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001 - Windows has no system time-zone database; yfinance always installs pytz
        import pytz

        return dt.datetime.now(pytz.timezone("America/New_York"))


def market_is_open():
    now = new_york_now()
    return now.weekday() < 5 and (9, 30) <= (now.hour, now.minute) < (16, 0)


def completed_sessions(df):
    """Drop today's bar while the New York session is open: historical statistics use completed closes only."""
    if df.empty:
        return df
    now = new_york_now()
    if str(df.index[-1])[:10] == now.strftime("%Y-%m-%d") and (now.hour, now.minute) < (16, 15):
        return df.iloc[:-1]
    return df


# ---------------------------------------------------------------- universe

def _wikipedia_sp500():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(http_get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"), "html.parser")
    table = soup.find("table", id="constituents")
    out = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) >= 3:
            out.append({"symbol": cells[0].replace(".", "-"), "name": cells[1], "sector": cells[2]})
    if len(out) < 450:
        raise ValueError(f"Only {len(out)} rows in the Wikipedia S&P 500 table")
    return out


def _ssga_spy():
    """Fallback: State Street's daily SPY holdings spreadsheet, read with the standard library."""
    url = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
    z = zipfile.ZipFile(io.BytesIO(http_get(url, raw=True)))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    shared = [si.findtext(".//m:t", default="", namespaces=ns) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns)]
    rows = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(f"{{{ns['m']}}}row"):
        vals = []
        for c in row.findall("m:c", ns):
            v = c.findtext("m:v", default="", namespaces=ns)
            vals.append(shared[int(v)] if c.get("t") == "s" and v else v)
        rows.append(vals)
    header = next(i for i, r in enumerate(rows) if "Ticker" in r)
    col_t, col_n, col_s = rows[header].index("Ticker"), rows[header].index("Name"), rows[header].index("Sector")
    return [{"symbol": r[col_t].replace(".", "-"), "name": r[col_n], "sector": r[col_s]}
            for r in rows[header + 1:] if len(r) > col_s and r[col_t] and r[col_t] != "-" and r[col_t].isupper()]


def _nasdaq100():
    rows = json.loads(http_get("https://api.nasdaq.com/api/quote/list-type/nasdaq100"))["data"]["data"]["rows"]
    return [{"symbol": r["symbol"].replace(".", "-"), "name": r.get("companyName"), "sector": r.get("sector")} for r in rows]


def universe():
    def build():
        sources = {}
        try:
            sp, sources["sp500"] = _wikipedia_sp500(), "wikipedia"
        except Exception:  # noqa: BLE001
            sp, sources["sp500"] = _ssga_spy(), "ssga spy holdings"
        ndx = safe(_nasdaq100, [])
        sources["nasdaq100"] = "nasdaq api" if ndx else "unavailable"
        members = {}
        for row in sp:
            members[row["symbol"]] = {**row, "index": ["S&P 500"]}
        for row in ndx:
            members.setdefault(row["symbol"], {**row, "index": []})["index"].append("Nasdaq-100")
        return {"sources": sources, "sp500": len(sp), "nasdaq100": len(ndx), "members": members}

    return cached(("universe",), 6 * 3600, build)


# ---------------------------------------------------------------- prices

def batch_history(symbols):
    """3 years of completed daily closes and volumes for many symbols in one download."""
    import yfinance as yf

    def fetch():
        df = completed_sessions(yf.download(symbols, period="3y", progress=False, auto_adjust=True, threads=True))
        out = {}
        for s in symbols:
            try:
                c, v = df["Close"][s].dropna(), df["Volume"][s].dropna()
            except KeyError:
                continue
            if len(c) > 60:
                out[s] = {"close": [float(x) for x in c], "volume": [float(x) for x in v]}
        return out

    return cached(("batch", tuple(symbols)), 1800, fetch)


def risk_free_rate():
    """13-week US Treasury bill yield (^IRX), as a decimal. Falls back to 4% if unavailable."""
    import yfinance as yf

    def fetch():
        v = completed_sessions(yf.Ticker("^IRX").history(period="1mo"))["Close"].dropna()
        return round(float(v.iloc[-1]) / 100, 4) if len(v) else 0.04

    return cached(("irx",), 3600, lambda: safe(fetch, 0.04))


def next_earnings(symbol):
    import yfinance as yf

    def fetch():
        cal = clean(yf.Ticker(symbol).calendar) or {}
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        return dates[0] if dates else None

    return cached(("earnings", symbol), 6 * 3600, lambda: safe(fetch, "unknown"))


# ---------------------------------------------------------------- option chains

def _pick_expirations(expirations, today):
    picks = {}
    for label, (target, lo, hi) in HORIZONS.items():
        inside = [e for e in expirations if lo <= (dt.date.fromisoformat(e) - today).days <= hi]
        if inside:
            picks[label] = min(inside, key=lambda e: abs((dt.date.fromisoformat(e) - today).days - target))
    return picks


def _credit(row, live, now_utc):
    """Price we'd expect to sell the put for, and where it came from. None if the quote isn't usable."""
    bid, ask, last = row.get("bid") or 0, row.get("ask") or 0, row.get("lastPrice") or 0
    if bid > 0 and ask > bid:
        mid = (bid + ask) / 2
        if (ask - bid) / mid <= 0.35:
            return round(mid, 2), "bid/ask midpoint"
        return None, "spread too wide"
    if not live and last > 0:
        try:
            traded = row.get("lastTradeDate").to_pydatetime()
            if traded.tzinfo is None:
                traded = traded.replace(tzinfo=dt.timezone.utc)
            fresh = (now_utc - traded).days <= 4
        except (AttributeError, TypeError, ValueError):
            fresh = False
        if fresh:
            return round(last, 2), "last trade (market closed)"
    return None, "no usable quote"


def put_candidates(symbol, closes, max_strike, min_open_interest, min_credit=0.10, retries=3):
    """Evaluate every out-of-the-money put under max_strike for the 2- and 4-week expirations."""
    import yfinance as yf

    today = dt.date.today()
    live = market_is_open()
    now_utc = dt.datetime.now(dt.timezone.utc)
    r = risk_free_rate()
    for attempt in range(retries):
        try:
            tk = yf.Ticker(symbol)
            picks = _pick_expirations(tk.options, today)
            out = []
            for label, exp in picks.items():
                chain = tk.option_chain(exp)
                S = (getattr(chain, "underlying", None) or {}).get("regularMarketPrice") or closes[-1]
                days = (dt.date.fromisoformat(exp) - today).days
                for row in chain.puts.to_dict("records"):
                    K = row["strike"]
                    if not (K < max_strike and K < S and K >= 0.6 * S):
                        continue
                    if (row.get("openInterest") or 0) < min_open_interest:
                        continue
                    credit, source = _credit(row, live, now_utc)
                    if credit is None or credit < min_credit:
                        continue
                    ev = pricing.evaluate_put(S, K, days, r, credit, closes)
                    if ev is None:
                        continue
                    out.append({"symbol": symbol, "horizon": label, "expiration": exp, "days": days, "strike": K,
                                "price": round(S, 2), "credit": credit, "price_source": source,
                                "bid": clean(row.get("bid")), "ask": clean(row.get("ask")),
                                "open_interest": int(row.get("openInterest") or 0), "volume": clean(row.get("volume")),
                                "contract": row.get("contractSymbol"), **ev})
            return out
        except Exception:  # noqa: BLE001 - Yahoo rate-limits bursts; back off and retry
            time.sleep(1 + 2 * attempt)
    return []


# ---------------------------------------------------------------- the scan

def scan(max_strike=100, min_pop=0.80, exclude_earnings=True, min_open_interest=100, max_results=10,
         min_price=5, min_dollar_volume=25e6, workers=4):
    t0 = time.time()
    uni = universe()
    members = uni["members"]
    hist = batch_history(sorted(members))
    screened = []
    for sym, h in hist.items():
        price = h["close"][-1]
        dollar_vol = sum(c * v for c, v in zip(h["close"][-20:], h["volume"][-20:])) / 20
        if min_price <= price <= max_strike * 1.15 and dollar_vol >= min_dollar_volume:
            screened.append(sym)

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(lambda s: put_candidates(s, hist[s]["close"], max_strike, min_open_interest), screened))
    contracts = [c for rs in results for c in rs]
    passing = [c for c in contracts
               if c["pop_implied"] >= min_pop and c["pop_historical"] is not None and c["pop_historical"] >= min_pop]

    # Best contract per stock and horizon: the highest annualized return among those that pass.
    best = {}
    for c in passing:
        key = (c["symbol"], c["horizon"])
        if key not in best or c["annualized_return"] > best[key]["annualized_return"]:
            best[key] = c
    symbols = sorted({s for s, _ in best})
    with ThreadPoolExecutor(workers) as ex:
        dates = dict(zip(symbols, ex.map(next_earnings, symbols)))

    out = {}
    for label in HORIZONS:
        rows, earnings_excluded = [], []
        for (sym, lab), c in best.items():
            if lab != label:
                continue
            m = members.get(sym, {})
            ed = dates.get(sym)
            c = {**c, "name": m.get("name"), "sector": m.get("sector"), "index": m.get("index"), "next_earnings": ed,
                 "earnings_before_expiration": bool(ed and ed not in ("unknown",) and ed <= c["expiration"])}
            (earnings_excluded if exclude_earnings and c["earnings_before_expiration"] else rows).append(c)
        rows.sort(key=lambda c: c["annualized_return"], reverse=True)
        out[label] = {
            "expiration": rows[0]["expiration"] if rows else None,
            "trades": rows[:max_results],
            "more_qualifying": max(0, len(rows) - max_results),
            "excluded_for_earnings": [f"{c['symbol']} {c['strike']} put (earnings {c['next_earnings']})" for c in earnings_excluded],
        }
    return {
        "as_of": new_york_now().strftime("%Y-%m-%d %H:%M ET"),
        "market_open": market_is_open(),
        "quotes_note": ("Live bid/ask midpoints." if market_is_open() else
                        "Market closed: credits use the last trade, and implied volatility is backed out from it. "
                        "Re-check quotes when the market opens."),
        "risk_free_rate": risk_free_rate(),
        "criteria": {"strategy": "cash-secured put", "max_strike": max_strike, "min_pop": min_pop,
                     "pop_rule": "implied (Black-Scholes N(d2) at breakeven) AND historical (same cushion, same length, last 3 years) both at or above min_pop",
                     "exclude_earnings_before_expiration": exclude_earnings, "min_open_interest": min_open_interest,
                     "screen": f"price ${min_price}-${round(max_strike * 1.15)}, 20-day average dollar volume >= ${min_dollar_volume / 1e6:.0f}M"},
        "funnel": {"universe": len(members), "with_prices": len(hist), "screened": len(screened),
                   "contracts_evaluated": len(contracts), "contracts_passing_pop": len(passing),
                   "stocks_with_a_passing_contract": len({s for s, _ in best})},
        "universe_sources": uni["sources"],
        "horizons": out,
        "seconds": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------- one trade in depth

def analyze_put(symbol, strike, expiration):
    import yfinance as yf

    symbol = symbol.upper()
    h = batch_history([symbol]).get(symbol)
    if not h:
        raise ValueError(f"No price history for {symbol}")
    closes = h["close"]
    contract = None
    for c in put_candidates(symbol, closes, max_strike=strike + 0.01, min_open_interest=0, min_credit=0.01):
        if abs(c["strike"] - strike) < 1e-6 and c["expiration"] == expiration:
            contract = c
    t = yf.Ticker(symbol)
    df = completed_sessions(t.history(period="1y", auto_adjust=True))
    highs, lows = [float(x) for x in df["High"]], [float(x) for x in df["Low"]]
    cl = [float(x) for x in df["Close"]]
    price = cl[-1]
    support, _ = an.swing_levels(highs, lows, price)
    info = safe(lambda: t.info, {})
    sma50, sma200 = an.sma_series(cl, 50)[-1], an.sma_series(cl, 200)[-1]
    context = {
        "price": an.r(price), "sma50": an.r(sma50), "sma200": an.r(sma200),
        "above_sma50": price > sma50, "above_sma200": price > sma200, "rsi14": an.r(an.rsi_series(cl)[-1], 1),
        "return_1m": an.r(an.pct_change(cl, 21), 4), "return_3m": an.r(an.pct_change(cl, 63), 4),
        "atr14_pct": an.r(an.atr_series(highs, lows, cl)[-1] / price, 4),
        "support_swing_low": an.r(support), "low_52w": an.r(min(lows)), "high_52w": an.r(max(highs)),
        "strike_vs_support": an.r(strike / support - 1, 4) if support else None,
        "strike_vs_52w_low": an.r(strike / min(lows) - 1, 4),
    }
    return {
        "symbol": symbol,
        "name": info.get("shortName") if isinstance(info, dict) else None,
        "contract": contract or {"note": f"No usable quote for the {strike} put expiring {expiration}"},
        "stock": context,
        "fundamentals": {k: clean(info.get(k)) for k in ["sector", "marketCap", "trailingPE", "forwardPE", "beta",
                                                          "shortPercentOfFloat", "recommendationKey", "targetMeanPrice",
                                                          "dividendYield", "exDividendDate"]} if isinstance(info, dict) else {},
        "next_earnings": next_earnings(symbol),
        "sentiment": {
            "stocktwits": safe(lambda: stocktwits(symbol)),
            "news": safe(lambda: news(f"{(info or {}).get('shortName') or symbol} stock", days=7, limit=8)["items"], []),
        },
    }


# ---------------------------------------------------------------- news, sentiment, market

def _google_news(query, days):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{query} when:{days}d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
    root = ET.fromstring(http_get(url))
    items = []
    for it in root.iter("item"):
        pub = it.findtext("pubDate")
        # Google News links are JavaScript redirects that read_article can't follow, so they're left out.
        items.append({"title": it.findtext("title"), "source": it.findtext("source"),
                      "date": parsedate_to_datetime(pub).strftime("%Y-%m-%d") if pub else None, "via": "google_news"})
    return items


def _ddgs_news(query, days):
    from ddgs import DDGS

    limit = "d" if days <= 1 else "w" if days <= 7 else "m"
    with DDGS() as d:
        # Named explicitly so the hosts contacted are known: duckduckgo.com, bing.com, news.search.yahoo.com.
        rows = d.news(query, max_results=15, timelimit=limit, backend="duckduckgo, bing, yahoo") or []
    return [{"title": x.get("title"), "source": x.get("source"), "url": x.get("url"),
             "date": (x.get("date") or "")[:10] or None, "snippet": (x.get("body") or "")[:240], "via": "duckduckgo"}
            for x in rows]


def news(query, days=7, limit=10):
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
    tag = lambda m: ((m.get("entities") or {}).get("sentiment") or {}).get("basic")  # noqa: E731
    bull, bear = sum(tag(m) == "Bullish" for m in msgs), sum(tag(m) == "Bearish" for m in msgs)
    return {"messages_sampled": len(msgs), "bullish": bull, "bearish": bear,
            "bullish_share_of_tagged": round(bull / (bull + bear), 3) if bull + bear else None}


def read_article(url, max_chars=6000):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(http_get(url), "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else None
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = "\n".join(p for p in paras if len(p) > 40) or soup.get_text(" ", strip=True)
    return {"url": url, "title": title, "text": text[:max_chars], "truncated": len(text) > max_chars}


def market_overview():
    import yfinance as yf

    symbols = ["SPY", "QQQ", "^VIX", "^TNX", *SECTORS]
    df = cached(("overview",), 900, lambda: completed_sessions(
        yf.download(symbols, period="1y", progress=False, auto_adjust=True)["Close"]))
    out = {"as_of": str(df.index[-1])[:10], "indexes": {}, "sectors_1m": {}}
    for sym in ["SPY", "QQQ"]:
        c = [float(x) for x in df[sym].dropna()]
        s50, s200 = an.sma_series(c, 50)[-1], an.sma_series(c, 200)[-1]
        out["indexes"][sym] = {
            "price": an.r(c[-1]), "return_1w": an.r(an.pct_change(c, 5), 4), "return_1m": an.r(an.pct_change(c, 21), 4),
            "above_sma50": c[-1] > s50, "above_sma200": c[-1] > s200, "rsi14": an.r(an.rsi_series(c)[-1], 1),
            "pct_below_52w_high": an.r(c[-1] / max(c) - 1, 4),
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
    out["regime"] = "risk-on" if spy["above_sma50"] and spy["above_sma200"] and vix[-1] < 20 else (
        "risk-off" if (not spy["above_sma200"]) or vix[-1] > 28 else "mixed")
    out["headlines"] = safe(lambda: news("stock market", days=3, limit=8)["items"], [])
    return out
