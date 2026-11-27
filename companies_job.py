"""Watchlist details + deal news for Owl Hours (see .github/workflows/companies.yml).

Prices come from the 15-minute quotes robot (quotes.json). This job adds the slower-moving detail:
  every run (hourly):   3 latest headlines per company, latest merger/acquisition headlines
  once a day:           valuation and growth, company profile, analyst ratings, earnings beats/misses,
                        and 3 months of daily closes for the chart (Twelve Data)
Writes companies.json. Keys: FINNHUB_API_KEY (required), TWELVEDATA_API_KEY (for charts).
Headlines are stored as title, source, time and link only; readers open the full story at the source.
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
TD = os.environ.get("TWELVEDATA_API_KEY", "").strip()
OUT = os.path.join(HERE, "companies.json")


def log(m): print(m, flush=True)


def fetch_json(url, opener, sleep, tries=2):
    req = urllib.request.Request(url, headers={"User-Agent": "owl-hours/1.0 (personal research)"})
    for i in range(tries):
        try:
            with opener(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i + 1 < tries:
                log("  rate limit, waiting 25s"); sleep(25); continue
            raise


def fh(path, opener, sleep):
    d = fetch_json(f"https://finnhub.io/api/v1/{path}{'&' if '?' in path else '?'}token={KEY}", opener, sleep)
    sleep(1.05)
    return d


def num(x, nd=2):
    return round(x, nd) if isinstance(x, (int, float)) else None


def headline(n):
    if not n.get("headline") or not n.get("url"):
        return None
    return {"title": n["headline"][:180], "source": n.get("source", ""), "url": n["url"],
            "t": datetime.fromtimestamp(n.get("datetime", 0), timezone.utc).isoformat(timespec="minutes")}


def td_history(sym, opener, sleep):
    url = (f"https://api.twelvedata.com/time_series?symbol={urllib.parse.quote(sym)}&interval=1day&outputsize=65"
           f"&apikey={TD}")
    d = fetch_json(url, opener, sleep)
    sleep(8)   # Twelve Data free plan: 8 calls a minute
    if d.get("status") == "error" or not d.get("values"):
        raise ValueError(d.get("message", "no data"))
    return [[v["datetime"][:10], round(float(v["close"]), 2)] for v in reversed(d["values"])]


ALIASES = {"GOOGL": ["google", "youtube", "waymo"], "META": ["facebook", "instagram", "whatsapp", "zuckerberg"],
           "SPCX": ["spacex", "starlink", "starship", "xai"], "TSLA": ["tesla", "robotaxi", "cybertruck"],
           "LLY": ["lilly", "zepbound", "mounjaro", "orforglipron"], "NVDA": ["nvidia", "blackwell"], "MSFT": ["microsoft", "azure", "copilot"],
           "AAPL": ["apple", "iphone"], "AMZN": ["amazon", "aws"], "BRK.B": ["berkshire", "buffett"], "XOM": ["exxon"],
           "MCD": ["mcdonald"], "JPM": ["jpmorgan", "jp morgan", "dimon"], "GS": ["goldman"], "UNH": ["unitedhealth", "optum"],
           "KO": ["coca-cola", "coke"], "COIN": ["coinbase"], "NEM": ["newmont"], "AVGO": ["broadcom"], "PLTR": ["palantir"]}


def keywords(sym, name):
    base = [w.lower().strip(".,'") for w in name.replace("'s", "").split() if len(w) >= 4]
    return list(dict.fromkeys([sym.lower() + " ", "(" + sym.lower() + ")", "$" + sym.lower()] + base + ALIASES.get(sym, [])))


def daily_detail(sym, opener, sleep):
    out = {}
    m = (fh(f"stock/metric?symbol={sym}&metric=all", opener, sleep) or {}).get("metric", {}) or {}
    out.update(pe=num(m.get("peTTM", m.get("peBasicExclExtraTTM")), 1), ps=num(m.get("psTTM"), 1), pb=num(m.get("pbQuarterly", m.get("pbAnnual")), 1),
               mcap=num(m.get("marketCapitalization"), 0), hi52=num(m.get("52WeekHigh")), lo52=num(m.get("52WeekLow")),
               epsGrowth=num(m.get("epsGrowthTTMYoy"), 1), revGrowth=num(m.get("revenueGrowthTTMYoy"), 1),
               margin=num(m.get("netProfitMarginTTM"), 1), divYield=num(m.get("currentDividendYieldTTM"), 2), beta=num(m.get("beta"), 2))
    p = fh(f"stock/profile2?symbol={sym}", opener, sleep) or {}
    out["profile"] = {k: p.get(k) for k in ("name", "finnhubIndustry", "ipo", "weburl", "logo", "exchange") if p.get(k)}
    r = fh(f"stock/recommendation?symbol={sym}", opener, sleep) or []
    if r:
        x = r[0]
        out["recs"] = {"period": x.get("period"), "strongBuy": x.get("strongBuy", 0), "buy": x.get("buy", 0), "hold": x.get("hold", 0),
                       "sell": x.get("sell", 0), "strongSell": x.get("strongSell", 0)}
    e = fh(f"stock/earnings?symbol={sym}&limit=4", opener, sleep) or []
    out["earnings"] = [{"period": q.get("period"), "actual": q.get("actual"), "estimate": q.get("estimate"),
                        "surprisePct": num(q.get("surprisePercent"), 1)} for q in e[:4]]
    return out


def main(opener=urllib.request.urlopen, sleep=time.sleep, now=None):
    if not KEY:
        log("No FINNHUB_API_KEY; nothing to do."); return 0
    now = now or datetime.now(timezone.utc)
    old = {}
    try: old = json.load(open(OUT))
    except Exception: pass
    oldU = {u["sym"]: u for u in old.get("universe", [])}
    daily = old.get("detailDate") != now.date().isoformat()
    names, secs = CFG.get("company_names", {}), CFG.get("company_sector", {})
    companies = list(dict.fromkeys(CFG.get("featured", []) + CFG.get("universe", [])))
    etfs = CFG.get("watch_etfs", [])
    frm, to = (now - timedelta(days=4)).date().isoformat(), now.date().isoformat()
    uni, warnings = [], []
    for sym in companies + etfs:
        prev = oldU.get(sym, {})
        row = {k: v for k, v in prev.items() if k not in ("news",)}
        row.update(sym=sym, name=names.get(sym, sym), sector=secs.get(sym), kind="etf" if sym in etfs else "stock")
        if sym in companies and (daily or prev.get("mcap") is None):
            try: row.update(daily_detail(sym, opener, sleep))
            except Exception as e: warnings.append(f"{sym} detail: {e}")
        if TD and (daily or not prev.get("h")):
            try: row["h"] = td_history(sym, opener, sleep)
            except Exception as e: warnings.append(f"{sym} chart: {e}")
        if sym in companies:
            try:
                news = fh(f"company-news?symbol={sym}&from={frm}&to={to}", opener, sleep) or []
                seen, keep = set(), []
                kws = keywords(sym, names.get(sym, sym))
                for h in (headline(n) for n in sorted(news, key=lambda n: -n.get("datetime", 0))):
                    if not h: continue
                    if not any(k in h["title"].lower() for k in kws): continue
                    k = h["title"].lower()[:60]
                    if k in seen: continue
                    seen.add(k); keep.append(h)
                    if len(keep) == 3: break
                row["news"] = keep
            except Exception as e:
                warnings.append(f"{sym} news: {e}"); row["news"] = prev.get("news", [])
        uni.append(row)
        log(f"  {sym}: pe {row.get('pe')} news {len(row.get('news', []))} chart {len(row.get('h', []))}")
    mergers = old.get("mergers", [])
    try:
        mm = fh("news?category=merger", opener, sleep) or []
        mergers = [h for h in (headline(n) for n in sorted(mm, key=lambda n: -n.get("datetime", 0))) if h][:10]
    except Exception as e:
        warnings.append(f"merger news: {e}")
    data = {"asOf": now.isoformat(timespec="seconds"), "detailDate": now.date().isoformat() if daily else old.get("detailDate"),
            "featured": CFG.get("featured", []), "customerDefault": CFG.get("customer_default", []),
            "universe": uni, "mergers": mergers, "warnings": warnings[:25]}
    json.dump(data, open(OUT, "w"), indent=1)
    log(f"Saved {len(uni)} names, {len(mergers)} deal headlines, {len(warnings)} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
