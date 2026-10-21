#!/usr/bin/env python3
# Options connector for the options-analyst-kit plugin: an MCP server (stdio).
# It starts with the standard library only, answers Claude Code right away, and installs yfinance, ddgs and
# beautifulsoup4 into the plugin's data folder in the background the first time it runs (see deps.py).
import contextlib
import sys

import deps
from mcp_stdio import Server

VERSION = "1.0.0"
READ_ONLY = {"readOnlyHint": True, "openWorldHint": True}
server = Server("options-analyst-kit-options", VERSION)


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


def number(description=None, **extra):
    return {"type": "number", **({"description": description} if description else {}), **extra}


def integer(description=None, **extra):
    return {"type": "integer", **({"description": description} if description else {}), **extra}


@tool("scan_cash_secured_puts", "Scan cash-secured puts",
      "Scans every S&P 500 and Nasdaq-100 stock for cash-secured puts expiring in about 2 weeks and about 4 weeks with "
      "a strike below max_strike, and returns the trades whose probability of profit is at least min_pop both by "
      "Black-Scholes (implied volatility backed out from the option's price) and historically (how often the stock "
      "stayed above the same breakeven over the same period in the last 3 years). One best trade per stock and "
      "horizon, ranked by annualized return on collateral. Takes about 2 minutes.",
      {
          "max_strike": number("Highest strike to consider, in dollars", minimum=1, maximum=1000, default=100),
          "min_pop": number("Minimum probability of profit, 0-1", minimum=0.5, maximum=0.99, default=0.80),
          "exclude_earnings": {"type": "boolean", "default": True,
                               "description": "Leave out trades with an earnings report before expiration"},
          "min_open_interest": integer("Minimum open interest per contract", minimum=0, maximum=100000, default=100),
          "max_results": integer("Trades to return per horizon", minimum=1, maximum=50, default=10),
      })
def scan_cash_secured_puts(data, max_strike, min_pop, exclude_earnings, min_open_interest, max_results):
    return data.scan(max_strike, min_pop, exclude_earnings, min_open_interest, max_results)


@tool("analyze_put", "Analyze a put",
      "One cash-secured put in depth: the contract's price, implied volatility, probabilities and returns, plus the "
      "stock's trend, support levels relative to the strike, 52-week range, fundamentals, next earnings date, "
      "Stocktwits sentiment and recent news.",
      {"symbol": string("Stock ticker"), "strike": number("Strike price"),
       "expiration": string("Expiration date, YYYY-MM-DD")},
      required=["symbol", "strike", "expiration"])
def analyze_put(data, symbol, strike, expiration):
    return data.analyze_put(symbol, strike, expiration)


@tool("get_market_overview", "Market overview",
      "Market backdrop: SPY and QQQ trend, VIX level and percentile, 10-year yield, 1-month sector returns, a regime "
      "label (risk-on / mixed / risk-off) and recent market headlines.")
def get_market_overview(data):
    return data.market_overview()


@tool("get_news", "Search news",
      "Recent news headlines from DuckDuckGo News and Google News, de-duplicated and newest first.",
      {"query": string("e.g. 'Ford stock'"), "days": integer(minimum=1, maximum=30, default=7),
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
