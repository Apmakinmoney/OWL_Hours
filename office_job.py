"""Owl Hours HQ: the office robots.

  python office_job.py report   -> Chief of Staff report (7:00 am and 4:30 pm Central), watchlist desk, metals desk,
                                   risk officer, website director, data QA. 
  python office_job.py weekly   -> Saturday: the same report plus HR reviews + innovation
  python office_job.py inbox    -> read the CEO's emails to the office and answer them (free, rule-based)

Writes office.json for the app. Emails the CEO when GMAIL_USER, GMAIL_APP_PASSWORD and READ_TO are set.
Only mail FROM the READ_TO address is answered: nobody else can talk to the office.
"""
import email as emaillib, imaplib, json, os, re, smtplib, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from zoneinfo import ZoneInfo
import clockmath as cm

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://apmakinmoney.github.io/OWL_Hours/"
CT = ZoneInfo("America/Chicago")
NOW = datetime.now(timezone.utc)
BOT_TAG = "X-Owl-Office"


def load(name, default=None):
    try: return json.load(open(os.path.join(HERE, name)))
    except Exception: return default


def age_h(iso):
    try: return (NOW - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 3600
    except Exception: return None


def iso(): return NOW.isoformat(timespec="seconds")


def weekendish():
    l = NOW.astimezone(CT)
    return l.weekday() >= 5 or (l.weekday() == 0 and l.hour < 18)


# ---------------- robots ----------------
ROBOTS = [  # file, person, job, normal max age (hours)
    ("quotes.json", "Quinn", "prices", 20), ("latest.json", "Dana", "sector scores", 30), ("calendar.json", "Cal", "calendar", 30),
    ("paper.json", "Penny", "paper portfolios", 30), ("crypto.json", "Coco", "crypto", 3), ("companies.json", "Rex", "company research", 26),
    ("dailyread.json", "Wren", "daily read", 30), ("backtest.json", "Sage", "backtest", 24 * 8)]


def robots():
    out = []
    for f, n, job, mx in ROBOTS:
        d = load(f)
        a = age_h((d or {}).get("asOf") or (d or {}).get("date") or "") if d else None
        lim = mx + (72 if weekendish() and mx < 100 else 0)
        warns = len((d or {}).get("warnings") or [])
        ok = d is not None and a is not None and a <= lim
        note = "no file yet" if d is None else (f"{a:.0f}h old (limit {lim}h)" if not ok else f"fresh, {a:.1f}h old") + (f", {warns} warnings" if warns else "")
        out.append({"n": n, "job": job, "file": f, "ageH": None if a is None else round(a, 1), "ok": ok, "warn": warns, "note": note})
    return out


# ---------------- clock ----------------
def clock(prev):
    latest = load("latest.json", {})
    z, m = cm.from_latest(latest)
    ang, cl = cm.needle(m)
    if ang is None: return None
    ph = cm.phase(ang)
    strong = sorted([s for s in m if m[s] > 0], key=lambda s: -z[s])[:3]
    weak = sorted([s for s in m if m[s] < 0], key=lambda s: z[s])[:3]
    c = {"angle": round(ang, 1), "phase": ph[0], "hour": ph[1], "clarity": round(cl, 2), "word": cm.clarity_word(cl),
         "strong": [cm.NAMES[s] for s in strong], "weak": [cm.NAMES[s] for s in weak]}
    p = (prev or {}).get("clock")
    if p and p.get("angle") is not None:
        mv = (c["angle"] - p["angle"] + 540) % 360 - 180
        c["moved"] = round(mv, 1)
        c["movedTxt"] = ("forward " if mv > 0 else "back ") + f"{abs(mv):.0f}°" + (f", now {c['hour']}" if p.get("hour") != c["hour"] else "")
    return c


# ---------------- desks ----------------
def watch_desk():
    cfg, q, co, cal = load("config.json", {}), load("quotes.json", {}), load("companies.json", {}), load("calendar.json", {})
    syms = list(dict.fromkeys((cfg.get("featured") or []) + (cfg.get("customer_default") or [])))
    names = cfg.get("company_names") or {}
    uni = {u.get("sym"): u for u in (co.get("universe") or [])}
    rows, near = [], []
    for s in syms:
        qq = (q.get("quotes") or {}).get(s) or {}
        if not qq.get("price"): continue
        r = {"sym": s, "name": names.get(s, s), "price": qq["price"], "pct": qq.get("pct")}
        u = uni.get(s)
        if u:
            if u.get("hi52") and qq["price"] >= 0.97 * u["hi52"]: near.append(f"{s} is within 3% of its 52-week high"); r["tag"] = "near high"
            if u.get("lo52") and qq["price"] <= 1.05 * u["lo52"]: near.append(f"{s} is within 5% of its 52-week low"); r["tag"] = "near low"
            nw = u.get("news") or []
            if nw: r["news"] = nw[0].get("headline") or nw[0].get("h") or ""
        rows.append(r)
    rows.sort(key=lambda r: -abs(r.get("pct") or 0))
    today = NOW.astimezone(CT).date()
    soon = [e for e in (cal.get("events") or []) if e.get("kind") == "earnings" and e.get("symbol") in syms and
            0 <= (datetime.fromisoformat(e["date"]).date() - today).days <= 7]
    earn = [f"{e['symbol']} reports {e['date']}" for e in soon]
    up = [r for r in rows if (r.get("pct") or 0) > 0]
    line = f"{len(up)} of {len(rows)} names up last session." + (f" Biggest move: {rows[0]['sym']} {rows[0]['pct']:+.1f}%." if rows and rows[0].get("pct") is not None else "")
    return {"asOf": iso(), "line": line, "rows": rows, "earnings": earn, "near": near}


def metals_desk():
    m2 = (load("latest.json", {}) or {}).get("metals2") or {}
    rows = []
    for k in ("gold", "silver", "platinum", "palladium"):
        d = m2.get(k)
        if not d or not d.get("price"): continue
        tr = "above both" if d.get("m50") and d.get("m200") and d["price"] > d["m50"] > 0 and d["price"] > d["m200"] else \
             "below both" if d.get("m50") and d.get("m200") and d["price"] < d["m50"] and d["price"] < d["m200"] else "between"
        rows.append({"name": k.title(), "src": d.get("sym") or d.get("src"), "price": d["price"], "chg1": d.get("chg1"), "chg20": d.get("chg20"), "trend": tr})
    g = next((r for r in rows if r["name"] == "Gold"), None)
    line = (f"Gold ${g['price']:,.0f}, {g['chg20']:+.1f}% over 20 days, {g['trend']} its 50- and 200-day averages." if g and g.get("chg20") is not None else "No gold price yet.")
    return {"asOf": iso(), "line": line, "rows": rows}


def risk_desk():
    p = load("paper.json", {}) or {}
    rows, warn = [], []
    for k, v in (p.get("models") or {}).items():
        nav, peak = v.get("nav") or 0, v.get("peak") or v.get("nav") or 1
        dd = (nav / peak - 1) * 100 if peak else 0
        rows.append({"id": k, "name": v.get("name", k), "nav": round(nav), "ret": v.get("ret"), "dd": round(dd, 2), "guard": bool(v.get("guardOn"))})
        if dd <= -8: warn.append(f"{v.get('name', k)} is {dd:.1f}% below its high")
        if v.get("guardOn"): warn.append(f"{v.get('name', k)}: drawdown guard is ON (in cash)")
    line = (f"Since {p.get('start')}: " + ", ".join(f"{r['name'].split(':')[0]} {r['ret']:+.2f}%" for r in rows if r["id"] in ("spy", "B", "t3") and r.get("ret") is not None)) if rows else "No paper portfolios yet."
    return {"asOf": iso(), "line": line, "rows": rows, "warn": warn}


def website_check():
    out = {"asOf": iso(), "checks": []}
    for path, need in (("", b"Owl"), ("latest.json", b"sectors"), ("manifest.webmanifest", b"name")):
        t0 = time.time()
        try:
            req = urllib.request.Request(SITE + path + ("?t=%d" % time.time() if path else ""), headers={"User-Agent": "owl-office"})
            body = urllib.request.urlopen(req, timeout=20).read()
            ok = need in body
            out["checks"].append({"name": path or "home page", "ok": ok, "ms": int((time.time() - t0) * 1000), "note": "loads" if ok else "loaded but looks wrong"})
            if path == "latest.json" and ok:
                live = json.loads(body).get("asOf"); repo = (load("latest.json", {}) or {}).get("asOf")
                if live != repo: out["checks"].append({"name": "site is up to date", "ok": False, "note": "the live site is still showing older data than the repo"})
        except Exception as e:
            out["checks"].append({"name": path or "home page", "ok": False, "note": "couldn't load (" + (str(getattr(e, "code", "")) or type(e).__name__) + ")"})
    out["ok"] = all(c["ok"] for c in out["checks"])
    out["line"] = "Website is up, data files load." if out["ok"] else "Website problem: " + "; ".join(c["name"] + " " + c["note"] for c in out["checks"] if not c["ok"])
    return out


def data_qa():
    checks = []
    q = load("quotes.json", {}) or {}
    bad = [s for s, v in (q.get("quotes") or {}).items() if not v.get("price")]
    stale = [s for s, v in (q.get("quotes") or {}).items() if v.get("stale")]
    checks.append({"name": "prices", "ok": not bad, "note": f"{len(q.get('quotes') or {})} prices" + (f", missing: {', '.join(bad[:8])}" if bad else "") + (f", {len(stale)} stale" if stale else "")})
    lt = load("latest.json", {}) or {}
    miss = [s for s, v in (lt.get("sectors") or {}).items() if v.get("rel20") is None]
    checks.append({"name": "sector scores", "ok": len(lt.get("sectors") or {}) >= 14 and not miss, "note": f"{len(lt.get('sectors') or {})} sectors" + (f", no 20-day trend: {', '.join(miss)}" if miss else "")})
    co = load("companies.json", {}) or {}
    nomc = [u["sym"] for u in (co.get("universe") or []) if u.get("kind") == "stock" and not u.get("mcap")]
    checks.append({"name": "company detail", "ok": not nomc, "note": f"{len(co.get('universe') or [])} companies" + (f", missing detail: {', '.join(nomc[:8])}" if nomc else "")})
    m2 = lt.get("metals2") or {}
    checks.append({"name": "metals", "ok": all((m2.get(k) or {}).get("price") for k in ("gold", "silver", "platinum", "palladium")), "note": ", ".join(k for k in ("gold", "silver", "platinum", "palladium") if (m2.get(k) or {}).get("price")) or "none"})
    warns = []
    for f in ("latest.json", "calendar.json", "companies.json", "backtest.json"):
        for w in ((load(f, {}) or {}).get("warnings") or []): warns.append(f"{f}: {w}")
    known = [w for w in warns if "XAG/USD" in w or "XPT/USD" in w or "XPD/USD" in w]
    real = [w for w in warns if w not in known]
    checks.append({"name": "robot warnings", "ok": not real, "note": (f"{len(real)} new: " + "; ".join(real[:4])) if real else "none new" + (f" ({len(known)} known: free plan has no silver/platinum/palladium spot)" if known else "")})
    ok = all(c["ok"] for c in checks)
    return {"asOf": iso(), "ok": ok, "checks": checks, "line": "All data checks pass." if ok else "Data issues: " + "; ".join(c["name"] for c in checks if not c["ok"]) + "."}


# ---------------- weekly ----------------
WF_PERSON = {"Owl quotes": "Quinn", "Owl daily data": "Dana", "Owl crypto": "Coco", "Owl companies": "Rex", "Owl backtest": "Sage",
             "Owl daily read": "Wren", "Owl office": "Morgan", "Owl office inbox": "Morgan"}


def hr_reviews():
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY", "Apmakinmoney/OWL_Hours")
    since = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
    runs = []
    try:
        for page in range(1, 6):
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs?per_page=100&page={page}&created=%3E%3D{since}",
                                         headers={"Accept": "application/vnd.github+json", "User-Agent": "owl-office", **({"Authorization": f"Bearer {tok}"} if tok else {})})
            d = json.load(urllib.request.urlopen(req, timeout=30))
            runs += d.get("workflow_runs") or []
            if len(d.get("workflow_runs") or []) < 100: break
    except Exception as e:
        return {"asOf": iso(), "rows": [], "line": f"Could not read the run history: {e}"[:160]}
    by = {}
    for r in runs:
        if r.get("status") != "completed": continue
        b = by.setdefault(r.get("name") or "?", {"runs": 0, "ok": 0, "fail": 0})
        b["runs"] += 1; b["ok" if r.get("conclusion") in ("success", "skipped") else "fail"] += 1
    rows = []
    for name, b in sorted(by.items()):
        rate = round(100 * b["ok"] / b["runs"]) if b["runs"] else 0
        grade = "A" if rate >= 98 else "B" if rate >= 90 else "C" if rate >= 75 else "Needs help"
        rows.append({"workflow": name, "person": WF_PERSON.get(name, name), **b, "rate": rate, "grade": grade})
    weak = [r for r in rows if r["rate"] < 90]
    line = f"{sum(r['runs'] for r in rows)} robot runs this week, {sum(r['fail'] for r in rows)} failed." + (" Needs a look: " + ", ".join(f"{r['person']} ({r['rate']}%)" for r in weak) if weak else " Everyone gets an A or B.")
    return {"asOf": iso(), "rows": rows, "line": line}


def innovation():
    bt = load("backtest.json", {}) or {}
    lines = []
    v = bt.get("verdict") or {}
    if v.get("bestName"): lines.append(f"Best tested model: {v['bestName']}. It beat {', '.join(v.get('beatsSharpe') or []) or 'nothing'} on risk-adjusted return and ranked in the top {100 - (v.get('randomPercentile') or 0)}% vs 200 random pickers.")
    rs = bt.get("research") or {}
    if rs.get("spa"):
        p = rs["spa"].get("pConsistent")
        lines.append(f"Luck test (SPA) p = {p}: " + ("strong evidence the edge is real." if p is not None and p < 0.05 else "can't rule out luck yet." if p is not None else ""))
    if not rs: lines.append("The new 27-year backtest (luck test, confidence cone, direction study) hasn't run yet. Next test: run it.")
    else:
        lines.append("Next test to try: " + ("add a valuation filter so the clock avoids sectors that are already expensive." if rs.get("spa", {}).get("pConsistent", 1) < 0.1 else "give it more history before adding new rules."))
    ps = bt.get("phaseStudy") or []
    night = next((x for x in ps if x.get("hour") == "Night"), None)
    if night: lines.append(f"Night has been followed by SPY {night.get('spyNext'):+.2f}% the next month, up {night.get('spyUp'):.0f}% of the time.")
    return {"asOf": iso(), "lines": lines, "line": lines[0] if lines else "No backtest yet."}


# ---------------- engineering + chief of staff ----------------
def engineering():
    ch = load("changes.json", {}) or {}
    items = ch.get("changes") or []
    pend = [c for c in items if c.get("status") == "pending"]
    last = next((c for c in items if c.get("status") == "shipped"), None)
    return {"asOf": iso(), "pending": len(pend), "pendingTitles": [c["title"] for c in pend], "last": last and {"id": last["id"], "title": last["title"], "date": last.get("date")},
            "line": (f"{len(pend)} change request(s) waiting for your approval: " + "; ".join(c["title"] for c in pend)) if pend else (f"No requests waiting. Last shipped: {last['id']} {last['title']}." if last else "No changes logged yet.")}


def chief_of_staff(o, slot):
    bots = o["robots"]; bad = [b for b in bots if not b["ok"]]
    c = o.get("clock")
    lines = []
    if c:
        lines.append(f"Clock: {c['hour']} ({c['phase'].lower()}), {c['word']} signals" + (f", moved {c['movedTxt']} since last report" if c.get("movedTxt") else "") + ".")
        if c["strong"]: lines.append("Strongest: " + ", ".join(c["strong"]) + ". Weakest: " + ", ".join(c["weak"] or ["none"]) + ".")
    lines.append(f"Robots: {len(bots) - len(bad)} of {len(bots)} on schedule." + (" Late: " + ", ".join(f"{b['n']} ({b['note']})" for b in bad) if bad else ""))
    for k in ("watch", "metals", "risk", "site", "qa", "eng"):
        if o.get(k) and o[k].get("line"): lines.append(o[k]["line"])
    needs = [f"{b['n']} ({b['job']}) is late" for b in bad]
    needs += o.get("risk", {}).get("warn", [])
    if not o.get("site", {}).get("ok", True): needs.append(o["site"]["line"])
    if not o.get("qa", {}).get("ok", True): needs.append(o["qa"]["line"])
    if o.get("eng", {}).get("pending"): needs.append(o["eng"]["line"])
    head = ("Good morning" if slot == "am" else "Saturday review" if slot == "weekly" else "After the close") + (", CEO. All clear." if not needs else f", CEO. {len(needs)} thing(s) need your eyes.")
    return {"asOf": iso(), "slot": slot, "headline": head, "lines": lines, "needs": needs}


# ---------------- email ----------------
def send(subject, text, html=None, reply_to_msg=None):
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "READ_TO"))
    if not (user and pw and to): print("Email not set up; skipping send.", flush=True); return False
    ceo = to.split(",")[0].strip()
    msg = MIMEMultipart("alternative"); msg["Subject"] = subject; msg["From"] = f"Owl Hours HQ <{user}>"; msg["To"] = ceo; msg[BOT_TAG] = "1"
    if reply_to_msg is not None and reply_to_msg.get("Message-ID"):
        msg["In-Reply-To"] = reply_to_msg["Message-ID"]; msg["References"] = reply_to_msg["Message-ID"]
    msg.attach(MIMEText(text, "plain"))
    if html: msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw); s.sendmail(user, [ceo], msg.as_string())
    print("Emailed the CEO:", subject, flush=True); return True


FOOT = "\n\nReply with one word to ask the office: status, watchlist, metals, clock, risk, website, engineering, or a ticker like NVDA. Reply APPROVED or DENIED to answer a change request.\nOpen HQ: " + SITE + "#lab"


def report_email(o):
    cos = o["cos"]
    t = [cos["headline"], ""]
    if cos["needs"]: t += ["Needs your eyes:"] + ["- " + n for n in cos["needs"]] + [""]
    t += cos["lines"]
    w = o.get("watch") or {}
    if w.get("rows"): t += ["", "Watchlist:"] + [f"- {r['sym']} ${r['price']:,.2f} {r['pct']:+.2f}%" + (f" ({r['tag']})" if r.get("tag") else "") for r in w["rows"][:10] if r.get("pct") is not None]
    if w.get("earnings"): t += ["", "Earnings this week: " + "; ".join(w["earnings"])]
    m = o.get("metals") or {}
    if m.get("rows"): t += ["", "Metals:"] + [f"- {r['name']} ${r['price']:,.2f}" + (f", 20 days {r['chg20']:+.1f}%" if r.get("chg20") is not None else "") + f", {r['trend']} its 50/200-day averages" for r in m["rows"]]
    if o.get("hr") and o["hr"].get("asOf", "")[:10] == iso()[:10]: t += ["", "HR weekly review: " + o["hr"]["line"]] + [f"- {r['person']}: {r['rate']}% ({r['grade']})" for r in o["hr"]["rows"]]
    if o.get("innovation") and o["innovation"].get("asOf", "")[:10] == iso()[:10]: t += ["", "Innovation weekly:"] + ["- " + l for l in o["innovation"]["lines"]]
    txt = "\n".join(t) + FOOT
    html = "<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:600px;line-height:1.45'>" + "".join(
        f"<h2 style='margin:0 0 6px'>{l}</h2>" if i == 0 else ("<br>" if not l else f"<div>{l}</div>") for i, l in enumerate(t)) + \
        "<hr><div style='color:#777;font-size:13px'>" + FOOT.strip().replace("\n", "<br>") + "</div></div>"
    when = {"am": "7 am", "pm": "4:30 pm", "weekly": "Saturday"}.get(cos["slot"], "")
    return send(f"Owl HQ {when}: {cos['headline'].split('. ', 1)[-1]}", txt, html)


# ---------------- answers (same words as the app's office chat) ----------------
def answer(q, o):
    w = q.strip().lower()
    word = re.sub(r"[^a-z0-9 ]", " ", w).split()
    first = word[0] if word else ""
    qs = load("quotes.json", {}) or {}
    sym = q.strip().split()[0].upper().strip("$.,!?") if q.strip() else ""
    if first in ("approved", "approve", "yes", "denied", "deny", "no"):
        return None
    if sym and sym in (qs.get("quotes") or {}):
        v = qs["quotes"][sym]
        co = next((u for u in (load("companies.json", {}) or {}).get("universe", []) if u.get("sym") == sym), None)
        s = f"{sym}: ${v['price']:,.2f}, {v.get('pct', 0):+.2f}% last session."
        if co:
            if co.get("pe"): s += f" P/E {co['pe']}."
            if co.get("hi52"): s += f" 52-week range ${co['lo52']:,.2f} to ${co['hi52']:,.2f}."
            if co.get("news"): s += " Latest headline: " + (co["news"][0].get("headline") or "")
        return s
    if any(k in w for k in ("watch", "mover")): d = o.get("watch") or watch_desk(); return d["line"] + "\n" + "\n".join(f"- {r['sym']} {r['pct']:+.2f}%" for r in d["rows"][:10] if r.get("pct") is not None) + ("\nEarnings: " + "; ".join(d["earnings"]) if d.get("earnings") else "")
    if any(k in w for k in ("metal", "gold", "silver", "platinum", "palladium")): d = o.get("metals") or metals_desk(); return d["line"] + "\n" + "\n".join(f"- {r['name']} ${r['price']:,.2f}, {r['trend']} its averages" for r in d["rows"])
    if any(k in w for k in ("clock", "needle", "phase", "sector")):
        c = o.get("clock") or clock(None)
        return f"{c['hour']} ({c['phase'].lower()}), needle {c['angle']}°, {c['word']} signals. Strongest: {', '.join(c['strong'])}. Weakest: {', '.join(c['weak'])}." if c else "No clock read yet."
    if any(k in w for k in ("risk", "paper", "portfolio", "drawdown")): d = o.get("risk") or risk_desk(); return d["line"] + ("\n" + "\n".join(d["warn"]) if d["warn"] else "\nNo drawdown alarms.")
    if any(k in w for k in ("site", "website", "web", "qa", "data")): return (o.get("site") or {}).get("line", "") + "\n" + (o.get("qa") or {}).get("line", "")
    if any(k in w for k in ("eng", "code", "change", "build", "atlas")): return engineering()["line"]
    if any(k in w for k in ("hr", "review")): return (o.get("hr") or {}).get("line", "HR reviews run on Saturdays.")
    if any(k in w for k in ("idea", "innov", "lab", "backtest")): return "\n".join((o.get("innovation") or innovation())["lines"])
    if any(k in w for k in ("status", "report", "robot", "how", "update", "brief")): c = o.get("cos") or {}; return (c.get("headline", "") + "\n" + "\n".join(c.get("lines", []))).strip()
    return ("I run on free rules for now, so I know these words: status, watchlist, metals, clock, risk, website, engineering, HR, ideas, "
            "or any ticker (NVDA). Smart free-form answers switch on when you add an AI key later.")


def inbox():
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "READ_TO"))
    if not (user and pw and to): print("Email not set up; inbox skipped.", flush=True); return
    ceo = to.split(",")[0].strip().lower()
    o = load("office.json", {}) or {}
    appr = load("approvals.json", {"decisions": []})
    M = imaplib.IMAP4_SSL("imap.gmail.com"); M.login(user, pw)
    if M.select('"[Gmail]/All Mail"')[0] != "OK": M.select("INBOX")
    # Gmail search: your mail from the last 2 days that the office hasn't handled yet (handled mail gets the label owldone)
    typ, data = M.search(None, "X-GM-RAW", f'"from:{ceo} newer_than:2d -label:owldone"')
    ids = data[0].split() if data and data[0] else []
    answered = 0
    for i in ids[:10]:
        typ, raw = M.fetch(i, "(RFC822)")
        msg = emaillib.message_from_bytes(raw[0][1])
        mine = msg.get(BOT_TAG) or (msg.get("Subject", "").startswith("Owl") and not msg.get("In-Reply-To"))
        M.store(i, "+X-GM-LABELS", "owldone")
        if mine or parseaddr(msg.get("From", ""))[1].lower() != ceo: continue
        body = ""
        for part in (msg.walk() if msg.is_multipart() else [msg]):
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace"); break
        first = ""
        for l in body.splitlines():
            if re.match(r"^\s*(On .+wrote:|>|-----)", l): break
            if l.strip(): first = l.strip(); break
        subj = re.sub(r"^(re|fwd?):\s*", "", msg.get("Subject", ""), flags=re.I).strip()
        q = first or subj
        if not q: continue
        w = q.lower().split()[0].strip(".,!")
        if w in ("approved", "approve", "yes", "denied", "deny", "no"):
            dec = "approved" if w in ("approved", "approve", "yes") else "denied"
            ch = load("changes.json", {}) or {}
            pend = [c for c in (ch.get("changes") or []) if c.get("status") == "pending"]
            target = pend[0]["id"] if pend else (q.split()[1] if len(q.split()) > 1 else "latest")
            appr["decisions"].insert(0, {"id": target, "decision": dec, "note": q[:200], "at": iso()})
            json.dump(appr, open(os.path.join(HERE, "approvals.json"), "w"), indent=1)
            reply = f"Logged: {target} {dec.upper()}. Atlas (lead engineer) will see it in approvals.json before the next build."
        else:
            reply = answer(q, o)
        send("Re: " + (msg.get("Subject") or "Owl office"), "Morgan, Chief of Staff:\n\n" + reply + FOOT, reply_to_msg=msg)
        answered += 1
    M.logout(); print(f"Answered {answered} email(s).", flush=True)


def main(mode):
    prev = load("office.json", {}) or {}
    if mode == "inbox": return inbox()
    local = NOW.astimezone(CT)
    sched = os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    o = dict(prev); o["asOf"] = iso()
    if mode == "report":
        if sched and not ((local.hour == 7) or (local.hour == 16 and local.minute >= 15) or (local.hour == 17 and local.minute < 15)):
            print(f"Not 7:00 or 4:30 Central (it's {local:%H:%M}); daylight-saving duplicate, skipping.", flush=True); return
    if mode in ("report", "weekly"):
        slot = "weekly" if mode == "weekly" else "am" if local.hour < 12 else "pm"
        o["robots"] = robots(); o["clock"] = clock(prev)
        o["watch"] = watch_desk(); o["metals"] = metals_desk(); o["risk"] = risk_desk()
        o["site"] = website_check(); o["qa"] = data_qa(); o["eng"] = engineering()
        if mode == "weekly": o["hr"] = hr_reviews(); o["innovation"] = innovation()
        o["cos"] = chief_of_staff(o, slot)
    json.dump(o, open(os.path.join(HERE, "office.json"), "w"), indent=1)
    print(json.dumps(o.get("cos"), indent=1)[:3000])
    if mode in ("report", "weekly"):
        try: report_email(o)
        except Exception as e: print(f"Email failed: {e}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "report")
