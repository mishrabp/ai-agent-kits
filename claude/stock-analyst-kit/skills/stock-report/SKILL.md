---
name: stock-report
description: Produces a stock report on the top 10 holdings of QQQ (Nasdaq-100) and SPY (S&P 500) - technical and fundamental analysis, sentiment, news and upcoming earnings - listing the stocks that could gain 5% or more within a month with 80% or higher confidence, with entry and exit prices and an explanation of each confidence level. Use when the user asks for a stock report, stock picks, which stocks to buy this month, or an analysis of the top Nasdaq or S&P stocks.
argument-hint: "[extra tickers...] [target=5%] [confidence=80%] [horizon=1 month]"
allowed-tools: mcp__plugin_stock-analyst-kit_market__get_top_holdings mcp__plugin_stock-analyst-kit_market__get_market_overview
---

# Stock report: top QQQ and SPY holdings

Arguments: $ARGUMENTS

Defaults: target gain **5%**, minimum confidence **80%**, horizon **21 trading days** (about one month).
The arguments may add tickers to analyze or change these numbers (for example `TSLA PLTR target=7% confidence=70%`).

## Steps

1. **Universe.** Call `get_top_holdings` for `QQQ` and for `SPY` (limit 10 each). Merge them into one list, keeping the
   order of the largest weight, and add any tickers from the arguments. Treat share classes of one company as one stock
   (keep `GOOGL`, drop `GOOG`), and say so in the report.

2. **Market backdrop.** Call `get_market_overview`. Summarize it in 3 or 4 lines: regime, SPY and QQQ trend, VIX level
   and percentile, 10-year yield, strongest and weakest sectors, and any market-moving headline.

3. **Analyze in parallel.** Split the tickers into batches of 3 or 4 and send every batch to the
   `stock-analyst-kit:equity-analyst` agent at the same time (several Agent calls in one message). Give each agent:
   today's date, its tickers, the market backdrop summary, the target gain, the horizon in trading days and the minimum
   confidence. Wait for all of them.

4. **Check the results.** For every block, confirm that the confidence equals the anchor plus the listed adjustments
   (a difference of 1 point from rounding to whole percents is fine and needs no note), that the adjustments total no
   more than +/-15 points, and that the confidence is at most 90%. Show every confidence and anchor as a whole percent.
   If a block breaks a rule, correct the number and mention the correction under that stock. A stock **qualifies** only if its exit is at
   least the target gain above its entry and its confidence is at least the minimum.

5. **Write the report** in this format, show it in full, and save it as `stock-report-YYYY-MM-DD.md` in the current
   directory:

```markdown
# Stock report - YYYY-MM-DD

**Universe:** top 10 holdings of QQQ and SPY (N stocks after merging). **Goal:** +5% or more within 1 month,
confidence 80% or higher. Prices as of YYYY-MM-DD close.

**Market backdrop:** the 3-4 line summary.

## Predictions

| # | Stock | Price | Entry | Exit (gain) | Stop | Time horizon | Next earnings | Confidence |
|---|-------|-------|-------|-------------|------|--------------|---------------|-----------|
| 1 | TICKER - Name | $P | $A-$B | $X (+G%) | $S | by YYYY-MM-DD | YYYY-MM-DD | C% |

(If no stock qualifies, write "No stock met the bar today." and, instead of the table above, show the three
closest candidates under the heading "Closest candidates (did not meet the bar)" with the same columns.)

## Why these confidence levels

One section per stock in the table above:

### TICKER - Name: C%
| Step | Points | Evidence |
|------|--------|----------|
| Anchor: 3-year backtest, similar setups | K% | n=N; target hit before stop within 21 trading days |
| Trend and momentum | +a | ... |
| Fundamentals and analysts | +b | ... |
| Sentiment and news | +c | ... |
| Market regime | +d | ... |
| Earnings inside horizon | -e | ... |
| **Confidence** | **C%** | |

Then the analyst's "why" bullets and "risks" bullets.

## Everything analyzed

| Stock | Price | Trend | Next earnings | Anchor | Confidence | Verdict |
|-------|-------|-------|---------------|--------|-----------|---------|
(every stock, sorted by confidence)

## How to read this report

- **Confidence** is an estimate of the chance that the stock reaches the exit price before the stop, within the
  horizon. It starts from how often that actually happened in similar setups for this stock over the last 3 years,
  adjusted by at most 15 points for trend, fundamentals, analysts, sentiment, the market and earnings.
- Past behavior does not guarantee future results, and an earnings report inside the horizon can move a stock by
  more than the stop.
- This report is generated from public market data for research and education. It is not financial advice.
```

Never invent prices or statistics: every number in the report must come from a tool result or an agent block.
