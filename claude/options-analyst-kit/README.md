# options-analyst-kit

A Claude Code plugin that scans **every S&P 500 and Nasdaq-100 stock** for **cash-secured puts** with a **strike under
$100** and an **80% or higher probability of profit**, expiring in about **2 weeks** or about **4 weeks**. It reviews
each trade for risks the numbers miss and writes a report with the credit, breakeven, probabilities, return and
collateral of every trade.

```text
/options-analyst-kit:put-report
/options-analyst-kit:put-report max_strike=50 pop=85%
```

**A cash-secured put** means selling a put option: you collect the premium (the credit) now, and if the stock is below
the strike at expiration you buy 100 shares at the strike. You keep strike x 100 in cash as collateral. You profit if
the stock stays above the **breakeven** (strike minus credit).

## How a trade is found

Every number is computed by code (`server/pricing.py` and `server/data.py`); the reviewing agent only adds a verdict.

| Step | What happens |
|---|---|
| 1. Universe | All members of the S&P 500 (Wikipedia's list, read with BeautifulSoup; State Street's SPY holdings file as a fallback) and the Nasdaq-100 (Nasdaq's own list): about 518 stocks |
| 2. Screen | Price between $5 and $115, so a strike under $100 can be a sensible out-of-the-money put, and at least $25M of shares traded per day (20-day average) |
| 3. Contracts | For each stock, the expiration closest to 14 days (10-18) and to 28 days (24-35). Every out-of-the-money put with a strike under $100, open interest of 100 or more, a bid/ask spread within 35% of the midpoint, and a credit of at least $0.10 |
| 4. Implied volatility | Backed out from the option's own price with the Black-Scholes formula (bisection), using the 13-week T-bill rate. The credit is the bid/ask midpoint, or, when the market is closed, a last trade from the last 4 days |
| 5. Probability of profit | **Implied**: the risk-neutral chance the stock ends above the breakeven, N(d2) with the strike replaced by the breakeven, the standard broker definition. **Historical**: how often, over the last 3 years, the stock ended above the same % cushion after the same number of trading days |
| 6. Qualify | **Both** probabilities at least 80%, and no earnings report before expiration (earnings can gap a stock past any cushion) |
| 7. Choose | For each stock and horizon, the qualifying strike with the highest annualized return on collateral; then the top 10 per horizon |
| 8. Review | The `put-analyst` agent checks support levels against the strike, the trend, volatility and the last 7 days of news, and marks each trade OK, CAUTION or AVOID by fixed rules. It never changes a number |

**Why two probabilities.** The implied one is what the options market is pricing; the historical one is what this
stock has actually done. Requiring both protects against a stock whose options look calm but whose history doesn't,
and the reverse.

**What the probability doesn't say.** A put that wins 80% of the time can still lose money over many trades: the gain
is capped at the credit, while a loss can be many times larger. The report shows the collateral and the cushion so you
can judge the size of a bad outcome, not just its likelihood. Dividends are ignored in the pricing, and early
assignment is possible on American-style options. This is research software, not financial advice.

## What's in it

| Piece | File | What it does |
|---|---|---|
| **Connector** (MCP server `options`) | `server/options_mcp.py`, `server/data.py`, `server/pricing.py`, `server/analysis.py`, `server/deps.py`, `server/mcp_stdio.py` | Five read-only tools: `scan_cash_secured_puts`, `analyze_put`, `get_market_overview`, `get_news`, `read_article` |
| **Agent** | `agents/put-analyst.md` | Reviews a batch of trades and returns OK / CAUTION / AVOID with reasons |
| **Skill** | `skills/put-report/SKILL.md` | `/options-analyst-kit:put-report`: market backdrop, scan, parallel review, report |

## What it does on your machine

**Runs.** One process, the MCP server: `python3 ${CLAUDE_PLUGIN_ROOT}/server/options_mcp.py`. There are no hooks and
no other commands.

**Installs, once.** If `yfinance`, `ddgs` and `beautifulsoup4` can't already be imported, `server/deps.py` installs
them in a background thread with `uv pip install --target` or `python -m pip install --target`, into the plugin's own
data folder (`${CLAUDE_PLUGIN_DATA}`, or `~/.cache/options-analyst-kit/` outside a plugin), never into your Python.
You need `python3` 3.9+ and either `uv` or `pip`. Uninstalling the plugin deletes the folder.

**Contacts these hosts**, only when a tool is called:

| Purpose | Hosts |
|---|---|
| First-run package install | `pypi.org`, `files.pythonhosted.org` |
| Index members | `en.wikipedia.org`, `api.nasdaq.com`, and `www.ssga.com` only if Wikipedia fails |
| Prices and option chains (yfinance) | `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, `finance.yahoo.com`, `fc.yahoo.com`, and Yahoo's consent pages (`guce.yahoo.com`, `consent.yahoo.com`) when asked |
| News | `duckduckgo.com`, `www.bing.com`, `news.search.yahoo.com`, `news.google.com` |
| Retail sentiment | `api.stocktwits.com` |
| `read_article` | only the article URL Claude passes to it |

**Writes** only to its data folder and, when you run a report, `put-report-YYYY-MM-DD.md` in the current folder, which
Claude Code asks you to approve. **Doesn't** need API keys or credentials, read files outside the plugin, or place
orders: every tool only reads data.

## Install and use it

### Claude Code in VS Code

1. Open the Claude Code panel and type `/plugins`.
2. On the **Marketplaces** tab, add `mishrabp/ai-agent-kits`.
3. On the **Plugins** tab, find **options-analyst-kit** and click **Install**.

Or paste this link into your browser:

```text
vscode://anthropic.claude-code/install-plugin?plugin=options-analyst-kit&marketplace=mishrabp/ai-agent-kits
```

### Claude Code CLI

```bash
claude plugin marketplace add mishrabp/ai-agent-kits
claude plugin install options-analyst-kit@ai-agent-kits
claude plugin update options-analyst-kit@ai-agent-kits      # later, to get new versions
```

### Claude Desktop

1. Download the repository (**Code › Download ZIP** on GitHub) and unzip it.
2. Zip the `claude/options-analyst-kit` folder by itself, so the archive holds
   `options-analyst-kit/.claude-plugin/plugin.json`. On Windows: right-click the folder › **Send to** › **Compressed (zipped) folder**.
3. Click **Customize** in the sidebar, then **Plugins › ＋ Add › Upload plugin**, and select the zip.

| | Works? |
|---|---|
| **Code** tab | Yes, everything: `/options-analyst-kit:put-report`. If it doesn't show up in a Code session, install it there with **+ › Add plugins** |
| **Cowork** | Yes: the skill, the `put-analyst` agent and the options connector load |
| **Chat** | No: chat ignores local MCP servers and agents |

On Windows, install Python from the Microsoft Store (it provides `python3`). The Desktop app doesn't load plugins in
WSL sessions.

### Claude cloud sessions (claude.ai/code, Desktop **Cloud**, mobile)

In your cloud environment's settings: a **setup script** `git clone --depth 1 https://github.com/mishrabp/ai-agent-kits /opt/ai-agent-kits`,
an **environment variable** `CLAUDE_CODE_PLUGIN_DIRS=/opt/ai-agent-kits/claude/options-analyst-kit`, and **network
access** to the hosts listed above (the default Trusted level covers PyPI only). This recipe follows the Claude Code
docs but hasn't been run in a cloud session yet.

### In your own agentic AI application

```bash
git clone https://github.com/mishrabp/ai-agent-kits
```

**The whole kit, with the Claude Agent SDK** (`pip install claude-agent-sdk`):

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

async def main():
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": "/path/to/ai-agent-kits/claude/options-analyst-kit"}],
        setting_sources=[],
        cwd="/path/to/reports",
        allowed_tools=["mcp__plugin_options-analyst-kit_options__*", "Agent", "Write"],
    )
    async for message in query(prompt="/options-analyst-kit:put-report", options=options):
        if isinstance(message, ResultMessage):
            print(message.result)

asyncio.run(main())
```

**Only the MCP server, with any MCP client** (Claude Desktop's `claude_desktop_config.json`, Gemini CLI, Cursor; VS
Code's `.vscode/mcp.json` uses a `servers` key with `"type": "stdio"`):

```json
{
  "mcpServers": {
    "options": {
      "command": "python3",
      "args": ["/path/to/ai-agent-kits/claude/options-analyst-kit/server/options_mcp.py"]
    }
  }
}
```

**Or import the code**: `server/pricing.py` (Black-Scholes, implied volatility, probability of profit) needs only the
standard library, and `server/data.py` returns plain dictionaries (`data.scan()`).

## Using it

| You type | What happens |
|---|---|
| `/options-analyst-kit:put-report` | Strikes under $100, POP 80%+, about 2 and 4 weeks, earnings excluded |
| `/options-analyst-kit:put-report max_strike=50 pop=85%` | Cheaper strikes, a stricter bar |
| `/options-analyst-kit:put-report include_earnings` | Keeps trades with earnings before expiration |
| "Find me safe put-selling trades under $100" | Claude picks the skill from its description |

A run takes about 4 minutes: about 2 for the scan and the rest for the review. **Run it while the market is open**
(9:30-16:00 New York time) for live bid/ask prices; outside those hours the credits are the last trades, and the report
says so. To check one trade: "use analyze_put on F, strike 10, expiring 2026-11-20".

## Develop

```bash
python3 -m unittest discover -s tests     # Black-Scholes, implied volatility, probabilities; no network
python3 scripts/smoke_test.py             # every tool against live data (the scan takes about 2 minutes)
claude plugin validate --strict .
claude --plugin-dir .
```

To release, run the tests, raise `version` in `.claude-plugin/plugin.json` (and in `pyproject.toml`), then push to
`main`. Users get it with `claude plugin update options-analyst-kit@ai-agent-kits`.

## References

Black & Scholes, *The Pricing of Options and Corporate Liabilities* (Journal of Political Economy, 1973); Hull,
*Options, Futures, and Other Derivatives* (implied volatility, risk-neutral probabilities, the reflection-principle
approximation for the probability of touching a price).
