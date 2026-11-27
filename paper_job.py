"""Paper portfolios for the Owl models, tracked forward from their start date (owner Lab only).

Runs after the daily robot. Each model starts with $100,000, rebalances on the first run of each new month
using that day's clock read, and is valued every day at the closing prices. No look-ahead is possible:
it only ever knows what the clock knew that day. Writes paper.json.
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import clockmath as cm

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
OUT = os.path.join(HERE, "paper.json")
START_CASH = 100000.0
MIXES = {"Recovery": (0.40, 0.35, 0.25), "Expansion": (0.35, 0.35, 0.30), "Late cycle": (0.60, 0.25, 0.15), "Contraction": (0.70, 0.20, 0.10)}


def log(m): print(m, flush=True)


def models(z, m, ang, cl):
    S = CFG["sectors"]
    ph = cm.phase(ang)[0] if ang is not None else None
    top = [s for s in sorted(z, key=lambda k: -z[k]) if z[s] > 0][:3]
    A = {S[s]: 1 / 3 for s in top}
    if len(top) < 3: A["SPY"] = (3 - len(top)) / 3
    top2 = [s for s in sorted(z, key=lambda k: -z[k]) if z[s] > 0][:2]
    A2 = {S[s]: 1 / 2 for s in top2}
    if len(top2) < 2: A2["SPY"] = (2 - len(top2)) / 2
    home = [s for s in z if ph and cm.phase(cm.ANG[s])[0] == ph]
    B = {S[s]: 1 / len(home) for s in home} if home else {"SPY": 1.0}
    C = {S[s]: 1 / 3 for s in cm.DEFENSIVE} if ph in ("Late cycle", "Contraction") else {"SPY": 1.0}
    g, sv, mi = MIXES.get(ph, (0.6, 0.3, 0.1))
    def mix(parts):
        w = {}
        for share, ws in parts:
            for k, x in ws.items(): w[k] = w.get(k, 0) + share * x
        return w
    return {
        "spy": ("SPY buy and hold", None, {"SPY": 1.0}),
        "A": ("Owl A: top 3 strongest", None, A), "B": ("Owl B: needle's phase", None, B), "C": ("Owl C: defensive switch", None, C),
        "t1": ("Highest risk", None, A2), "t2": ("Aggressive", None, A),
        "t3": ("Moderately aggressive", 0.20, mix([(0.8, A), (0.2, {"AGG": 1})])),
        "t4": ("Moderate", 0.15, mix([(0.6, A), (0.3, {"AGG": 1}), (0.1, {"GLD": 1})])),
        "t5": ("Conservatively moderate", 0.12, mix([(0.45, A), (0.35, {"AGG": 1}), (0.1, {"SHY": 1}), (0.1, {"GLD": 1})])),
        "t6": ("Conservative", 0.08, mix([(0.3, A), (0.4, {"AGG": 1}), (0.2, {"SHY": 1}), (0.1, {"GLD": 1})])),
        "t7": ("Retirement income", 0.10, mix([(0.15, C), (0.4, {"AGG": 1}), (0.1, {"SHY": 1}), (0.35, {"SCHD": 0.5, "VIG": 0.5})])),
        "h1": ("Clock-steered metals mix", None, {"GLD": g, "SLV": sv, "GDX": mi}),
        "h2": ("Metals core + miners switch", None, {"GLD": 0.6, "SLV": 0.3, ("GDX" if z.get("GOLD", 0) > 0 else "SHY"): 0.1}),
    }


def finnhub_price(sym, opener=urllib.request.urlopen):
    with opener(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={KEY}", timeout=20) as r:
        d = json.load(r)
    return d["c"] if isinstance(d.get("c"), (int, float)) and d["c"] > 0 else None


def main(opener=urllib.request.urlopen, sleep=time.sleep, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    latest = json.load(open(os.path.join(HERE, "latest.json")))
    quotes = json.load(open(os.path.join(HERE, "quotes.json"))).get("quotes", {})
    px = {s: q["price"] for s, q in quotes.items() if isinstance(q.get("price"), (int, float))}
    z, m = cm.from_latest(latest)
    ang, cl = cm.needle(m)
    targets = models(z, m, ang, cl)
    need = {s for _, _, w in targets.values() for s in w} - set(px)
    for s in sorted(need):
        if not KEY: break
        try:
            p = finnhub_price(s, opener)
            if p: px[s] = p
        except Exception as e:
            log(f"  price {s} failed: {e}")
        sleep(1.1)
    try: book = json.load(open(OUT))
    except Exception: book = {"start": day, "models": {}}
    for mid, (name, guard, w) in targets.items():
        P = book["models"].get(mid)
        if P is None:
            P = {"name": name, "start": day, "cash": START_CASH, "units": {}, "hist": [], "lastRebal": None, "peak": START_CASH}
            book["models"][mid] = P
        P["name"] = name
        value = P["cash"] + sum(u * px.get(s, 0) for s, u in P["units"].items())
        missing = [s for s in P["units"] if s not in px]
        if missing:
            log(f"  {mid}: no price for {missing}; skipping today"); continue
        P["peak"] = max(P.get("peak", value), value)
        if P["lastRebal"] is None or P["lastRebal"][:7] != day[:7]:
            tw = dict(w)
            if guard and value < P["peak"] * (1 - guard):
                tw = {k: x for k, x in w.items() if k in ("AGG", "SHY", "GLD", "SCHD", "VIG")}
                rest = 1 - sum(tw.values()); tw["SHY"] = tw.get("SHY", 0) + rest
                P["guard"] = f"Drawdown guard on since {day}"
            else:
                P.pop("guard", None)
            tw = {k: x for k, x in tw.items() if k in px and x > 1e-6}
            tot = sum(tw.values()) or 1
            P["units"] = {k: round(value * x / tot / px[k], 6) for k, x in tw.items()}
            P["cash"] = round(value - sum(u * px[k] for k, u in P["units"].items()), 2)
            P["lastRebal"] = day
            P["weights"] = {k: round(x / tot, 3) for k, x in tw.items()}
        if P["hist"] and P["hist"][-1][0] == day: P["hist"][-1][1] = round(value, 2)
        else: P["hist"].append([day, round(value, 2)])
        P["nav"] = round(value, 2)
        P["ret"] = round(100 * (value / START_CASH - 1), 2)
    book["asOf"] = now.isoformat(timespec="seconds")
    book["clock"] = {"angle": round(ang, 1) if ang is not None else None, "clarity": round(cl, 2), "phase": cm.phase(ang)[0] if ang is not None else None}
    json.dump(book, open(OUT, "w"), indent=1)
    log(f"Paper: {len(book['models'])} models valued for {day}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
