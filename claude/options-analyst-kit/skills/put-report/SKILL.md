---
name: put-report
description: Finds cash-secured puts on S&P 500 and Nasdaq-100 stocks with strikes under $100 and an 80% or higher probability of profit over about 2 weeks or 4 weeks, reviews each for risks, and writes a report with credit, breakeven, probabilities, returns and collateral. Use when the user asks for option trades, put selling ideas, high-probability options, or cash-secured puts.
argument-hint: "[max_strike=100] [pop=80%] [include_earnings]"
allowed-tools: mcp__plugin_options-analyst-kit_options__scan_cash_secured_puts mcp__plugin_options-analyst-kit_options__get_market_overview
---

# Cash-secured put report

Arguments: $ARGUMENTS

Defaults: strikes under **$100**, probability of profit at least **80%**, expirations about **2 weeks** and about
**4 weeks** out, trades with an earnings report before expiration **left out**. The arguments may change these
(for example `max_strike=50 pop=85%`, or `include_earnings`).

## Steps

1. **Market backdrop.** Call `get_market_overview`. Summarize it in 3 lines: regime, SPY trend, VIX level and percentile
   (a higher VIX means richer premiums but bigger moves), and any market-moving headline.

2. **Scan.** Call `scan_cash_secured_puts` with the arguments. It takes about 2 minutes. Every number in the report
   comes from this result or from the reviewers; never recompute or invent one.

3. **Review in parallel.** Take the trades from both horizons (up to 10 each). Split them into batches of about 5 and
   send every batch to the `options-analyst-kit:put-analyst` agent at the same time (several Agent calls in one
   message), giving each trade's symbol, strike, expiration and horizon. Wait for all of them.

4. **Write the report** in this format, show it in full, and save it as `put-report-YYYY-MM-DD.md` in the current
   directory. Within each horizon, list OK trades first, then CAUTION, keeping the scan's order (highest annualized
   return first). Move AVOID trades to their own section.

```markdown
# Cash-secured put report - YYYY-MM-DD

**Universe:** S&P 500 and Nasdaq-100 (N stocks; S screened by price and liquidity; C contracts evaluated; P passed).
**Criteria:** cash-secured puts, strike under $100, probability of profit 80%+ by Black-Scholes **and** by the stock's
own 3-year history, no earnings before expiration. **Quotes:** the scan's quotes_note.

**Market backdrop:** the 3-line summary.

## About 2 weeks - expiring YYYY-MM-DD (D days)

| # | Stock | Price | Strike | Credit | Breakeven (cushion) | POP implied / historical | Return (annualized) | Collateral | Review |
|---|-------|-------|--------|--------|---------------------|--------------------------|---------------------|-----------|--------|
| 1 | TICKER - Name | $P | $K | $C | $B (X%) | Y% / Z% | R% (A%) | $K00 | OK |

## About 4 weeks - expiring YYYY-MM-DD (D days)

(same table)

## Why these probabilities

One short section per trade above: implied volatility and what it implies (expected 1-standard-deviation move), how far
the breakeven sits below the price, the historical rate and its sample size, the support level relative to the strike,
the next earnings date, and the reviewer's reasons and news line.

## Reviewed and avoided

| Stock | Strike | Expiration | Reason |
(or "None.")

## Left out for earnings before expiration

The scan's excluded_for_earnings list, one line per horizon (or "None.").

## How to read this report

- **Selling a cash-secured put** means collecting the credit now and agreeing to buy 100 shares at the strike if the
  stock is below it at expiration. You need the collateral (strike x 100) in cash for each contract.
- **Probability of profit** is the chance the stock finishes above the breakeven (strike minus credit) at expiration.
  "Implied" uses the Black-Scholes model with the volatility priced into the option; "historical" is how often this
  stock stayed above the same cushion over the same number of trading days in the last 3 years. A trade is listed only
  if both are at least 80%.
- **The losses are bigger than the gains.** The most you can make is the credit; if the stock falls far below the
  strike you lose the difference, which can be many times the credit. One loss can erase several wins.
- Option quotes move all day. Check the live bid and ask before placing an order; if the market was closed when this
  ran, the credits are last trades and may differ.
- This report is generated from public market data for research and education. It is not financial advice.
```

If a horizon has no trades, write "No trade met the criteria for this horizon." under its heading.
