"""Hourly crypto prices for Owl Hours (see .github/workflows/crypto.yml).
Writes crypto.json with price and 24-hour change for BTC, ETH and XRP from CoinGecko (no key needed)."""
import json, sys, urllib.request
from datetime import datetime, timezone

IDS = {"bitcoin": "btc", "ethereum": "eth", "ripple": "xrp"}


def fetch(opener=urllib.request.urlopen):
    url = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=" + ",".join(IDS)
           + "&price_change_percentage=24h")
    req = urllib.request.Request(url, headers={"User-Agent": "owl-hours/1.0 (personal research)"})
    with opener(req, timeout=30) as r:
        rows = json.loads(r.read())
    out = {}
    for row in rows:
        k = IDS.get(row.get("id"))
        if not k or row.get("current_price") is None:
            continue
        chg = row.get("price_change_percentage_24h_in_currency", row.get("price_change_percentage_24h"))
        out[k] = {"price": row["current_price"], "chg24": round(chg, 2) if isinstance(chg, (int, float)) else None}
    return out


def main(opener=urllib.request.urlopen, path="crypto.json"):
    try:
        coins = fetch(opener)
    except Exception as e:
        print(f"CoinGecko failed: {e}", flush=True)
        return 0          # keep the last good file; never fail the run
    if not coins:
        print("CoinGecko returned nothing; keeping the last file.", flush=True)
        return 0
    data = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"), "coins": coins}
    json.dump(data, open(path, "w"), indent=1)
    print("Saved", ", ".join(f"{k} {v['price']}" for k, v in coins.items()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
