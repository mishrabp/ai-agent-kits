# stock-analyst-kit

A Claude Code plugin that analyzes the **top 10 holdings of QQQ (Nasdaq-100) and SPY (S&P 500)** and reports which
stocks could gain **5% or more within a month with 80% or higher confidence**, with an entry price, exit price, stop,
time horizon and an explanation of every confidence level.

```text
/stock-analyst-kit:stock-report
/stock-analyst-kit:stock-report TSLA PLTR target=7% confidence=70%
```

For each stock it looks at:

| Area | What it uses |
|---|---|
| Technicals | Trend vs SMA20/50/200, RSI, MACD, Bollinger %B, ATR, relative strength vs SPY, support and resistance, 52-week range |
| Fundamentals | Valuation (P/E, forward P/E, PEG, EV/EBITDA), growth, margins, ROE, free cash flow, debt, short interest |
| Analysts | Mean and median price targets, upside, recommendation trend, upgrades, downgrades and target changes in the last 45 days |
| Earnings | Next earnings date and whether it falls inside the horizon, EPS and revenue estimates, estimate revisions, the last 4 surprises, the typical earnings-day move |
| Sentiment and news | Headlines from DuckDuckGo News and Google News, articles read on demand, Stocktwits bullish/bearish mix |
| Market | SPY and QQQ trend, VIX level and percentile, 10-year yield, sector returns, market headlines, a risk-on / mixed / risk-off label |

## How the confidence is computed

A confidence level is only useful if it means something you can check, so the kit doesn't let the model make it up.

1. **Anchor from a backtest.** For each stock the server replays the last 3 years: on every day that looked like today
   (same side of the 50-day average, RSI within 10 points), it buys at the close and checks whether the price reached
   +5% **before** hitting a stop of 1.5 x ATR (3-10%) within 21 trading days. That hit rate is the anchor. A day that
   touches both counts as a loss.
2. **Adjustments, at most 15 points in total**, each tied to a number or a headline: trend and momentum, fundamentals
   and analysts, sentiment and news, the market regime, and an earnings report inside the horizon (usually a penalty,
   because an earnings move can be bigger than the stop).
3. **Confidence = anchor + adjustments**, never above 90%. A stock qualifies only if its exit is at least 5% above its
   entry and its confidence is at least 80%.

The report shows the anchor and each adjustment for every stock. Expect few or no qualifying stocks on many days: a
large, steady company like Apple rarely gains 5% in a month before falling 3%, and the report says so instead of
stretching the numbers. This is research software, not financial advice.

## What's in it

| Piece | File | What it does |
|---|---|---|
| **Connector** (MCP server `market`) | `server/stock_mcp.py`, `server/data.py`, `server/analysis.py`, `server/deps.py`, `server/mcp_stdio.py` | Five read-only tools: `get_top_holdings`, `get_market_overview`, `analyze_stock`, `get_news`, `read_article` |
| **Agent** | `agents/equity-analyst.md` | Analyzes a batch of tickers with the confidence rules above and returns a fixed-format block per stock |
| **Skill** | `skills/stock-report/SKILL.md` | `/stock-analyst-kit:stock-report`: builds the universe, reads the market, runs analysts in parallel, checks their arithmetic, writes the report |

Data comes from **yfinance** (Yahoo Finance prices, fundamentals, earnings, analysts and ETF holdings), **ddgs**
(DuckDuckGo news search), Google News RSS, Stocktwits and **BeautifulSoup** (reading articles). No API keys.

### Python packages install themselves

You need `python3` 3.9 or newer and either [`uv`](https://docs.astral.sh/uv/) or `pip` for that Python. Claude Code
installs plugins without running an install step, so the first time the server starts it installs `yfinance`, `ddgs`
and `beautifulsoup4` into the plugin's own data folder (not into your Python). That takes about 10 seconds with `uv` or
a minute or two with `pip`; the first tool call waits for it. The server still answers Claude Code instantly, so
startup never times out. Outside a plugin, the folder is `~/.cache/stock-analyst-kit/`.

## What it does on your machine

A summary for anyone reviewing the plugin before installing it. All of the code is readable Python in `server/`.

**Runs.** One process, the MCP server: `python3 ${CLAUDE_PLUGIN_ROOT}/server/stock_mcp.py`. There are no hooks and no
other commands. The skill and the agent are Markdown instructions for Claude.

**Installs, once.** If `yfinance`, `ddgs` and `beautifulsoup4` can't already be imported, `server/deps.py` installs
them, in a background thread, with one of these commands (whichever tool is available):

```bash
uv pip install --quiet --python <this python> --target <data folder>/pylib-py<version> "yfinance>=0.2.54" "ddgs>=9" "beautifulsoup4>=4.12"
<this python> -m pip install --quiet --disable-pip-version-check --target <data folder>/pylib-py<version> "yfinance>=0.2.54" "ddgs>=9" "beautifulsoup4>=4.12"
```

The data folder is the plugin's own (`${CLAUDE_PLUGIN_DATA}`), or `~/.cache/stock-analyst-kit/` outside a plugin. The
packages never go into your Python installation, and nothing is installed at any other time. To remove them, delete
that folder; uninstalling the plugin deletes it too.

**Contacts these hosts**, only when a tool is called:

| Purpose | Hosts |
|---|---|
| First-run package install | `pypi.org`, `files.pythonhosted.org` |
| Prices, fundamentals, earnings, analysts, ETF holdings (yfinance) | `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `finance.yahoo.com`, `fc.yahoo.com`, and Yahoo's consent pages (`guce.yahoo.com`, `consent.yahoo.com`) when Yahoo asks for them |
| News search (ddgs) | `duckduckgo.com`, `www.bing.com`, `news.search.yahoo.com` |
| News (RSS) | `news.google.com` |
| Retail sentiment | `api.stocktwits.com` |
| `read_article` | only the article URL that Claude passes to it |

**Writes** only to the data folder above (the installed packages) and, when you run a report, one file:
`stock-report-YYYY-MM-DD.md` in the current folder, which Claude Code asks you to approve.

**Doesn't** need or read any API keys, credentials, environment secrets or files outside the plugin, and its five
tools only read data: they never place trades or post anything.

## Install and use it

### Claude Code in VS Code

1. Open the Claude Code panel and type `/plugins`.
2. On the **Marketplaces** tab, add `mishrabp/ai-agent-kits`.
3. On the **Plugins** tab, find **stock-analyst-kit** and click **Install**, then pick a scope.

Or paste this link into your browser:

```text
vscode://anthropic.claude-code/install-plugin?plugin=stock-analyst-kit&marketplace=mishrabp/ai-agent-kits
```

Then type `/stock-analyst-kit:stock-report`, or ask "which top Nasdaq stocks could gain 5% this month?". The VS Code
extension and the Claude Code CLI on the same machine share their plugins.

### Claude Code CLI

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install stock-analyst-kit@ai-agent-kits
claude plugin update stock-analyst-kit@ai-agent-kits      # later, to get new versions
```

### Claude Desktop

Install it by uploading a zip:

1. Download the repository (**Code › Download ZIP** on GitHub) and unzip it.
2. Zip the `claude/stock-analyst-kit` folder by itself, so the archive holds
   `stock-analyst-kit/.claude-plugin/plugin.json`. On Windows: right-click the folder › **Send to** › **Compressed (zipped) folder**.
3. Click **Customize** in the sidebar, then **Plugins › ＋ Add › Upload plugin**, and select the zip.

An uploaded copy doesn't update by itself: to get a newer version, upload a new zip.

| | Works? |
|---|---|
| **Code** tab | Yes, everything: `/stock-analyst-kit:stock-report`. If it doesn't show up in a Code session, install it there with **+ › Add plugins** |
| **Cowork** | Yes: the skill, the `equity-analyst` agent and the market connector load |
| **Chat** | No: chat ignores local MCP servers and agents, so there is no market data |

On Windows, the server starts with `python3`: install Python from the Microsoft Store (it provides `python3`) and
check that `python3 --version` works. The Desktop app doesn't load plugins in WSL sessions.

### Claude cloud sessions (claude.ai/code, Desktop **Cloud**, mobile)

Cloud sessions don't install plugins from marketplaces. In your cloud **environment's** settings:

1. **Setup script**: `git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /opt/ai-agent-kits`
2. **Environment variable**: `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/stock-analyst-kit`
3. **Network access**: the default **Trusted** level allows PyPI (for the package install) but not the market data
   sites. Allow the hosts listed under [What it does on your machine](#what-it-does-on-your-machine), or use full
   network access.

> This recipe follows the Claude Code docs, and `CLAUDE_CODE_PLUGIN_DIRS` was tested locally, but it hasn't been run
> in a cloud session yet.

### Turn it on for everyone in a project

Commit this to the project's `.claude/settings.json`. Teammates get the plugin after they trust the folder:

```json
{
  "extraKnownMarketplaces": {
    "ai-agent-kits": { "source": { "source": "github", "repo": "mishrabp/ai-agent-kits" } }
  },
  "enabledPlugins": { "stock-analyst-kit@ai-agent-kits": true }
}
```

### In your own agentic AI application

Clone the repository first: `git clone https://github.com/mishrabp/ai-agent-kits`.

**The whole kit, with the Claude Agent SDK** (`pip install claude-agent-sdk`). The skill, the agent and the connector
all work, under the same names as in Claude Code:

```python
import asyncio
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

KIT = Path("/path/to/ai-agent-kits/claude/stock-analyst-kit")

async def main():
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(KIT)}],
        setting_sources=[],  # load only this kit, not the plugins and settings on this machine
        cwd="/path/to/reports",  # where stock-report-YYYY-MM-DD.md is written
        allowed_tools=["mcp__plugin_stock-analyst-kit_market__*", "Agent", "Write"],
    )
    async for message in query(prompt="/stock-analyst-kit:stock-report", options=options):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Only the MCP server, with any MCP client.** `server/stock_mcp.py` is a standard stdio MCP server. Most clients take
the same shape (Claude Desktop's `claude_desktop_config.json`, Gemini CLI's `settings.json`, Cursor's `mcp.json`);
VS Code's `.vscode/mcp.json` (GitHub Copilot) uses a `servers` key with `"type": "stdio"` instead:

```json
{
  "mcpServers": {
    "market": {
      "command": "python3",
      "args": ["/path/to/ai-agent-kits/claude/stock-analyst-kit/server/stock_mcp.py"]
    }
  }
}
```

With the Agent SDK, pass it in code:

```python
options = ClaudeAgentOptions(
    setting_sources=[],
    mcp_servers={"market": {"command": "python3", "args": [str(KIT / "server/stock_mcp.py")]}},
    allowed_tools=["mcp__market__*"],
)
# then: query(prompt="Analyze NVDA with analyze_stock and summarize the trade setup.", options=options)
```

From plain Python with the official MCP client (`pip install mcp`), for frameworks that aren't MCP hosts:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python3", args=["/path/to/ai-agent-kits/claude/stock-analyst-kit/server/stock_mcp.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("analyze_stock", {"symbol": "NVDA"})
            print(result.content[0].text)

asyncio.run(main())
```

Or skip MCP entirely and import the code: `server/analysis.py` (indicators and the backtest) needs only the standard
library, and `server/data.py` returns plain dictionaries (`data.analyze("NVDA")`).

**Only the skill.** The skill and agent are plain Markdown, but they depend on the connector's tools and on each
other, so use the whole kit.

## Using it

### Run a report

Once the kit is installed, type the command in any Claude Code session (CLI, VS Code, or the Desktop app's Code tab):

| You type | What happens |
|---|---|
| `/stock-analyst-kit:stock-report` | Top 10 of QQQ and SPY, target +5%, minimum confidence 80%, horizon 1 month |
| `/stock-analyst-kit:stock-report PLTR COIN` | The same, plus those tickers |
| `/stock-analyst-kit:stock-report target=7% confidence=70%` | Changes the bar |
| "Which top Nasdaq stocks could gain 5% this month?" | Claude picks the skill from its description |

What to expect:

- **Time.** A run takes about 3 minutes: the analysts work on the stocks in parallel. The very first run also installs
  the kit's Python packages, which adds a few seconds with `uv` or a minute or two with `pip`.
- **Permissions.** Claude Code asks once before using the market-data tools and before saving the report. Choose
  "don't ask again" for the tools to skip the prompt next time.
- **Output.** The report appears in the conversation and is saved as `stock-report-YYYY-MM-DD.md` in the current folder.
- **Results.** On many days no stock reaches 80%. The report then says "No stock met the bar today" and lists the three
  closest candidates, with what held each one back.

### Read the report

- **Predictions**: the stocks that qualify, or the closest candidates if none do. Buy within the **Entry** range; the
  **Exit** is the price to sell at, at least 5% above the entry; the **Stop** is where the trade is wrong; the
  **Time horizon** is the latest date to hold.
- **Why these confidence levels**: for each stock, the backtest anchor (with its sample size) and each adjustment with
  its evidence. If the confidence looks too high or too low to you, this is where to check the reasoning.
- **Everything analyzed**: every stock in the universe, sorted by confidence, with its trend and next earnings date.
- **Next earnings** inside the horizon is the biggest single risk: a report can move a stock by more than its stop.

### Ask about a single stock or the market

The tools also work on their own, in any conversation, without the full report:

```text
Use analyze_stock on AMD and tell me if it's a good trade for the next month.
Get the market overview. Is this a good week to be buying tech?
Search the news for Micron from the last 3 days and read the most important article.
What are the top 10 holdings of QQQ right now?
```

## Develop

```bash
python3 -m unittest discover -s tests     # indicator and backtest math, no network
python3 scripts/smoke_test.py NVDA        # every tool against live data (installs packages on first run)
claude plugin validate .
claude --plugin-dir .                     # try the plugin in a real session
```

If you registered your clone as a local marketplace (`claude plugin marketplace add ./` from the repository root),
pick up a new or changed kit with `claude plugin marketplace update ai-agent-kits`, then
`claude plugin install stock-analyst-kit@ai-agent-kits` and `/reload-plugins`.

To release, run the tests, raise `version` in `.claude-plugin/plugin.json` (and in `pyproject.toml`), then push to `main`.
Users get the new version with `claude plugin update stock-analyst-kit@ai-agent-kits`; a push that doesn't change `version`
doesn't reach them. Directory listings update after the new version passes review.
