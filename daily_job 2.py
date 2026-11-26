"""Daily data job for Owl Hours. Runs after the US market close (see .github/workflows/daily.yml).

Reads config.json and writes:
  latest.json              everything the wheel page and the letter draft need
  history.json             the market's own wheel reading for each trading day (the page's 90-day ring)
  snapshots/YYYY-MM-DD.json  a dated copy, so you build a record over time

Keys: TWELVEDATA_API_KEY (free key from twelvedata.com). FRED and CoinGecko need no key.
Only the Python standard library is used. If one source fails, the rest still run and the failure is listed under "warnings".
"""
import csv, io, json, os, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

CFG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))
TD_KEY = os.environ.get("TWELVEDATA_API_KEY", "")
THROTTLE = float(os.environ.get("TD_THROTTLE_SECONDS", "8"))   # free Twelve Data plan allows about 8 calls a minute


def http_text(url, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, headers={"User-Agent": "owl-hours/1.0 (personal research)"})
    with opener(req, timeout=30) as r:
        data = r.read()
    return data.decode("utf-8") if isinstance(data, bytes) else data


# ---------- sources ----------
def fred_series(series_id, opener=urllib.request.urlopen, days=70):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    text = http_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}", opener)
    out = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or row[0].upper().startswith("DATE") or row[0].upper().startswith("OBSERVATION"):
            continue
        try:
            out.append((row[0], float(row[1])))
        except ValueError:
            continue            # FRED marks holidays with "."
    if not out:
        raise ValueError(f"no data for {series_id}")
    return out


def twelve_history(symbol, opener=urllib.request.urlopen):
    if not TD_KEY:
        raise ValueError("TWELVEDATA_API_KEY is not set")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize={CFG['history_bars']}&apikey={TD_KEY}"
    d = json.loads(http_text(url, opener))
    if d.get("status") == "error" or "values" not in d:
        raise ValueError(f"{symbol}: {d.get('message', 'no values')}")
    rows = [{"date": v["datetime"], "high": float(v["high"]), "low": float(v["low"]), "close": float(v["close"])} for v in d["values"]]
    rows.sort(key=lambda r: r["date"])           # oldest first
    return rows


def coingecko(opener=urllib.request.urlopen):
    ids = ",".join(CFG["crypto"].values())
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}&price_change_percentage=7d"
    rows = json.loads(http_text(url, opener))
    by_id = {r["id"]: r for r in rows}
    out = {}
    for key, cid in CFG["crypto"].items():
        r = by_id.get(cid)
        if not r:
            continue
        pct = r.get("price_change_percentage_7d_in_currency")
        t = CFG["crypto_dir_pct"]
        d = None if pct is None else (1 if pct >= t else -1 if pct <= -t else 0)
        out[key] = {"level": r["current_price"], "dir": d, "chg7dPct": None if pct is None else round(pct, 2)}
    return out


# ---------- calculations ----------
def sma(values, n):
    return round(sum(values[-n:]) / n, 2) if len(values) >= n else None


def direction(values, kind, tol, lookback=5):
    """-1 falling, 0 flat, 1 rising, comparing the latest value with `lookback` observations earlier."""
    if len(values) <= lookback:
        return None
    a, b = values[-1], values[-1 - lookback]
    change = (a - b) if kind == "abs" else ((a - b) / abs(b) if b else 0)
    return 1 if change >= tol else -1 if change <= -tol else 0


def pivots(rows, window):
    highs, lows = [], []
    for i in range(window, len(rows) - window):
        seg = rows[i - window:i + window + 1]
        if rows[i]["high"] == max(r["high"] for r in seg):
            highs.append(rows[i]["high"])
        if rows[i]["low"] == min(r["low"] for r in seg):
            lows.append(rows[i]["low"])
    return highs, lows


def suggest_levels(rows):
    """Suggest two support and two resistance levels from swing highs and lows plus the 50 and 200-day averages.
    These are suggestions for the author to approve, not signals."""
    closes = [r["close"] for r in rows]
    last = closes[-1]
    recent = rows[-130:]
    highs, lows = pivots(recent, CFG["pivot_window"])
    cands = highs + lows
    for n in (50, 200):
        v = sma(closes, n)
        if v:
            cands.append(v)
    cands.sort()
    clusters = []
    for c in cands:
        if clusters and abs(c - clusters[-1][-1]) / clusters[-1][-1] * 100 <= CFG["cluster_pct"]:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    levels = [round(sum(g) / len(g), 2) for g in clusters]
    below = sorted([l for l in levels if l < last * 0.998], reverse=True)[:2]
    above = sorted([l for l in levels if l > last * 1.002])[:2]
    pad = lambda xs: (xs + [None, None])[:2]
    s, r = pad(below), pad(above)
    return {"s1": s[0], "s2": s[1], "r1": r[0], "r2": r[1]}


def pct_return(rows, days):
    if len(rows) <= days:
        return None
    return (rows[-1]["close"] / rows[-1 - days]["close"] - 1) * 100


# Live Wheel blend. The page uses the same numbers, so keep them in step with index.html (blendScore).
# today = 1-day return minus the S&P 500 ETF's, trend = 20-day return minus the S&P 500 ETF's, both in points.
SECTOR_ANGLE = {"FIN": 8, "REIT": 22, "DISC": 36, "TECH": 52, "CYB": 66, "NEO": 80, "SEMI": 94, "COMM": 112, "IND": 132,
                "MAT": 165, "ENGY": 200, "GOLD": 222, "STPL": 240, "HLTH": 280, "UTIL": 320}


def blend_score(today, trend):
    if today is None and trend is None:
        return 0
    if trend is None: z = today / 1.0
    elif today is None: z = trend / 3.0
    else: z = 0.4 * today / 1.0 + 0.6 * trend / 3.0
    return 2 if z >= 1.2 else 1 if z >= 0.4 else -2 if z <= -1.2 else -1 if z <= -0.4 else 0


def needle(scores):
    import math
    sx = sy = tot = 0.0
    for sid, a in SECTOR_ANGLE.items():
        v = scores.get(sid, 0); t = math.radians(a); sx += v * math.sin(t); sy += v * math.cos(t); tot += abs(v)
    if tot == 0 or math.hypot(sx, sy) < 1e-6: return None, 0.0
    return round(math.degrees(math.atan2(sx, sy)) % 360, 1), round(math.hypot(sx, sy) / tot, 3)


def save_history(date, scores, path="history.json", keep=400):
    """The market's own record: one point per trading day, so the 90-day ring fills in by itself."""
    hist = []
    if os.path.exists(path):
        try: hist = json.load(open(path))
        except Exception: hist = []
    angle, clarity = needle(scores)
    hist = [h for h in hist if h.get("date") != date] + [{"date": date, "m": scores, "angle": angle, "clarity": clarity}]
    hist.sort(key=lambda h: h["date"])
    json.dump(hist[-keep:], open(path, "w"), indent=1)
    return hist


def backfill_history(hist_rows, days=90, path="history.json"):
    """First run only: rebuild the market's wheel reading for the last `days` trading days from price history."""
    if os.path.exists(path):
        try:
            if len(json.load(open(path))) >= days // 2: return
        except Exception: pass
    bench = hist_rows.get(CFG["benchmark"])
    if not bench or len(bench) < days + 21: return
    closes = {sym: {r["date"]: r["close"] for r in rows} for sym, rows in hist_rows.items()}
    dates = [r["date"] for r in bench]
    out = []
    for i in range(len(dates) - days, len(dates)):
        d, d1, d20 = dates[i], dates[i - 1], dates[i - 20]
        def ret(sym, a, b):
            c = closes.get(sym, {}); return (c[a] / c[b] - 1) * 100 if a in c and b in c and c[b] else None
        b1, b20 = ret(CFG["benchmark"], d, d1), ret(CFG["benchmark"], d, d20)
        scores = {}
        for sid, sym in CFG["sectors"].items():
            r1, r20 = ret(sym, d, d1), ret(sym, d, d20)
            if r1 is None and r20 is None: continue
            scores[sid] = blend_score(None if r1 is None or b1 is None else r1 - b1, None if r20 is None or b20 is None else r20 - b20)
        a, cl = needle(scores)
        out.append({"date": d, "m": scores, "angle": a, "clarity": cl})
    json.dump(out, open(path, "w"), indent=1)
    print(f"backfilled history.json with {len(out)} trading days")


def score(rel):
    lo2, lo1, hi1, hi2 = CFG["momentum_thresholds"]
    return 2 if rel >= hi2 else 1 if rel >= hi1 else -2 if rel <= lo2 else -1 if rel <= lo1 else 0


# ---------- main ----------
def main(opener=urllib.request.urlopen, sleep=time.sleep):
    warnings, out = [], {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "note": "Auto-generated suggestions. The author reviews and approves everything before publishing.",
                         "macro": {}, "etf": {}, "sectors": {}, "metals": {}, "crypto": {}}
    # macro from FRED
    fred = {}
    for key, sid in CFG["fred"].items():
        try:
            fred[key] = fred_series(sid, opener)
        except Exception as e:
            warnings.append(f"FRED {sid}: {e}")
    for key, series in fred.items():
        vals = [v for _, v in series]
        kind, tol = CFG["direction"][key]
        out["macro"][key] = {"level": round(vals[-1], 3), "date": series[-1][0], "dir": direction(vals, kind, tol), "source": f"FRED {CFG['fred'][key]}"}
    # crypto
    try:
        for k, v in coingecko(opener).items():
            out["crypto"][k] = v
            out["macro"][k] = {"level": v["level"], "dir": v["dir"], "source": "CoinGecko"}
    except Exception as e:
        warnings.append(f"CoinGecko: {e}")
    # price history for ETFs, sectors and metals
    symbols = list(dict.fromkeys(CFG["etfs"] + list(CFG["sectors"].values()) + list(CFG["metals"].values())))
    hist = {}
    for i, sym in enumerate(symbols):
        try:
            hist[sym] = twelve_history(sym, opener)
        except Exception as e:
            warnings.append(f"Twelve Data {sym}: {e}")
        if i < len(symbols) - 1:
            sleep(THROTTLE)
    for sym in CFG["etfs"]:
        rows = hist.get(sym)
        if not rows:
            continue
        closes = [r["close"] for r in rows]
        lv = suggest_levels(rows)
        out["etf"][sym] = {"date": rows[-1]["date"], "c": round(closes[-1], 2), "m50": sma(closes, 50), "m200": sma(closes, 200),
                           "chg5Pct": None if pct_return(rows, 5) is None else round(pct_return(rows, 5), 2), **lv}
    bench = hist.get(CFG["benchmark"])
    if bench:
        b = pct_return(bench, CFG["momentum_days"]); b1 = pct_return(bench, 1); b20 = pct_return(bench, 20)
        for sid, sym in CFG["sectors"].items():
            rows = hist.get(sym)
            r = pct_return(rows, CFG["momentum_days"]) if rows else None
            if r is None or b is None:
                continue
            rel = r - b
            r1, r20 = pct_return(rows, 1), pct_return(rows, 20)
            rel1 = None if r1 is None or b1 is None else round(r1 - b1, 2)
            rel20 = None if r20 is None or b20 is None else round(r20 - b20, 2)
            out["sectors"][sid] = {"proxy": sym, "relReturnPct": round(rel, 2), "suggested": score(rel),
                                   "rel1": rel1, "rel20": rel20, "blend": blend_score(rel1, rel20)}
    for key, sym in CFG["metals"].items():
        rows = hist.get(sym)
        if rows:
            closes = [r["close"] for r in rows]
            out["metals"][key] = {"proxy": sym, "level": round(closes[-1], 2), "dir": direction(closes, "rel", 0.01),
                                  "note": "ETF price, not spot"}
            out["macro"].setdefault(key, {"level": None, "dir": out["metals"][key]["dir"], "source": f"{sym} 5-day direction"})
    out["warnings"] = warnings
    if not out["macro"] and not out["etf"]:
        print("nothing fetched; leaving files unchanged", file=sys.stderr)
        for w in warnings:
            print("warning:", w, file=sys.stderr)
        sys.exit(1)
    if out["sectors"] and bench:
        backfill_history(hist)
        save_history(bench[-1]["date"], {k: v["blend"] for k, v in out["sectors"].items()})
    os.makedirs("snapshots", exist_ok=True)
    json.dump(out, open("latest.json", "w"), indent=2)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json.dump(out, open(f"snapshots/{day}.json", "w"), indent=2)
    print(f"wrote latest.json and snapshots/{day}.json ({len(warnings)} warnings)")
    for w in warnings:
        print("warning:", w)
    return out


if __name__ == "__main__":
    main()
