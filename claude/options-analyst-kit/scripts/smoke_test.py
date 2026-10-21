#!/usr/bin/env python3
# Starts the MCP server the way Claude Code does (stdio) and calls each tool against live data.
# The scan covers about 500 stocks and takes about 2 minutes; the first run also installs the kit's packages.
# Usage: python3 scripts/smoke_test.py
import json
import os
import subprocess
import sys
import time

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "options_mcp.py")
proc = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
next_id, failed = 0, 0


def request(method, params=None):
    global next_id
    next_id += 1
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": next_id, "method": method, "params": params or {}}) + "\n")
    proc.stdin.flush()
    reply = json.loads(proc.stdout.readline())
    if "error" in reply:
        raise RuntimeError(f"{method}: {reply['error']['message']}")
    return reply["result"]


def call(name, args=None):
    t = time.time()
    res = request("tools/call", {"name": name, "arguments": args or {}})
    text = res["content"][0]["text"]
    if res.get("isError"):
        raise RuntimeError(f"{name}: {text}")
    return json.loads(text), time.time() - t


def check(label, cond, extra=""):
    global failed
    print(f"{'PASS' if cond else 'FAIL'}  {label}" + (f"  ({extra})" if extra else ""))
    failed += not cond


try:
    t = time.time()
    request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}})
    check("initialize answers before packages are installed", time.time() - t < 5, f"{time.time() - t:.2f}s")
    names = [x["name"] for x in request("tools/list")["tools"]]
    check("tools/list returns 5 tools", len(names) == 5, ", ".join(names))

    m, s = call("get_market_overview")
    check("get_market_overview", m["regime"] in ("risk-on", "mixed", "risk-off"), f"{s:.1f}s: {m['regime']}, VIX {m['vix']['level']}")

    scan, s = call("scan_cash_secured_puts", {"max_results": 5})
    f = scan["funnel"]
    check("scan_cash_secured_puts", f["universe"] > 450 and f["contracts_evaluated"] > 0,
          f"{s:.0f}s: {f['universe']} stocks -> {f['screened']} screened -> {f['contracts_evaluated']} contracts -> "
          f"{f['contracts_passing_pop']} passing; market open: {scan['market_open']}")
    trades = [t for h in scan["horizons"].values() for t in h["trades"]]
    check("every listed trade meets the criteria",
          all(t["strike"] < 100 and t["pop_implied"] >= 0.8 and t["pop_historical"] >= 0.8 and not t["earnings_before_expiration"]
              for t in trades), f"{len(trades)} trades")
    if trades:
        t0 = trades[0]
        a, s = call("analyze_put", {"symbol": t0["symbol"], "strike": t0["strike"], "expiration": t0["expiration"]})
        check("analyze_put", "stock" in a and a["stock"]["price"] > 0,
              f"{s:.1f}s: {t0['symbol']} {t0['strike']} put {t0['expiration']}, support {a['stock']['support_swing_low']}, "
              f"{len(a['sentiment']['news'])} headlines")

    n, s = call("get_news", {"query": "stock market", "days": 3})
    check("get_news", len(n["items"]) > 0, f"{s:.1f}s: {len(n['items'])} items")
except Exception as err:  # noqa: BLE001
    check("tool call", False, str(err)[:300])
finally:
    proc.stdin.close()
    proc.wait(timeout=60)

print(f"\n{failed} check(s) failed" if failed else "\nAll smoke checks passed")
sys.exit(1 if failed else 0)
