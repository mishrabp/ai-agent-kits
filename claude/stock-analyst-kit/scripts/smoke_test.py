#!/usr/bin/env python3
# Starts the MCP server the way Claude Code does (stdio) and calls each tool against live data.
# The first run installs the kit's packages, so it can take a minute or two.
# Usage: python3 scripts/smoke_test.py [SYMBOL]
import json
import os
import subprocess
import sys
import time

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "stock_mcp.py")
symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"

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

    for etf in ("QQQ", "SPY"):
        h, s = call("get_top_holdings", {"etf": etf})
        check(f"get_top_holdings {etf}", len(h["holdings"]) == 10, f"{s:.1f}s: " + " ".join(x["symbol"] for x in h["holdings"]))

    m, s = call("get_market_overview")
    check("get_market_overview", "vix" in m and m["regime"], f"{s:.1f}s: regime {m['regime']}, VIX {m['vix']['level']}, {len(m['headlines'])} headlines")

    a, s = call("analyze_stock", {"symbol": symbol})
    pa = a["technicals"]["probability_anchors"]
    check(f"analyze_stock {symbol}", a["technicals"]["price"] > 0,
          f"{s:.1f}s: price {a['technicals']['price']}, similar-setup win rate {pa['similar_setups_3y'].get('target_before_stop')} "
          f"(n={pa['similar_setups_3y'].get('samples')}), next earnings {a['earnings'].get('next_earnings_date')}, "
          f"{len(a['sentiment']['news'])} headlines, stocktwits {a['sentiment']['stocktwits'].get('bullish_share_of_tagged')}")
    check("analyze_stock has no source errors", "error" not in json.dumps(a["fundamentals"])[:50] and "error" not in a["earnings"],
          ", ".join(k for k in ("fundamentals", "earnings") if isinstance(a[k], dict) and "error" in a[k]) or "ok")

    n, s = call("get_news", {"query": f"{symbol} stock", "days": 7})
    check("get_news", len(n["items"]) > 0, f"{s:.1f}s: {len(n['items'])} items")
    if n["items"]:
        url = next((i["url"] for i in n["items"] if i.get("via") == "duckduckgo"), n["items"][0]["url"])
        try:
            art, s = call("read_article", {"url": url, "max_chars": 1500})
            check("read_article", len(art["text"]) > 100, f"{s:.1f}s: {art['title']!r:.60}")
        except RuntimeError as err:  # some publishers block scripted readers; not a kit failure
            print(f"SKIP  read_article ({str(err)[:100]})")
except Exception as err:  # noqa: BLE001
    check("tool call", False, str(err)[:300])
finally:
    proc.stdin.close()
    proc.wait(timeout=30)

print(f"\n{failed} check(s) failed" if failed else "\nAll smoke checks passed")
sys.exit(1 if failed else 0)
