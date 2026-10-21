#!/usr/bin/env python3
# Market-data connector for the stock-analyst-kit plugin: an MCP server (stdio).
# It starts with the standard library only, answers Claude Code right away, and installs yfinance, ddgs and
# beautifulsoup4 into the plugin's data folder in the background the first time it runs (see deps.py).
import contextlib
import sys

import deps
from mcp_stdio import Server

VERSION = "1.0.0"
READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}
server = Server("stock-analyst-kit-market", VERSION)


def tool(name, title, description, properties=None, required=()):
    """Registers a read-only tool whose handler runs once the packages are ready, with stdout sent to stderr:
    libraries that print would otherwise corrupt the MCP stream."""

    def register(fn):
        def handler(**args):
            deps.wait()
            import data  # imported late: it needs the packages

            with contextlib.redirect_stdout(sys.stderr):
                return fn(data, **args)

        server.tool(name, description, properties, required, title=title, annotations=READ_ONLY)(handler)
        return fn

    return register


def string(description=None, **extra):
    return {"type": "string", **({"description": description} if description else {}), **extra}


def integer(description=None, **extra):
    return {"type": "integer", **({"description": description} if description else {}), **extra}


@tool("get_top_holdings", "Top ETF holdings",
      "Largest holdings of an ETF by weight, e.g. QQQ (Nasdaq-100) or SPY (S&P 500).",
      {"etf": string("ETF ticker, e.g. QQQ or SPY"), "limit": integer(minimum=1, maximum=25, default=10)},
      required=["etf"])
def get_top_holdings(data, etf, limit):
    return {"etf": etf.upper(), "holdings": data.top_holdings(etf.upper(), limit)}


@tool("get_market_overview", "Market overview",
      "Market backdrop: SPY and QQQ trend and momentum, VIX level and percentile, 10-year yield, 1-month sector "
      "returns, a regime label (risk-on / mixed / risk-off) and recent market headlines.")
def get_market_overview(data):
    return data.market_overview()


@tool("analyze_stock", "Analyze a stock",
      "One-call analysis bundle for a stock: `scores` (the backtest anchor plus rule-based points for trend, "
      "fundamentals and analysts, market regime and earnings, with the rules that fired; only news and sentiment is "
      "left to judge), technicals (trend, momentum, volatility, support/resistance), a suggested entry/target/stop, "
      "probability anchors from a 3-year backtest of hitting the target before the stop within the horizon, "
      "fundamentals, analyst targets and rating changes, next earnings date with estimates, revisions, past surprises "
      "and typical earnings moves, Stocktwits sentiment and recent news headlines. Uses completed daily closes only.",
      {
          "symbol": string("Stock ticker, e.g. NVDA. Use '-' for share classes, e.g. BRK-B"),
          "target_return": {"type": "number", "minimum": 0.01, "maximum": 0.5, "default": 0.05,
                            "description": "Target gain as a fraction (0.05 = 5%)"},
          "horizon_days": integer("Horizon in trading days (21 = about one month)", minimum=5, maximum=126, default=21),
      },
      required=["symbol"])
def analyze_stock(data, symbol, target_return, horizon_days):
    return data.analyze(symbol.upper(), target_return, horizon_days)


@tool("get_news", "Search news",
      "Recent news headlines from DuckDuckGo News and Google News, de-duplicated and newest first.",
      {"query": string("e.g. 'NVIDIA stock', 'Fed rate decision'"),
       "days": integer("How far back to look", minimum=1, maximum=30, default=7),
       "limit": integer(minimum=1, maximum=25, default=10)},
      required=["query"])
def get_news(data, query, days, limit):
    return data.news(query, days, limit)


@tool("read_article", "Read an article",
      "Fetch a web page (such as a news article from get_news) and return its main text.",
      {"url": string("The article URL"), "max_chars": integer(minimum=500, maximum=20000, default=6000)},
      required=["url"])
def read_article(data, url, max_chars):
    return data.read_article(url, max_chars)


if __name__ == "__main__":
    deps.start()
    server.run()
