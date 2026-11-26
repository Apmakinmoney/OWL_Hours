"""Builds the weekly letter draft from latest.json, snapshots/ and editorial.json.

Outputs (in draft/):
  letter-DRAFT.pdf   the letter with DRAFT marks, for your review
  context.json       every number and line of text in the draft, frozen so the approved letter matches it exactly
  meta.json          headline and summary, used by publish.py
The clean letter (no DRAFT marks) is only built by publish.py, after you approve.
  issue_title.txt, issue_body.md, issue_label.txt   used to open the approval issue

If the data is stale or incomplete it builds nothing and writes a "needs attention" issue instead.
Needs reportlab (pip install reportlab).
"""
import glob, json, math, os, sys
from datetime import datetime, timezone, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle

HERE = os.path.dirname(os.path.abspath(__file__))
def load(name, default=None):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else default
CFG, ED, LIB = load("config.json", {}), load("editorial.json", {}), load("library.json", {})
BRAND = CFG.get("brand", "Market Talks")
W, H = letter
NAVY = HexColor("#0C1430"); PLATE = HexColor("#121c40"); BRASS = HexColor("#E0B25B"); BRASS_D = HexColor("#8a6212"); INK = HexColor("#14213D")
MUTED = HexColor("#5B6784"); LINE = HexColor("#CBD3E2"); PAPER = HexColor("#F4F6FA"); UPD = HexColor("#13795B"); DOWND = HexColor("#C2432F")
UP = HexColor("#4FD1A5"); DOWN = HexColor("#FF7B66")
PHASES = [("Recovery", 0, 90, HexColor("#5B8CFF")), ("Expansion", 90, 180, HexColor("#4FD1A5")), ("Late cycle", 180, 270, HexColor("#E0B25B")), ("Contraction", 270, 360, HexColor("#A58BFF"))]
SECT = [("FIN", "FIN", "Financials", 8), ("REIT", "REIT", "Real estate", 22), ("DISC", "DISC", "Consumer discretionary", 36), ("TECH", "TECH", "Tech and software", 52),
        ("CYB", "CYBR", "Cybersecurity", 66), ("NEO", "AI-DC", "Neo-cloud and data centers", 80), ("SEMI", "SEMI", "Semiconductors", 94), ("COMM", "COMM", "Communication services", 112),
        ("IND", "IND", "Industrials", 132), ("MAT", "MAT", "Materials", 165), ("ENGY", "ENGY", "Energy", 200), ("GOLD", "GOLD", "Gold miners", 222),
        ("STPL", "STPL", "Consumer staples", 240), ("HLTH", "HLTH", "Healthcare", 280), ("UTIL", "UTIL", "Utilities", 320)]
REG = {"10": ("Goldilocks", 65, 60, "Growth stocks, tech and consumer discretionary have tended to lead."),
       "11": ("Reflation", 175, 60, "Energy, materials, industrials and financials have tended to lead."),
       "00": ("Slowdown", 305, 60, "Government bonds and defensive stocks have tended to lead."),
       "01": ("Stagflation squeeze", 240, 55, "Energy, gold and defensives have tended to hold up. Stocks and bonds both struggle.")}
WORD = {2: "rising hard", 1: "rising", 0: "flat", -1: "falling", -2: "falling hard"}
MNAME = {"y10": "10-year Treasury yield (%)", "y2": "2-year Treasury yield (%)", "curve": "Yield curve, 10y minus 2y (pts)", "hy": "High-yield credit spread (%)",
         "oil": "Oil, WTI ($)", "brent": "Oil, Brent ($)", "vix": "VIX", "ism": "ISM manufacturing", "usd": "US dollar index", "btc": "Bitcoin ($)", "eth": "Ether ($)", "xrp": "XRP ($)",
         "gold": "Gold (GLD, direction)", "silver": "Silver (SLV, direction)"}

def norm(a): return a % 360
def phase_of(a):
    a = norm(a)
    for n, lo, hi, _ in PHASES:
        if lo <= a < hi: return n
    return "Recovery"
def pt(cx, cy, a, r): t = math.radians(a); return cx + r * math.sin(t), cy + r * math.cos(t)
def fmt(v, nd=2): return "n/a" if v is None else f"{v:,.{nd}f}"
def dword(d): return {1: "rising", 0: "flat", -1: "falling"}.get(d, "n/a")

def estimate(scores):
    sx = sy = tot = 0
    for sid, _, _, ang in SECT:
        v = scores.get(sid, 0); t = math.radians(ang)
        sx += v * math.sin(t); sy += v * math.cos(t); tot += abs(v)
    if tot == 0 or math.hypot(sx, sy) < 1e-6: return None, 0
    return norm(math.degrees(math.atan2(sx, sy))), math.hypot(sx, sy) / tot

def regime(macro):
    def d(k): return macro.get(k, {}).get("dir")
    g = i = gn = inn = 0
    if d("ism") is not None: g += d("ism"); gn += 1
    if d("hy") is not None: g -= d("hy"); gn += 1
    if d("curve") is not None: g += .5 * d("curve"); gn += 1
    if d("oil") is not None: i += d("oil"); inn += 1
    if d("y10") is not None: i += .5 * d("y10"); inn += 1
    if d("usd") is not None: i -= .5 * d("usd"); inn += 1
    gs = None if not gn else ("up" if g >= .5 else "down" if g <= -.5 else "mixed")
    is_ = None if not inn else ("up" if i >= .5 else "down" if i <= -.5 else "mixed")
    key = None
    if gs in ("up", "down") and is_ in ("up", "down"): key = ("1" if gs == "up" else "0") + ("1" if is_ == "up" else "0")
    return key, gs, is_

def nearest_regime(angle):
    if angle is None: return None
    return min(REG, key=lambda k: abs(((angle - REG[k][1] + 540) % 360) - 180))

# ---------- load data ----------
def previous_scores(latest_day):
    files = sorted(glob.glob(os.path.join(HERE, "snapshots", "*.json")))
    cands = []
    for f in files:
        day = os.path.basename(f)[:10]
        if day < latest_day: cands.append((day, f))
    if not cands: return None
    cutoff = (datetime.strptime(latest_day, "%Y-%m-%d") - timedelta(days=5)).strftime("%Y-%m-%d")
    pick = [c for c in cands if c[0] <= cutoff]
    day, f = (pick[-1] if pick else cands[0])
    d = json.load(open(f))
    return day, {k: v["suggested"] for k, v in d.get("sectors", {}).items()}

def check(latest):
    reasons = []
    try: age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest["asOf"])).total_seconds() / 3600
    except Exception: age = 1e9
    if age > CFG.get("max_data_age_hours", 72): reasons.append(f"The data is {age:.0f} hours old (limit {CFG.get('max_data_age_hours', 72)}).")
    if len(latest.get("macro", {})) < 4: reasons.append("Fewer than 4 macro series came through.")
    if len(latest.get("etf", {})) < 3: reasons.append("Fewer than 3 ETF price histories came through.")
    if len(latest.get("sectors", {})) < 10: reasons.append("Fewer than 10 sector scores came through.")
    reasons += [f"Source warning: {w}" for w in latest.get("warnings", [])]
    blocking = [r for r in reasons if not r.startswith("Source warning")]
    return blocking, reasons

# ---------- drawing helpers ----------
def st(sz=9.4, ld=13, col=INK, f="Helvetica"): return ParagraphStyle("p", fontName=f, fontSize=sz, leading=ld, textColor=col)
def para(c, t, x, y, w, s):
    p = Paragraph(t, s); _, h = p.wrap(w, 900); p.drawOn(c, x, y - h); return y - h
def esc(t): return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
HDR, CELL = st(8.7, 11, MUTED, "Helvetica-Bold"), st(8.7, 11.3)
def table(c, rows, widths, x, ytop, pad=3.2):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRASS), ("LINEBELOW", (0, 1), (-1, -1), .5, LINE),
                           ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LEFTPADDING", (0, 0), (-1, -1), 4)]))
    _, h = t.wrap(sum(widths), 700); t.drawOn(c, x, ytop - h); return ytop - h
def box(c, x, top, w, kick, title, paras, fs=9.0):
    s = st(fs, fs * 1.4); ps = [Paragraph(p, s) for p in paras]; hh = sum(p.wrap(w, 1000)[1] + 5 for p in ps); bh = hh + 52
    c.setFillColor(PAPER); c.roundRect(x - 12, top - bh, w + 24, bh, 10, fill=1, stroke=0)
    c.setFillColor(BRASS_D); c.setFont("Helvetica-Bold", 9.4); c.drawString(x, top - 18, kick)
    c.setFillColor(INK); c.setFont("Times-Bold", 15); c.drawString(x, top - 38, title)
    y = top - 48
    for p in ps: _, hp = p.wrap(w, 1000); p.drawOn(c, x, y - hp); y -= hp + 5
    return top - bh

def wheel(c, cx, cy, scores, angle):
    def ring(a0, a1, r0, r1, col, alpha):
        n = max(8, int((a1 - a0) / 2)); pts = [pt(cx, cy, a0 + (a1 - a0) * i / n, r1) for i in range(n + 1)] + [pt(cx, cy, a1 - (a1 - a0) * i / n, r0) for i in range(n + 1)]
        p = c.beginPath(); p.moveTo(*pts[0]); [p.lineTo(*q) for q in pts[1:]]; p.close()
        c.setFillColor(col); c.setFillAlpha(alpha); c.drawPath(p, fill=1, stroke=0); c.setFillAlpha(1)
    for n, a0, a1, col in PHASES:
        ring(a0 + 1.2, a1 - 1.2, 82, 117, col, .16); ring(a0 + 1.2, a1 - 1.2, 119, 121.5, col, 1)
        lx, ly = pt(cx, cy, (a0 + a1) / 2, 141); c.setFillColor(col); c.setFont("Times-Bold", 9.5); c.drawCentredString(lx, ly - 3, n)
    c.setStrokeColor(HexColor("#8d9ac0"))
    for a in range(0, 360, 5):
        maj = a % 15 == 0; x0, y0 = pt(cx, cy, a, 124); x1, y1 = pt(cx, cy, a, 124 + (4 if maj else 2.5)); c.setLineWidth(.7 if maj else .4); c.line(x0, y0, x1, y1)
    c.setStrokeColor(HexColor("#2f3d6e")); c.setLineWidth(.6); c.circle(cx, cy, 82, stroke=1, fill=0)
    if angle is not None:
        p = c.beginPath(); p.moveTo(cx, cy)
        for i in range(31): p.lineTo(*pt(cx, cy, angle - 30 + i * 2, 78))
        p.close(); c.setFillColor(BRASS); c.setFillAlpha(.22); c.drawPath(p, fill=1, stroke=0); c.setFillAlpha(1)
    for sid, code, _, ang in SECT:
        v = scores.get(sid, 0); x, y = pt(cx, cy, ang, 99.5)
        fill, stroke, txt = HexColor("#1e2b55"), HexColor("#3a4772"), HexColor("#8d9ac0")
        if v == 2: fill, stroke, txt = UP, HexColor("#a8f0d6"), HexColor("#06231b")
        elif v == 1: fill, stroke, txt = HexColor("#2c8c73"), UP, HexColor("#f1fffa")
        elif v == -1: fill, stroke, txt = HexColor("#a14b47"), DOWN, HexColor("#fff4f1")
        elif v == -2: fill, stroke, txt = DOWN, HexColor("#ffc2b6"), HexColor("#2b0c06")
        c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(.9); c.circle(x, y, 8.6 + abs(v) * .9, fill=1, stroke=1)
        c.setFillColor(txt); c.setFont("Helvetica-Bold", 4.6 if len(code) > 4 else 5.2); c.drawCentredString(x, y - 1.7, code)
    if angle is not None:
        tx, ty = pt(cx, cy, angle, 74); bx, by = pt(cx, cy, angle + 180, 14); c.setStrokeColor(BRASS); c.setLineWidth(1.8); c.line(bx, by, tx, ty)
        lx, ly = pt(cx, cy, angle - 5, 60); rx, ry = pt(cx, cy, angle + 5, 60); hx, hy = pt(cx, cy, angle, 80)
        p = c.beginPath(); p.moveTo(hx, hy); p.lineTo(lx, ly); p.lineTo(tx, ty); p.lineTo(rx, ry); p.close(); c.setFillColor(BRASS); c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(NAVY); c.setStrokeColor(BRASS); c.setLineWidth(1.6); c.circle(cx, cy, 4.6, fill=1, stroke=1)

# ---------- build ----------
def compute(latest):
    """Turns the data and editorial.json into everything the letter shows. Saved as draft/context.json,
    so the approved letter is rebuilt from exactly what you reviewed."""
    day = latest["asOf"][:10]; macro = dict(latest.get("macro", {}))
    for k, v in (ED.get("manual_macro") or {}).items():
        if v and (v.get("dir") is not None or v.get("level") is not None): macro[k] = {"level": v.get("level"), "dir": v.get("dir"), "source": "author"}
    sect = latest.get("sectors", {})
    scores = {k: v["suggested"] for k, v in sect.items()}
    overrides = {}
    for k, v in (ED.get("sector_overrides") or {}).items():
        v = int(v)
        if scores.get(k) != v: overrides[k] = v
        scores[k] = v
    angle, clarity = estimate(scores); phase = phase_of(angle) if angle is not None else "No signal"
    rkey, gs, is_ = regime(macro); wkey = nearest_regime(angle)
    prev = previous_scores(day); pangle = estimate(prev[1])[0] if prev else None
    mechanical = []

    diverge = bool(rkey and wkey and rkey != wkey)
    if ED.get("headline"): headline = ED["headline"]
    else:
        mechanical.append("headline")
        if angle is None: headline = "Not enough signal to read the cycle this week"
        elif diverge: headline = "Sector momentum and the macro data disagree"
        elif rkey: headline = f"Momentum and data agree: the backdrop looks like {REG[rkey][0].lower()}"
        else: headline = f"Sector momentum points to {phase.lower()}, but the macro picture is incomplete"
    if ED.get("dek"): dek = ED["dek"]
    else:
        mechanical.append("dek")
        dek = (f"Sector momentum puts the wheel in the {phase} zone at {angle:.0f}° with {clarity*100:.0f}% signal clarity. " +
               (f"The macro signals lean toward {REG[rkey][0].lower()}. " if rkey else "") + ("That gap is the story this issue." if diverge else "")) if angle is not None else "Not enough sector data to read the cycle."
    reads = [r for r in (ED.get("reads") or ["", "", ""])] + ["", "", ""]
    names = {s[0]: s[2] for s in SECT}
    if not reads[0]:
        mechanical.append("read 1")
        if prev and pangle is not None and angle is not None:
            mv = sorted(((k, scores.get(k, 0) - prev[1].get(k, 0)) for k in scores), key=lambda kv: -abs(kv[1]))[:3]
            parts = [f"{names.get(k, k)} momentum went from {WORD[prev[1].get(k, 0)]} to {WORD[scores[k]]}" for k, dlt in mv if dlt]
            dd = ((angle - pangle + 540) % 360) - 180
            reads[0] = f"The needle moved {abs(dd):.0f}° since {prev[0]}, from {phase_of(pangle)} to {phase}. " + ("; ".join(parts) + "." if parts else "Sector momentum was little changed.")
        else: reads[0] = "This is the first issue with automated tracking, so there is no earlier week to compare."
    if not reads[1]:
        mechanical.append("read 2")
        bits = []
        for k, label in (("y10", "The 10-year yield"), ("oil", "Oil (WTI)"), ("hy", "The high-yield spread"), ("curve", "The 10y minus 2y curve")):
            m = macro.get(k)
            if m and m.get("level") is not None: bits.append(f"{label} is {fmt(m['level'])} and {dword(m.get('dir'))}")
        reads[1] = (". ".join(bits) + ".") if bits else "Macro data was limited this week."
    if not reads[2]:
        mechanical.append("read 3")
        if rkey and angle is not None:
            reads[2] = (f"Sector momentum leans toward {REG[wkey][0].lower()} while the macro signals point to {REG[rkey][0].lower()}. Either prices are ahead of the data, or the data has not confirmed the move yet." if diverge
                        else f"Sector momentum and the macro signals both point toward {REG[rkey][0].lower()}, which strengthens the story.")
        else: reads[2] = "Not enough growth and inflation signals came through to check the wheel against the data."
    wk = datetime.fromisoformat(latest["asOf"]).isocalendar()[1]
    q = ED.get("quote") or {}
    quote = q if q.get("text") else (LIB.get("quotes") or [{"text": "", "by": "", "why": ""}])[wk % max(1, len(LIB.get("quotes", [1])))]
    qa = ED.get("question") or {}
    if not qa.get("q"): qa = (LIB.get("questions") or [{"q": "", "a": ""}])[wk % max(1, len(LIB.get("questions", [1])))]
    fact = ED.get("fun_fact") or (LIB.get("facts") or [""])[wk % max(1, len(LIB.get("facts", [1])))]
    events = sorted([e for e in ED.get("events", []) if e.get("date", "") >= day], key=lambda e: e["date"])[:8]
    cmm = [str(x).strip() for x in (ED.get("change_my_mind") or []) if str(x).strip()][:4]
    return {"day": day, "asOf": latest["asOf"], "warnings": latest.get("warnings", []), "headline": headline, "dek": dek, "reads": reads[:3],
            "quote": quote, "qa": qa, "fact": fact, "events": events, "etf": latest.get("etf", {}), "macro": macro, "scores": scores,
            "rel": {k: v.get("relReturnPct") for k, v in sect.items()}, "overrides": overrides, "angle": angle, "clarity": clarity,
            "phase": phase, "pangle": pangle, "rkey": rkey, "wkey": wkey, "diverge": diverge, "change_my_mind": cmm,
            "ai_notes": ED.get("ai_notes", ""), "next_issue": ED.get("next_issue", ""), "mechanical": mechanical}


def render(ctx, path, draft):
    day, headline, dek, reads = ctx["day"], ctx["headline"], ctx["dek"], ctx["reads"]
    quote, qa, fact, events, etf, macro = ctx["quote"], ctx["qa"], ctx["fact"], ctx["events"], ctx["etf"], ctx["macro"]
    scores, angle, clarity, phase, pangle = ctx["scores"], ctx["angle"], ctx["clarity"], ctx["phase"], ctx["pangle"]
    rkey, wkey, diverge, rel = ctx["rkey"], ctx["wkey"], ctx["diverge"], ctx["rel"]
    names2 = {s[0]: s[2] for s in SECT}
    c = canvas.Canvas(path, pagesize=letter); c.setTitle(f"{BRAND}: {day}"); c.setAuthor(BRAND)
    def foot(n):
        c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(36, 44, W - 36, 44); c.setFillColor(MUTED); c.setFont("Helvetica", 8)
        c.drawString(36, 32, f"{BRAND}  |  {day}  |  Education and discussion only, not investment advice"); c.drawRightString(W - 36, 32, f"{n} / 4")
    def top(sub):
        c.setFillColor(NAVY); c.rect(0, H - 46, W, 46, fill=1, stroke=0); c.setFillColor(white); c.setFont("Times-Bold", 17); c.drawString(36, H - 30, BRAND)
        c.setFillColor(HexColor("#B9C3E3")); c.setFont("Helvetica", 9.4); c.drawRightString(W - 36, H - 29, sub + ("   |   DRAFT: not approved" if draft else ""))
    def stamp():
        if not draft: return
        c.saveState(); c.translate(W / 2, H / 2); c.rotate(35); c.setFillColor(HexColor("#C2432F")); c.setFillAlpha(.10)
        c.setFont("Helvetica-Bold", 110); c.drawCentredString(0, -40, "DRAFT"); c.restoreState()
    # page 1
    c.setFillColor(NAVY); c.rect(0, H - 150, W, 150, fill=1, stroke=0); c.setFillColor(BRASS); c.rect(36, H - 150, 60, 3, fill=1, stroke=0)
    c.setFillColor(white); c.setFont("Times-Bold", 46); c.drawString(36, H - 88, BRAND); c.setFillColor(HexColor("#B9C3E3")); c.setFont("Helvetica", 12); c.drawString(36, H - 114, CFG.get("tagline", ""))
    c.setFont("Helvetica", 10); c.drawRightString(W - 36, H - 60, datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %-d, %Y"))
    c.setFillColor(BRASS); c.setFont("Helvetica-Bold", 10); c.drawRightString(W - 36, H - 76, "Cycle update" + ("   DRAFT" if draft else ""))
    c.setFillColor(INK); c.setFont("Times-Bold", 24 if len(headline) < 50 else 20); c.drawString(36, H - 190, headline[:80])
    para(c, esc(dek), 36, H - 202, 540, st(11.2, 16, MUTED))
    px, py, pw, ph = 36, 214, 306, 316
    c.setFillColor(PLATE); c.roundRect(px, py, pw, ph, 16, fill=1, stroke=0); wheel(c, px + pw / 2, py + ph / 2 + 2, scores, angle)
    c.setFillColor(HexColor("#8d9ac0")); c.setFont("Helvetica", 7.2)
    c.drawString(px + 14, py + 20, "Green: beat the S&P 500 over 5 days. Red: lagged it. Dark: in line.")
    ov = ctx.get("overrides") or {}
    c.drawString(px + 14, py + 10, ("Author overrides: " + ", ".join(f"{names2.get(k, k)} {WORD.get(v, v)}" for k, v in ov.items()))[:95] if ov else "Needle: where sector momentum leans on the cycle wheel.")
    sx = 364
    def stat(y, big, lab, note, col=INK):
        c.setFillColor(MUTED); c.setFont("Helvetica", 9); c.drawString(sx, y, lab); c.setFillColor(col); c.setFont("Times-Bold", 30); c.drawString(sx, y - 30, big); para(c, esc(note), sx, y - 38, 214, st(8.6, 11.6, MUTED))
    stat(py + ph - 6, "n/a" if angle is None else f"{angle:.0f}°", "Where the needle points", "No signal yet." if angle is None else (f"{phase} zone." + (f" Previously {pangle:.0f}°." if pangle is not None else "")))
    c.setStrokeColor(LINE); c.setLineWidth(.5); c.line(sx, py + ph - 112, W - 36, py + ph - 112)
    stat(py + ph - 124, f"{clarity*100:.0f}%", "Signal clarity", "0 means sector momentum cancels out across the wheel. 100 means it all points one way.")
    c.line(sx, py + ph - 230, W - 36, py + ph - 230)
    stat(py + ph - 242, REG[rkey][0] if rkey else "Unclear", "Macro backdrop", ("Growth and inflation signals " + ("disagree with sector momentum." if diverge else "match sector momentum.")) if rkey else "Not enough growth and inflation signals came through.", UPD)
    y = py - 20; c.setFillColor(INK); c.setFont("Times-Bold", 17); c.drawString(36, y, "The read in three parts"); y -= 10
    for i, (t_, b) in enumerate(zip(("What changed", "What the data says", "Does it fit?"), reads[:3])):
        x = 36 + i * 185; c.setFillColor(BRASS_D); c.setFont("Helvetica-Bold", 10); c.drawString(x, y - 12, t_); para(c, esc(b), x, y - 17, 170, st(9.0, 12.5))
    if quote.get("text"):
        c.setFillColor(PAPER); c.roundRect(36, 48, 540, 38, 8, fill=1, stroke=0); c.setFillColor(BRASS_D); c.setFont("Helvetica-Bold", 9.4); c.drawString(50, 70, "Quote of"); c.drawString(50, 59, "the day")
        para(c, f"“{esc(quote.get('text',''))}” <font color='#5B6784'>{esc(quote.get('by',''))}</font>", 112, 82, 452, st(10.6, 13.5, INK, "Times-Italic")); para(c, esc(quote.get("why", "")), 112, 65, 452, st(8.6, 11, MUTED))
    stamp(); foot(1); c.showPage()
    # page 2
    top(day); c.setFillColor(INK); c.setFont("Times-Bold", 17); c.drawString(36, H - 76, "Where we are in the cycle")
    para(c, "Four environments built from growth rising or falling and inflation rising or falling, a framework popularized by Ray Dalio's All Weather approach. These are tendencies, not instructions.", 36, H - 84, 540, st(8.8, 11.6, MUTED))
    gx, cw_, chh, gp, gt = 78, 240, 70, 8, H - 130
    c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 8.8); c.drawCentredString(gx + cw_ / 2, gt + 8, "Inflation falling"); c.drawCentredString(gx + cw_ + gp + cw_ / 2, gt + 8, "Inflation rising")
    for r, lab in ((0, "Growth rising"), (1, "Growth falling")):
        c.saveState(); c.translate(60, gt - r * (chh + gp) - chh / 2); c.rotate(90); c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 8.8); c.drawCentredString(0, 0, lab); c.restoreState()
    for r, k_, key in ((0, 0, "10"), (0, 1, "11"), (1, 0, "00"), (1, 1, "01")):
        x = gx + k_ * (cw_ + gp); y = gt - r * (chh + gp) - chh; hit = key in (rkey, wkey)
        c.setFillColor(HexColor("#FBF3DF") if hit else PAPER); c.setStrokeColor(BRASS if hit else LINE); c.setLineWidth(2 if hit else .6); c.roundRect(x, y, cw_, chh, 9, fill=1, stroke=1)
        c.setFillColor(INK); c.setFont("Times-Bold", 13); c.drawString(x + 12, y + chh - 21, REG[key][0]); para(c, REG[key][3], x + 12, y + chh - 27, cw_ - 24, st(8.6, 11.4, MUTED))
        tags = (["MACRO SIGNALS POINT HERE"] if key == rkey else []) + (["SECTOR MOMENTUM LEANS HERE"] if key == wkey else [])
        c.setFillColor(BRASS_D); c.setFont("Helvetica-Bold", 7.6)
        for j, tg in enumerate(tags): c.drawRightString(x + cw_ - 10, y + 8 + j * 10, tg)
    ye = gt - 2 * chh - gp - 14
    rows = [[Paragraph("Signal", HDR), Paragraph("Level", HDR), Paragraph("Direction", HDR), Paragraph("Source", HDR)]]
    for k, m in macro.items():
        lv = m.get("level")
        rows.append([Paragraph(f"<b>{esc(MNAME.get(k, k))}</b>", CELL), Paragraph(esc(lv) if isinstance(lv, str) else fmt(lv if isinstance(lv, (int, float)) else None), CELL), Paragraph(dword(m.get("dir")), CELL), Paragraph(esc(m.get("source", "")), CELL)])
    c.setFillColor(INK); c.setFont("Times-Bold", 15); c.drawString(36, ye - 4, "The numbers behind the read"); yb = table(c, rows, [200, 80, 80, 180], 36, ye - 12, 2.4)
    para(c, "Macro levels from FRED and CoinGecko. Gold and silver show ETF direction, not spot prices. ISM and the dollar index are author-entered when shown. Directions compare the latest value with five observations earlier.", 36, yb - 6, 540, st(8.4, 11, MUTED))
    stamp(); foot(2); c.showPage()
    # page 3
    top(day); c.setFillColor(INK); c.setFont("Times-Bold", 17); c.drawString(36, H - 76, "The technical picture")
    para(c, "Fundamentals tell you why the market might move. These levels show where traders are likely to react. They are zones to watch, not instructions to trade.", 36, H - 84, 540, st(8.8, 11.6, MUTED))
    rows = [[Paragraph(h, HDR) for h in ("ETF", "Close", "50-day", "200-day", "Support", "Resistance", "What it says")]]
    names = {"SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF", "DIA": "Dow ETF", "IWM": "Russell 2000 ETF"}
    for sym, e in etf.items():
        says = []
        if e.get("m200"): says.append("above its 200-day average" if e["c"] >= e["m200"] else "below its 200-day average")
        if e.get("m50"): says.append("above its 50-day" if e["c"] >= e["m50"] else "below its 50-day")
        if e.get("chg5Pct") is not None: says.append(f"{e['chg5Pct']:+.1f}% over 5 days")
        rows.append([Paragraph(f"<b>{sym}</b><br/>{esc(names.get(sym, ''))}", CELL), Paragraph(fmt(e["c"]), CELL), Paragraph(fmt(e.get("m50")), CELL), Paragraph(fmt(e.get("m200")), CELL),
                     Paragraph(f"{fmt(e.get('s1'))}<br/>{fmt(e.get('s2'))}", CELL), Paragraph(f"{fmt(e.get('r1'))}<br/>{fmt(e.get('r2'))}", CELL), Paragraph(("; ".join(says) + ".").capitalize() if says else "", CELL)])
    yt = table(c, rows, [92, 52, 52, 52, 56, 62, 174], 36, H - 118, 4)
    yf = para(c, "ETF prices differ from index levels. Suggested support and resistance come from recent swing highs and lows and the 50 and 200-day averages. Review before relying on them.", 36, yt - 6, 540, st(8.4, 11, MUTED))
    c.setFillColor(INK); c.setFont("Times-Bold", 15); c.drawString(36, yf - 26, "Sector momentum"); c.setFillColor(MUTED); c.setFont("Helvetica", 8.4); c.drawString(36, yf - 40, "Each sector ETF's 5-day return minus the S&P 500 ETF's. A short-term reading, not a forecast.")
    ordered = sorted(scores.items(), key=lambda kv: -(rel.get(kv[0]) if rel.get(kv[0]) is not None else 0))
    y = yf - 62; axis = 236
    c.setStrokeColor(LINE); c.setLineWidth(.6); c.line(axis, y + 8, axis, y - len(ordered) * 17 + 6)
    for sid, v in ordered:
        rr = rel.get(sid); tag = " (author)" if sid in (ctx.get("overrides") or {}) else ""
        c.setFillColor(INK); c.setFont("Helvetica", 9); c.drawString(36, y - 3, names2.get(sid, sid))
        L = 30 * abs(v); c.setFillColor(UP if v > 0 else DOWN if v < 0 else LINE)
        if v > 0: c.roundRect(axis + 2, y - 6, L, 10, 2, fill=1, stroke=0)
        elif v < 0: c.roundRect(axis - 2 - L, y - 6, L, 10, 2, fill=1, stroke=0)
        c.setFillColor(MUTED); c.setFont("Helvetica", 8.2); c.drawString(axis + (L + 8 if v > 0 else 8), y - 3, WORD[v] + ("" if rr is None else f" ({rr:+.1f} pts)") + tag); y -= 17
    if ctx.get("ai_notes"):
        box(c, 48, y - 14, 516, "Author notes", "AI spending", [esc(ctx["ai_notes"])])
    stamp(); foot(3); c.showPage()
    # page 4
    top(day); c.setFillColor(INK); c.setFont("Times-Bold", 17); c.drawString(36, H - 76, "On the calendar, and a question worth asking")
    para(c, "Dates come from public calendars. Confirm them with the Fed, the Bureau of Labor Statistics and each company before relying on them.", 36, H - 84, 540, st(8.8, 11.6, MUTED))
    rows = [[Paragraph(h, HDR) for h in ("Date", "Event", "What to watch")]]
    for e in events: rows.append([Paragraph("<b>%s</b>" % datetime.strptime(e["date"], "%Y-%m-%d").strftime("%b %-d"), CELL), Paragraph(f"<b>{esc(e.get('kind',''))}</b>: {esc(e.get('title',''))}", CELL), Paragraph(esc(e.get("note", "")), CELL)])
    if len(rows) == 1: rows.append([Paragraph("", CELL), Paragraph("No upcoming events listed this week.", CELL), Paragraph("", CELL)])
    yt = table(c, rows, [64, 236, 240], 36, H - 112, 3.2)
    y = yt - 22
    if qa.get("q"): y = box(c, 48, y, 516, "Question of the day", esc(qa.get("q", "")), [esc(qa.get("a", ""))], 9.2) - 24
    cmm = ctx.get("change_my_mind") or []
    if cmm:
        c.setFillColor(INK); c.setFont("Times-Bold", 15); c.drawString(36, y, "What would change my mind"); y -= 10
        for k in range(0, len(cmm), 2):
            ys = []
            for j, it in enumerate(cmm[k:k + 2]):
                x = 36 if j == 0 else 318; ys.append(para(c, esc(it), x + 12, y, 244, st(9.2, 12.6)) - 4); c.setFillColor(BRASS); c.circle(x + 4, y - 8.5, 2.2, fill=1, stroke=0)
            y = min(ys)
        y -= 10
    if fact:
        c.setFillColor(PAPER); c.roundRect(36, y - 40, 540, 36, 8, fill=1, stroke=0); c.setFillColor(BRASS_D); c.setFont("Helvetica-Bold", 9.4); c.drawString(50, y - 20, "Fun fact"); para(c, esc(fact), 112, y - 9, 452, st(9, 12, INK))
    yc = y - 62; c.setFillColor(NAVY); c.roundRect(36, yc - 56, 540, 56, 12, fill=1, stroke=0); c.setFillColor(BRASS); c.setFont("Helvetica-Bold", 9.4); c.drawString(54, yc - 16, "Next issue")
    c.setFillColor(white); c.setFont("Times-Bold", 14); c.drawString(54, yc - 34, (ctx.get("next_issue") or "Did the data confirm the wheel? I will re-read it next week.")[:90])
    c.setFillColor(HexColor("#B9C3E3")); c.setFont("Helvetica", 9.2); c.drawString(54, yc - 49, "Tell me which sector you want unpacked and I will cover it.")
    yd = para(c, f"<b>Disclaimer.</b> {BRAND} is for education and discussion only and is not investment, tax or legal advice. Sector readings are mechanical 5-day momentum, reviewed by the author, and the cycle wheel is a framework, not a forecast. Crypto assets are highly volatile. Verify levels and dates before relying on them.", 36, yc - 66, 540, st(8.2, 10.8, MUTED))
    disc = (CFG.get("firm_disclosure") or "").strip()
    if disc: yd = para(c, esc(disc), 36, yd - 4, 540, st(8.2, 10.8, MUTED))
    para(c, f"<b>Sources.</b> FRED (Federal Reserve Bank of St. Louis), CoinGecko, Twelve Data and public calendars. Data as of {ctx['asOf'][:16].replace('T', ' ')} UTC.", 36, yd - 4, 540, st(8.2, 10.8, MUTED))
    stamp(); foot(4); c.showPage(); c.save()


def render_final(out_path):
    """Called by publish.py after approval. Rebuilds the letter without the DRAFT marks from the frozen context."""
    ctx = json.load(open(os.path.join(HERE, "draft", "context.json")))
    render(ctx, out_path, False)
    return ctx


def build():
    os.makedirs(os.path.join(HERE, "draft"), exist_ok=True)
    for old in ("letter-final.pdf",):   # never leave an unmarked copy lying around before approval
        p = os.path.join(HERE, "draft", old)
        if os.path.exists(p): os.remove(p)
    latest = load("latest.json", {})
    blocking, reasons = check(latest) if latest.get("asOf") else (["latest.json has no data yet."], ["latest.json has no data yet."])
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    base = f"https://github.com/{repo}/blob/main" if repo else ""
    out = lambda n, t: open(os.path.join(HERE, "draft", n), "w").write(t)
    if blocking:
        out("issue_title.txt", "Draft blocked: the data needs attention")
        out("issue_label.txt", "needs-attention")
        out("issue_body.md", "The weekly letter was **not** built because of a data problem:\n\n" + "\n".join(f"- {r}" for r in reasons) +
            "\n\nCheck the **Actions** tab for the failed run, fix or rerun the daily job, then run **Weekly letter draft** again. Nothing was sent or published.")
        out("status.json", json.dumps({"ok": False, "reasons": reasons})); print("blocked:", reasons); return False

    ctx = compute(latest); day = ctx["day"]
    json.dump(ctx, open(os.path.join(HERE, "draft", "context.json"), "w"), indent=2)
    render(ctx, os.path.join(HERE, "draft", "letter-DRAFT.pdf"), True)
    json.dump({"date": day, "headline": ctx["headline"], "dek": ctx["dek"], "brand": BRAND}, open(os.path.join(HERE, "draft", "meta.json"), "w"))
    angle, phase, clarity = ctx["angle"], ctx["phase"], ctx["clarity"]
    chk = [f"- Data as of {ctx['asOf'][:16].replace('T', ' ')} UTC", f"- Needle: {'n/a' if angle is None else f'{angle:.0f} degrees ({phase})'}, clarity {clarity*100:.0f}%", f"- Headline: {ctx['headline']}"]
    if ctx["mechanical"]: chk.append("- **Machine-written, not yours yet:** " + ", ".join(ctx["mechanical"]) + ". Write these in `editorial.json` if the story needs your judgment.")
    if not ctx["change_my_mind"]: chk.append("- \"What would change my mind\" is empty, so that section is left out. Add lines under `change_my_mind` in `editorial.json` to include it.")
    if not ctx["events"]: chk.append("- No upcoming events in `editorial.json`.")
    chk += [f"- Warning: {w}" for w in ctx["warnings"]]
    out("issue_title.txt", f"Draft ready: {BRAND} letter for {day}"); out("issue_label.txt", "letter-draft")
    out("issue_body.md", f"Your weekly letter draft is ready.\n\n" + "\n".join(chk) +
        (f"\n\n**Read the draft:** {base}/draft/letter-DRAFT.pdf" if base else "\n\nRead the draft in the `draft` folder.") +
        "\n\n**To change the text:** edit `editorial.json`, then run **Weekly letter draft** again. A new issue opens and this one closes automatically.\n\n"
        "**Before approving:** if you are registered with a firm, get its written approval first. Closing this issue is your release step, not your firm's review.\n\n"
        "**To approve:** close this issue as *completed*. The clean letter is built from exactly this draft and published to your archive and feed.\n\n**To decline:** close it as *not planned*. Nothing is published.")
    out("status.json", json.dumps({"ok": True, "reasons": reasons})); print("built draft for", day); return True

if __name__ == "__main__":
    build()
