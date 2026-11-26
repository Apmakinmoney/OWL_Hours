"""Economic and earnings calendar for Owl Hours. Runs after the daily job (see .github/workflows/daily.yml).

Writes calendar.json:
  events   upcoming CPI, jobs, GDP, PCE and retail-sales release dates (FRED), Fed decision days, big-name earnings (Finnhub)
  prints   latest CPI inflation (year over year), unemployment rate and payroll change (FRED)
Keys: FRED_API_KEY and FINNHUB_API_KEY. If one source fails the rest still save, and the failure is listed under "warnings".
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone

FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()
FH_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()

# FRED release ids -> what we call them
RELEASES = {10: ("CPI inflation report", "cpi"), 50: ("Jobs report", "jobs"), 53: ("GDP", "gdp"),
            54: ("PCE inflation (Fed's favorite)", "pce"), 9: ("Retail sales", "retail")}

# Fed policy decision days (second day of each meeting, 2 pm ET). From federalreserve.gov, revised Nov 12, 2026.
# Oct 26-27, 2027 is a strategy-only meeting with no rate decision, so it is not listed.
FOMC = ["2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28",
        "2027-09-15", "2027-11-17", "2028-01-26"]

# Big names worth flagging on the earnings calendar
WATCH = set("""AAPL MSFT NVDA AMZN GOOGL GOOG META TSLA AVGO BRK.B JPM V MA UNH XOM CVX LLY JNJ WMT COST HD PG ORCL CRM ADBE
AMD NFLX INTC QCOM MU CSCO IBM TXN BAC WFC GS MS C KO PEP MCD NKE DIS BA CAT DE GE HON LMT RTX UPS FDX TGT LOW SBUX
PLTR CRWD PANW SNOW SHOP UBER ABNB COIN MSTR SMCI ARM TSM ASML NOW INTU AMAT LRCX KLAC MRVL DELL HPQ ADSK WDAY ZS NET
DDOG OKTA S FTNT CIBR""".split())


def log(m): print(m, flush=True)


def get_json(url, opener=urllib.request.urlopen, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "owl-hours/1.0 (personal research)"})
    with opener(req, timeout=timeout) as r:
        return json.loads(r.read())


def fred_obs(series, start, opener):
    d = get_json(f"https://api.stlouisfed.org/fred/series/observations?series_id={series}&api_key={FRED_KEY}"
                 f"&file_type=json&observation_start={start}", opener)
    out = []
    for o in d.get("observations", []):
        try: out.append((o["date"], float(o["value"])))
        except (ValueError, KeyError, TypeError): continue
    if not out: raise ValueError(f"no data for {series}")
    return out


def release_dates(today, opener):
    out = []
    for rid, (name, kind) in RELEASES.items():
        d = get_json(f"https://api.stlouisfed.org/fred/release/dates?release_id={rid}&api_key={FRED_KEY}&file_type=json"
                     f"&realtime_start={today.isoformat()}&include_release_dates_with_no_data=true&sort_order=asc&limit=4", opener)
        for r in d.get("release_dates", []):
            if r.get("date", "") >= today.isoformat():
                log(f"  FRED release {rid} ({name}) on {r['date']}")
                out.append({"date": r["date"], "kind": kind, "title": name, "time": "8:30 am ET"})
    return out


def prints(opener):
    start = (datetime.now(timezone.utc) - timedelta(days=500)).strftime("%Y-%m-%d")
    p = {}
    cpi = fred_obs("CPIAUCSL", start, opener)
    if len(cpi) >= 13:
        last, prev = cpi[-1], cpi[-13]
        p["cpi"] = {"label": "CPI inflation, year over year", "value": round((last[1] / prev[1] - 1) * 100, 1), "unit": "%", "date": last[0]}
    u = fred_obs("UNRATE", start, opener)
    p["unrate"] = {"label": "Unemployment rate", "value": u[-1][1], "unit": "%", "date": u[-1][0],
                   "prev": u[-2][1] if len(u) > 1 else None}
    pay = fred_obs("PAYEMS", start, opener)
    if len(pay) >= 2:
        p["payrolls"] = {"label": "Jobs added last month", "value": int(round(pay[-1][1] - pay[-2][1])), "unit": "k", "date": pay[-1][0]}
    return p


def earnings(today, opener):
    end = (today + timedelta(days=14)).isoformat()
    d = get_json(f"https://finnhub.io/api/v1/calendar/earnings?from={today.isoformat()}&to={end}&token={FH_KEY}", opener)
    out = []
    for e in d.get("earningsCalendar", []) or []:
        sym = (e.get("symbol") or "").upper()
        if sym in WATCH and e.get("date"):
            hr = {"bmo": "before open", "amc": "after close"}.get(e.get("hour") or "", "")
            out.append({"date": e["date"], "kind": "earnings", "title": f"{sym} earnings", "symbol": sym, "time": hr,
                        "eps": e.get("epsEstimate")})
    return out


def main(opener=urllib.request.urlopen, path="calendar.json", today=None):
    today = today or datetime.now(timezone.utc).date()
    events, warnings, pr = [], [], {}
    for d in FOMC:
        if d >= today.isoformat():
            events.append({"date": d, "kind": "fed", "title": "Fed rate decision", "time": "2:00 pm ET"})
    if FRED_KEY:
        try: events += release_dates(today, opener)
        except Exception as e: warnings.append(f"FRED calendar: {e}"); log(f"FRED calendar failed: {e}")
        try: pr = prints(opener)
        except Exception as e: warnings.append(f"FRED prints: {e}"); log(f"FRED prints failed: {e}")
    else:
        warnings.append("No FRED_API_KEY, so CPI and jobs dates were skipped")
    if FH_KEY:
        try: events += earnings(today, opener)
        except Exception as e: warnings.append(f"Earnings: {e}"); log(f"Earnings failed: {e}")
    else:
        warnings.append("No FINNHUB_API_KEY, so earnings were skipped")
    for e in events:
        if e["kind"] in ("cpi", "jobs", "pce", "retail", "gdp"): e["time"] = "8:30 am ET"
    events.sort(key=lambda e: (e["date"], {"fed": 0, "cpi": 1, "jobs": 1, "pce": 2, "gdp": 2, "retail": 3}.get(e["kind"], 5), e["title"]))
    cutoff = (today + timedelta(days=45)).isoformat()
    events = [e for e in events if e["date"] <= cutoff]
    data = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": events, "prints": pr, "warnings": warnings}
    json.dump(data, open(path, "w"), indent=1)
    log(f"Saved {len(events)} events, {len(pr)} prints, {len(warnings)} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
