"""Fetch ETF quotes and write quotes.json. Runs from GitHub Actions every 15 minutes.

Needs one environment variable: FINNHUB_API_KEY (free key from finnhub.io).
Only uses the Python standard library.
"""
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

SYMBOLS = ["SPY", "QQQ", "DIA", "IWM"]   # S&P 500, Nasdaq 100, Dow, Russell 2000 ETFs
OUT = "quotes.json"
KEY = os.environ.get("FINNHUB_API_KEY", "")

def fetch(symbol, opener=urllib.request.urlopen):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={KEY}"
    with opener(url, timeout=20) as r:
        d = json.load(r)
    # Finnhub fields: c = current price, d = change, dp = percent change, pc = previous close, t = timestamp
    if not isinstance(d.get("c"), (int, float)) or d["c"] <= 0:
        raise ValueError(f"no price for {symbol}: {d}")
    return {"price": round(d["c"], 2), "change": round(d.get("d") or 0, 2), "pct": round(d.get("dp") or 0, 2),
            "prevClose": d.get("pc"), "high": d.get("h"), "low": d.get("l"), "t": d.get("t"), "stale": False}

def main(opener=urllib.request.urlopen):
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT)).get("quotes", {})
        except Exception:
            old = {}
    quotes, ok = {}, 0
    for s in SYMBOLS:
        try:
            quotes[s] = fetch(s, opener); ok += 1
        except Exception as e:
            print(f"warning: {s} failed: {e}", file=sys.stderr)
            if s in old:
                quotes[s] = dict(old[s], stale=True)   # keep the last good value, marked stale
        time.sleep(0.5)
    if ok == 0:
        print("no quotes fetched; leaving the file unchanged", file=sys.stderr)
        sys.exit(1)
    data = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": "Finnhub", "quotes": quotes}
    json.dump(data, open(OUT, "w"), indent=2)
    print(f"wrote {OUT} with {ok}/{len(SYMBOLS)} fresh quotes")

if __name__ == "__main__":
    if not KEY:
        sys.exit("FINNHUB_API_KEY is not set")
    main()
