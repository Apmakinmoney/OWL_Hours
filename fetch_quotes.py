"""Fetch ETF quotes and write quotes.json. Runs from GitHub Actions every 15 minutes during market hours.

Fetches the 4 index ETFs, the 14 sector ETFs and the metal ETFs listed in config.json, so the page can set
the wheel from live sector moves. It also keeps a trail of today's sector moves, so the page can show how
the needle travelled since the open.

Needs one environment variable: FINNHUB_API_KEY (free key from finnhub.io; the free plan allows 60 calls a minute).
Only uses the Python standard library.
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
INDEX = CFG.get("etfs", ["SPY", "QQQ", "DIA", "IWM"])
SECTOR_ETFS = list(CFG.get("sectors", {}).values())
METALS = list(CFG.get("metals", {}).values())
SYMBOLS = list(dict.fromkeys(INDEX + SECTOR_ETFS + METALS))
# watchlist names (top companies + a few market ETFs): fetched after the ETFs, a little slower, to stay under 60 calls a minute
WATCH = [s for s in dict.fromkeys(CFG.get("featured", []) + CFG.get("universe", []) + CFG.get("watch_etfs", [])) if s not in SYMBOLS]
BENCH = CFG.get("benchmark", "SPY")
OUT = os.path.join(HERE, "quotes.json")
KEY = os.environ.get("FINNHUB_API_KEY", "")
TRAIL_MAX = 60


def fetch(symbol, opener=urllib.request.urlopen):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={KEY}"
    with opener(url, timeout=20) as r:
        d = json.load(r)
    # Finnhub fields: c = current price, d = change, dp = percent change, pc = previous close, t = timestamp
    if not isinstance(d.get("c"), (int, float)) or d["c"] <= 0:
        raise ValueError(f"no price for {symbol}: {d}")
    return {"price": round(d["c"], 2), "change": round(d.get("d") or 0, 2), "pct": round(d.get("dp") or 0, 2),
            "prevClose": d.get("pc"), "high": d.get("h"), "low": d.get("l"), "t": d.get("t"), "stale": False}


def main(opener=urllib.request.urlopen, sleep=time.sleep, now=None):
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT))
        except Exception:
            old = {}
    quotes, ok = {}, 0
    for s in SYMBOLS:
        try:
            quotes[s] = fetch(s, opener); ok += 1
        except Exception as e:
            print(f"warning: {s} failed: {e}", file=sys.stderr)
            if s in old.get("quotes", {}):
                quotes[s] = dict(old["quotes"][s], stale=True)   # keep the last good value, marked stale
        sleep(0.4)   # stays well under the free plan's 60 calls a minute
    for s in WATCH:
        try:
            quotes[s] = fetch(s, opener)
        except Exception as e:
            print(f"warning: {s} failed: {e}", file=sys.stderr)
            if s in old.get("quotes", {}):
                quotes[s] = dict(old["quotes"][s], stale=True)
        sleep(0.9)
    if ok == 0:
        print("no quotes fetched; leaving the file unchanged", file=sys.stderr)
        sys.exit(1)
    now = now or datetime.now(timezone.utc)
    et_day = now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    # today's trail: one point per run, sector ETFs and the benchmark only
    trail = old.get("trail", []) if old.get("trailDay") == et_day else []
    point = {"t": now.isoformat(timespec="seconds"), "p": {s: quotes[s]["pct"] for s in SECTOR_ETFS + [BENCH] if s in quotes and not quotes[s].get("stale")}}
    if trail and trail[-1].get("p") == point["p"]:
        trail[-1]["t"] = point["t"]          # market closed or unchanged: don't pile up identical points
    else:
        trail.append(point)
    data = {"asOf": now.isoformat(timespec="seconds"), "source": "Finnhub", "quotes": quotes,
            "trailDay": et_day, "trail": trail[-TRAIL_MAX:]}
    json.dump(data, open(OUT, "w"), indent=1)
    print(f"wrote quotes.json with {ok}/{len(SYMBOLS)} fresh quotes, {len(data['trail'])} trail points")


if __name__ == "__main__":
    if not KEY:
        sys.exit("FINNHUB_API_KEY is not set")
    main()
