"""Owl Hours backtest (see .github/workflows/backtest.yml). Runs weekly; writes backtest.json for the owner Lab.

What it tests: does the clock's sector read have an edge? Everything is rebuilt month by month using only
prices that existed on that day (signals on the last trading day of a month, trades at the next day's close,
0.05% cost per unit of turnover). Sector ETFs join the test on the date they existed; nothing is back-filled.

  Clock scoring   the same math as the app: sector 1-day and 20-day returns vs SPY, blended, scored -2..+2,
                  then a weighted needle angle and clarity.  Three preset blends are tested.
  Owl models      A: hold the 3 strongest sectors (z > 0), rest SPY
                  B: hold the sectors that live in the needle's phase
                  C: SPY in Dawn/Midday, defensives (staples, health, utilities) in Dusk/Night
                  each with and without a clarity filter (low clarity -> SPY), plus a walk-forward pick of the blend
  Benchmarks      SPY, equal-weight sectors, momentum (top 3 by 3-month return), random 3 sectors (200 draws)
  Phase study     next-month SPY return and next-month home-sector edge for each needle phase
  Risk tiers      7 portfolios from highest risk to retirement income (Model A sleeve + bonds, cash, gold, dividends)
  Hard assets     gold/silver/miners steered by the clock, vs gold and 50/50 gold/silver
  Experiments     risk targeting (12% vol), factor model (momentum + low vol + trend), statistical regimes (k-means)

Data: Twelve Data daily closes (TWELVEDATA_API_KEY), 8 calls a minute on the free plan.
"""
import json, math, os, random, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json")))
TD = os.environ.get("TWELVEDATA_API_KEY", "").strip()
OUT = os.path.join(HERE, "backtest.json")
COST = 0.0005
ANG = {"FIN": 8, "REIT": 22, "DISC": 36, "TECH": 52, "CYB": 66, "SEMI": 94, "COMM": 112, "IND": 132, "MAT": 165,
       "ENGY": 200, "GOLD": 222, "STPL": 240, "HLTH": 280, "UTIL": 320}
NAMES = {"FIN": "Financials", "REIT": "Real estate", "DISC": "Discretionary", "TECH": "Tech", "CYB": "Cyber", "SEMI": "Semis",
         "COMM": "Comm", "IND": "Industrials", "MAT": "Materials", "ENGY": "Energy", "GOLD": "Gold miners", "STPL": "Staples",
         "HLTH": "Health", "UTIL": "Utilities"}
PHASES = [("Recovery", "Dawn", 0, 90), ("Expansion", "Midday", 90, 180), ("Late cycle", "Dusk", 180, 270), ("Contraction", "Night", 270, 360)]
BLENDS = {"base": (0.4, 0.6), "trend": (0.2, 0.8), "pure20": (0.0, 1.0)}
EXTRA = ["SPY", "AGG", "SHY", "BIL", "GLD", "SLV", "GDX", "SCHD", "VIG"]
DEFENSIVE = ["STPL", "HLTH", "UTIL"]


def log(m): print(m, flush=True)


def phase_of(a):
    for p in PHASES:
        if p[2] <= a % 360 < p[3]: return p[0]
    return PHASES[0][0]


# ---------------- data ----------------
def fetch(sym, opener=urllib.request.urlopen, sleep=time.sleep, bars=2700):
    base = f"https://api.twelvedata.com/time_series?symbol={urllib.parse.quote(sym)}&interval=1day&outputsize={bars}&apikey={TD}"
    for url, label in ((base + "&adjust=all", "adjusted"), (base, "split-adjusted")):
        req = urllib.request.Request(url, headers={"User-Agent": "owl-hours/1.0 (personal research)"})
        with opener(req, timeout=60) as r:
            d = json.loads(r.read())
        sleep(8)
        if d.get("status") != "error" and d.get("values"):
            return {v["datetime"][:10]: float(v["close"]) for v in d["values"]}, label
        if "credits" in str(d.get("message", "")).lower():
            sleep(62)
    raise ValueError(str(d.get("message", "no data"))[:120])


class Px:
    """Prices aligned to SPY's trading calendar, forward-filled up to 5 days, None before a fund existed."""
    def __init__(self, raw):
        self.dates = sorted(raw["SPY"])
        self.s = {}
        for sym, m in raw.items():
            out, last, gap = [], None, 0
            first = min(m) if m else None
            for d in self.dates:
                if d in m: last, gap = m[d], 0
                elif last is not None: gap += 1
                out.append(None if (first is None or d < first or gap > 5) else last)
            self.s[sym] = out

    def c(self, sym, i):
        a = self.s.get(sym)
        return None if a is None or i < 0 else a[i]

    def ret(self, sym, i, n):
        a, b = self.c(sym, i), self.c(sym, i - n)
        return None if a is None or b is None or b <= 0 else a / b - 1


# ---------------- clock replica ----------------
def score_z(z):
    return 2 if z >= 1.2 else 1 if z >= 0.4 else -2 if z <= -1.2 else -1 if z <= -0.4 else 0


def clock(px, i, blend):
    wt, wr = BLENDS[blend]
    s1, s20 = px.ret("SPY", i, 1), px.ret("SPY", i, 20)
    z, m = {}, {}
    for sid, etf in CFG["sectors"].items():
        if sid not in ANG: continue
        r1, r20 = px.ret(etf, i, 1), px.ret(etf, i, 20)
        if r1 is None or r20 is None or s1 is None or s20 is None: continue
        today, trend = 100 * (r1 - s1), 100 * (r20 - s20)
        z[sid] = wt * today / 1 + wr * trend / 3
        m[sid] = score_z(z[sid])
    x = y = tot = 0.0
    for sid, v in m.items():
        if v:
            x += v * math.sin(math.radians(ANG[sid])); y += v * math.cos(math.radians(ANG[sid])); tot += abs(v)
    if tot == 0: return z, m, None, 0.0
    return z, m, math.degrees(math.atan2(x, y)) % 360, math.hypot(x, y) / tot


# ---------------- portfolio engine ----------------
def month_ends(px, start_i):
    out = []
    for i in range(start_i, len(px.dates) - 1):
        if px.dates[i][:7] != px.dates[i + 1][:7]: out.append(i)
    return out


def period_ret(px, sym, a, b):
    x, y = px.c(sym, a), px.c(sym, b)
    return None if x is None or y is None or x <= 0 else y / x - 1


def run(px, rebal, weights_fn, guard=None):
    """weights_fn(k, i, state) -> {symbol: weight}. Returns monthly series [(date, ret)] and last weights."""
    rets, prev, eq, peak, state = [], {}, 1.0, 1.0, {"eq": 1.0, "dd": 0.0}
    for k, i in enumerate(rebal[:-1]):
        a, b = i + 1, rebal[k + 1] + 1
        if b >= len(px.dates): b = len(px.dates) - 1
        state["dd"] = 1 - eq / peak
        w = weights_fn(k, i, state) or {"SPY": 1.0}
        w = {s: x for s, x in w.items() if x > 1e-9 and px.c(s, a) is not None}
        tw = sum(w.values()) or 1.0
        w = {s: x / tw for s, x in w.items()}
        turn = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in set(w) | set(prev))
        r = 0.0
        for s, x in w.items():
            pr = period_ret(px, s, a, b)
            r += x * (pr if pr is not None else 0.0)
        r -= turn * COST
        drift = {}
        for s, x in w.items():
            pr = period_ret(px, s, a, b) or 0.0
            drift[s] = x * (1 + pr)
        dt = sum(drift.values()) or 1.0
        prev = {s: x / dt for s, x in drift.items()}
        eq *= 1 + r; peak = max(peak, eq)
        rets.append((px.dates[rebal[k + 1]], r))
    return rets, prev


def metrics(rets, bench=None, rf=None):
    if not rets: return {}
    r = [x for _, x in rets]
    n = len(r); eq, peak, mdd, curve = 1.0, 1.0, 0.0, []
    for d, x in rets:
        eq *= 1 + x; peak = max(peak, eq); mdd = max(mdd, 1 - eq / peak); curve.append([d, round(eq, 4)])
    yrs = n / 12
    cagr = eq ** (1 / yrs) - 1 if yrs > 0 and eq > 0 else None
    mean = sum(r) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in r) / (n - 1)) if n > 1 else 0
    rfm = (sum(x for _, x in rf) / len(rf)) if rf else 0.0
    out = {"cagr": round(100 * cagr, 2) if cagr is not None else None, "total": round(100 * (eq - 1), 1),
           "vol": round(100 * sd * math.sqrt(12), 2), "sharpe": round((mean - rfm) / sd * math.sqrt(12), 2) if sd else None,
           "maxDD": round(100 * mdd, 1), "months": n, "curve": curve}
    if bench:
        bm = dict(bench)
        pairs = [(x, bm[d]) for d, x in rets if d in bm]
        if pairs:
            out["hit"] = round(100 * sum(1 for a, b in pairs if a > b) / len(pairs), 1)
            beq = 1.0
            for _, b in pairs: beq *= 1 + b
            beq_c = beq ** (12 / len(pairs)) - 1
            out["excess"] = round(out["cagr"] - 100 * beq_c, 2) if out["cagr"] is not None else None
    return out


# ---------------- models ----------------
def avail_sectors(px, i, need=63):
    return [sid for sid, etf in CFG["sectors"].items() if sid in ANG and px.c(etf, i - need) is not None]


def model_top(px, i, blend, n=3, clarity_min=None):
    z, m, ang, cl = clock(px, i, blend)
    if clarity_min is not None and (ang is None or cl < clarity_min): return {"SPY": 1.0}
    picks = [sid for sid in sorted(z, key=lambda s: -z[s]) if z[sid] > 0][:n]
    w = {CFG["sectors"][sid]: 1.0 / n for sid in picks}
    if len(picks) < n: w["SPY"] = (n - len(picks)) / n
    return w


def model_phase(px, i, blend, clarity_min=None):
    z, m, ang, cl = clock(px, i, blend)
    if ang is None or (clarity_min is not None and cl < clarity_min): return {"SPY": 1.0}
    ph = phase_of(ang)
    home = [sid for sid in z if phase_of(ANG[sid]) == ph]
    return {CFG["sectors"][s]: 1.0 / len(home) for s in home} if home else {"SPY": 1.0}


def model_defensive(px, i, blend, clarity_min=None):
    z, m, ang, cl = clock(px, i, blend)
    if ang is None or (clarity_min is not None and cl < clarity_min): return {"SPY": 1.0}
    if phase_of(ang) in ("Late cycle", "Contraction"):
        d = [CFG["sectors"][s] for s in DEFENSIVE if s in z]
        return {s: 1.0 / len(d) for s in d} if d else {"SPY": 1.0}
    return {"SPY": 1.0}


def model_equal(px, i):
    s = avail_sectors(px, i, 20)
    return {CFG["sectors"][x]: 1.0 / len(s) for x in s} if s else {"SPY": 1.0}


def model_momentum(px, i, n=3):
    s = avail_sectors(px, i, 63)
    ranked = sorted(s, key=lambda x: -(px.ret(CFG["sectors"][x], i, 63) or -9))[:n]
    return {CFG["sectors"][x]: 1.0 / n for x in ranked} if ranked else {"SPY": 1.0}


def realized_vol(px, syms_w, i, n=63):
    rs = []
    for j in range(i - n + 1, i + 1):
        r = 0.0
        for s, w in syms_w.items():
            x = px.ret(s, j, 1)
            r += w * (x or 0.0)
        rs.append(r)
    m = sum(rs) / len(rs)
    return math.sqrt(sum((x - m) ** 2 for x in rs) / (len(rs) - 1)) * math.sqrt(252)


def model_factor(px, i, n=3):
    s = avail_sectors(px, i, 200)
    if len(s) < 4: return {"SPY": 1.0}
    feats = {}
    for x in s:
        e = CFG["sectors"][x]
        mom = px.ret(e, i, 63) or 0
        vol = realized_vol(px, {e: 1.0}, i)
        c, ma = px.c(e, i), sum(px.c(e, j) for j in range(i - 199, i + 1)) / 200
        feats[x] = (mom, -vol, 1.0 if c > ma else 0.0)
    def zs(k):
        v = [feats[x][k] for x in s]; m = sum(v) / len(v); sd = math.sqrt(sum((a - m) ** 2 for a in v) / len(v)) or 1
        return {x: (feats[x][k] - m) / sd for x in s}
    z0, z1, z2 = zs(0), zs(1), zs(2)
    comp = {x: z0[x] + 0.5 * z1[x] + 0.5 * z2[x] for x in s}
    picks = sorted(s, key=lambda x: -comp[x])[:n]
    return {CFG["sectors"][x]: 1.0 / n for x in picks}


def kmeans(points, k=4, iters=40, seed=7):
    rnd = random.Random(seed)
    cents = rnd.sample(points, k)
    lab = [0] * len(points)
    for _ in range(iters):
        for j, p in enumerate(points):
            lab[j] = min(range(k), key=lambda c: sum((p[t] - cents[c][t]) ** 2 for t in range(len(p))))
        for c in range(k):
            mem = [points[j] for j in range(len(points)) if lab[j] == c]
            if mem: cents[c] = [sum(m[t] for m in mem) / len(mem) for t in range(len(points[0]))]
    return cents


# ---------------- main ----------------
def main(opener=urllib.request.urlopen, sleep=time.sleep, raw=None):
    t0 = time.time()
    notes, warnings, data_info = [], [], {}
    if raw is None:
        if not TD: log("No TWELVEDATA_API_KEY"); return 0
        raw = {}
        syms = list(dict.fromkeys(list(CFG["sectors"].values()) + EXTRA))
        for s in syms:
            try:
                raw[s], how = fetch(s, opener, sleep)
                data_info[s] = {"from": min(raw[s]), "bars": len(raw[s]), "adjust": how}
                log(f"  {s}: {len(raw[s])} bars from {min(raw[s])} ({how})")
            except Exception as e:
                warnings.append(f"{s}: {e}"); log(f"  {s} failed: {e}")
    else:
        data_info = {s: {"from": min(m), "bars": len(m), "adjust": "test"} for s, m in raw.items() if m}
    if "SPY" not in raw or len(raw["SPY"]) < 600:
        log("Not enough SPY history; stopping."); return 0
    px = Px(raw)
    start_i = 260
    rebal = month_ends(px, start_i)
    log(f"Testing {px.dates[rebal[0]]} to {px.dates[rebal[-1]]}: {len(rebal) - 1} months")
    rf, _ = run(px, rebal, lambda k, i, st: {"BIL": 1.0}) if px.c("BIL", rebal[0] + 1) else ([], None)
    spy, _ = run(px, rebal, lambda k, i, st: {"SPY": 1.0})
    results = []

    def add(mid, name, group, fn, desc, bench=spy):
        rets, last = run(px, rebal, fn)
        m = metrics(rets, bench, rf)
        results.append({"id": mid, "name": name, "group": group, "desc": desc, "metrics": m,
                        "now": {s: round(w, 3) for s, w in sorted(last.items(), key=lambda x: -x[1]) if w > 0.005}})
        return rets

    add("spy", "SPY buy and hold", "Benchmark", lambda k, i, st: {"SPY": 1.0}, "The S&P 500, held the whole time.")
    add("eqw", "Equal-weight sectors", "Benchmark", lambda k, i, st: model_equal(px, i), "Every sector that existed, equal amounts, rebalanced monthly.")
    add("mom", "Momentum: top 3 by 3 months", "Benchmark", lambda k, i, st: model_momentum(px, i), "The 3 sectors with the best 3-month return.")
    # random pickers
    rnd_cagrs = []
    for seed in range(200):
        R = random.Random(seed)
        def rf_fn(k, i, st, R=R):
            s = avail_sectors(px, i, 20)
            p = R.sample(s, min(3, len(s)))
            return {CFG["sectors"][x]: 1.0 / len(p) for x in p}
        rr, _ = run(px, rebal, rf_fn)
        rnd_cagrs.append(metrics(rr)["cagr"])
    rnd_cagrs.sort()
    notes.append(f"Random 3-sector pickers (200 draws): median CAGR {rnd_cagrs[100]}%, best {rnd_cagrs[-1]}%, worst {rnd_cagrs[0]}%.")
    # Owl models
    labels = {"A": "Top 3 strongest", "B": "Needle's phase", "C": "Defensive switch"}
    fns = {"A": lambda i, b, cm: model_top(px, i, b, 3, cm), "B": lambda i, b, cm: model_phase(px, i, b, cm), "C": lambda i, b, cm: model_defensive(px, i, b, cm)}
    series = {}
    for key in "ABC":
        for b in BLENDS:
            for cm in (None, 0.35):
                mid = f"{key}-{b}{'-clar' if cm else ''}"
                series[mid] = add(mid, f"Owl {key}: {labels[key]} ({b}{', clarity filter' if cm else ''})", "Owl model",
                                  lambda k, i, st, key=key, b=b, cm=cm: fns[key](i, b, cm),
                                  f"Blend {b} {BLENDS[b]}; {'switch to SPY when clarity < 35%' if cm else 'no filter'}.")
        # walk-forward: each January pick the blend with the best trailing-36-month Sharpe (no filter), use it all year
        def wf(k, i, st, key=key):
            d = px.dates[i]
            past = [b for b in BLENDS]
            best, bs = "base", -9
            for b in past:
                r = [x for dd, x in series[f"{key}-{b}"] if dd <= d][-36:]
                if len(r) < 24: continue
                mu = sum(r) / len(r); sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1)) or 1
                if mu / sd > bs: bs, best = mu / sd, b
            return fns[key](i, best, None)
        add(f"{key}-wf", f"Owl {key}: {labels[key]} (walk-forward blend)", "Owl model", wf, "Each month uses the blend that had the best Sharpe over the prior 36 months.")
    # phase study: does the needle's phase tell us anything about next month?
    study = {p[0]: {"n": 0, "spy": [], "edge": []} for p in PHASES}
    for k, i in enumerate(rebal[:-1]):
        z, m, ang, cl = clock(px, i, "base")
        if ang is None: continue
        ph = phase_of(ang); a, b = i + 1, rebal[k + 1] + 1
        if b >= len(px.dates): continue
        sp = period_ret(px, "SPY", a, b)
        home = [CFG["sectors"][s] for s in z if phase_of(ANG[s]) == ph]
        hr = [period_ret(px, e, a, b) for e in home]
        hr = [x for x in hr if x is not None]
        study[ph]["n"] += 1; study[ph]["spy"].append(sp)
        if hr: study[ph]["edge"].append(sum(hr) / len(hr) - sp)
    phase_study = []
    for p in PHASES:
        s = study[p[0]]
        if not s["n"]: phase_study.append({"phase": p[0], "hour": p[1], "months": 0}); continue
        phase_study.append({"phase": p[0], "hour": p[1], "months": s["n"], "spyNext": round(100 * sum(s["spy"]) / len(s["spy"]), 2),
                            "spyUp": round(100 * sum(1 for x in s["spy"] if x > 0) / len(s["spy"]), 0),
                            "homeEdge": round(100 * sum(s["edge"]) / len(s["edge"]), 2) if s["edge"] else None,
                            "homeWin": round(100 * sum(1 for x in s["edge"] if x > 0) / len(s["edge"]), 0) if s["edge"] else None})
    # risk tiers: Model A sleeve (base blend) + building blocks, with a drawdown guard on the sleeve
    def sleeve(i, n=3): return model_top(px, i, "base", n)
    def mix(parts):
        w = {}
        for share, ws in parts:
            for s, x in ws.items(): w[s] = w.get(s, 0) + share * x
        return w
    def div(i): return {"SCHD": 0.5, "VIG": 0.5} if px.c("SCHD", i) else {"VIG": 1.0}
    tiers = [("t1", "Highest risk", 1.0, None, lambda i: sleeve(i, 2), {}),
             ("t2", "Aggressive", 1.0, None, lambda i: sleeve(i), {}),
             ("t3", "Moderately aggressive", 0.8, 0.20, lambda i: sleeve(i), {"AGG": 0.2}),
             ("t4", "Moderate", 0.6, 0.15, lambda i: sleeve(i), {"AGG": 0.3, "GLD": 0.1}),
             ("t5", "Conservatively moderate", 0.45, 0.12, lambda i: sleeve(i), {"AGG": 0.35, "SHY": 0.1, "GLD": 0.1}),
             ("t6", "Conservative", 0.3, 0.08, lambda i: sleeve(i), {"AGG": 0.4, "SHY": 0.2, "GLD": 0.1}),
             ("t7", "Retirement income", 0.15, 0.10, lambda i: model_defensive(px, i, "base"), {"AGG": 0.4, "SHY": 0.1, "_DIV": 0.35})]
    for tid, nm, sl, guard, sfn, rest in tiers:
        def build(i, s, sl=sl, rest=rest):
            parts = [(sl, s)]
            for a, x in rest.items(): parts.append((x, div(i) if a == "_DIV" else {a: 1.0}))
            return mix(parts)
        # the guard watches the UNGUARDED version of the tier ("shadow"), so it can switch back on when that recovers
        shadow, _ = run(px, rebal, lambda k, i, st, sfn=sfn, build=build: build(i, sfn(i)))
        sdd, eq, peak = {}, 1.0, 1.0
        for d, r in shadow:
            eq *= 1 + r; peak = max(peak, eq); sdd[d] = 1 - eq / peak
        gstate = {"on": False}
        def tf(k, i, st, guard=guard, sfn=sfn, build=build, gstate=gstate):
            s = sfn(i)
            if guard:
                dd = sdd.get(px.dates[i], 0.0)
                if dd > guard: gstate["on"] = True
                elif dd < guard / 2: gstate["on"] = False
                if gstate["on"]: s = {"SHY": 1.0}
            return build(i, s)
        add(tid, nm, "Risk tier", tf, f"{int(sl * 100)}% clock sleeve" + (f", sleeve to short Treasuries while the tier is down more than {int(guard * 100)}% from its high (back on below {int(guard * 50)}%)" if guard else "") +
            "; " + ", ".join(f"{int(x * 100)}% {'dividend ETFs' if a == '_DIV' else a}" for a, x in rest.items()))
    # hard assets
    MIXES = {"Recovery": (0.40, 0.35, 0.25), "Expansion": (0.35, 0.35, 0.30), "Late cycle": (0.60, 0.25, 0.15), "Contraction": (0.70, 0.20, 0.10)}
    def h1(k, i, st):
        z, m, ang, cl = clock(px, i, "base")
        g, s, mi = MIXES[phase_of(ang)] if ang is not None else (0.6, 0.3, 0.1)
        return {"GLD": g, "SLV": s, "GDX": mi}
    def h2(k, i, st):
        z, m, ang, cl = clock(px, i, "base")
        return {"GLD": 0.6, "SLV": 0.3, ("GDX" if z.get("GOLD", 0) > 0 else "SHY"): 0.1}
    gld, _ = run(px, rebal, lambda k, i, st: {"GLD": 1.0})
    add("gld", "Gold buy and hold", "Hard assets", lambda k, i, st: {"GLD": 1.0}, "GLD held the whole time.", gld)
    add("gs50", "50/50 gold and silver", "Hard assets", lambda k, i, st: {"GLD": 0.5, "SLV": 0.5}, "Half GLD, half SLV, rebalanced monthly.", gld)
    add("h1", "Clock-steered metals mix", "Hard assets", h1, "More gold in Dusk/Night, more silver and miners in Dawn/Midday.", gld)
    add("h2", "Metals core + miners switch", "Hard assets", h2, "60% gold, 30% silver; 10% miners when the gold-miner sector scores positive, else short Treasuries.", gld)
    # experiments
    def rt(k, i, st):
        w = sleeve(i)
        v = realized_vol(px, w, i)
        sc = min(1.0, 0.12 / v) if v > 0 else 1.0
        out = {s: x * sc for s, x in w.items()}; out["SHY"] = out.get("SHY", 0) + 1 - sc
        return out
    add("x-rt", "Experiment: Owl A with 12% volatility target", "Experiment", rt, "Model A scaled down when recent volatility runs above 12% a year; the rest in short Treasuries.")
    add("x-factor", "Experiment: factor model", "Experiment", lambda k, i, st: model_factor(px, i), "Top 3 sectors by momentum + low volatility + above-200-day trend.")
    # statistical regimes: k-means on SPY 3-month return and volatility, fitted only on the past (refit each January)
    reg_rows, cents = [], None
    feats_all = []
    for k, i in enumerate(rebal[:-1]):
        f = (px.ret("SPY", i, 63) or 0, realized_vol(px, {"SPY": 1.0}, i))
        if px.dates[i][5:7] == "01" or cents is None:
            if len(feats_all) >= 24: cents = kmeans(feats_all, 4)
        if cents:
            lab = min(range(4), key=lambda c: (f[0] - cents[c][0]) ** 2 * 25 + (f[1] - cents[c][1]) ** 2)
            z, m, ang, cl = clock(px, i, "base")
            a, b = i + 1, rebal[k + 1] + 1
            if b < len(px.dates) and ang is not None:
                reg_rows.append((lab, cents[lab], phase_of(ang), period_ret(px, "SPY", a, b)))
        feats_all.append(f)
    regimes = []
    for c in range(4):
        rows = [r for r in reg_rows if r[0] == c]
        if not rows: continue
        ce = rows[-1][1]
        ph = {}
        for r in rows: ph[r[2]] = ph.get(r[2], 0) + 1
        regimes.append({"cluster": c, "spy3m": round(100 * ce[0], 1), "vol": round(100 * ce[1], 1), "months": len(rows),
                        "spyNext": round(100 * sum(r[3] for r in rows) / len(rows), 2), "clockPhases": ph})
    regimes.sort(key=lambda r: r["vol"])
    for j, r in enumerate(regimes): r["label"] = ["Calm uptrend", "Normal", "Choppy", "Stress"][min(j, 3)]
    # verdict
    def get(mid): return next(r for r in results if r["id"] == mid)["metrics"]
    owl = [r for r in results if r["group"] == "Owl model"]
    best = max(owl, key=lambda r: r["metrics"].get("sharpe") or -9)
    mom, eq, sp = get("mom"), get("eqw"), get("spy")
    beats = [n for n, b in (("SPY", sp), ("equal-weight", eq), ("momentum", mom)) if (best["metrics"].get("sharpe") or -9) > (b.get("sharpe") or -9)]
    rank = sum(1 for x in rnd_cagrs if (best["metrics"].get("cagr") or -99) > x) / len(rnd_cagrs) * 100
    verdict = {"best": best["id"], "bestName": best["name"], "beatsSharpe": beats, "randomPercentile": round(rank),
               "caution": "Best-of-many results flatter the winner. Judge the walk-forward rows and the phase study, not the single best line."}
    data = {"asOf": datetime.now(timezone.utc).isoformat(timespec="seconds"), "start": px.dates[rebal[0]], "end": px.dates[rebal[-1]],
            "months": len(rebal) - 1, "cost": COST, "verdict": verdict, "phaseStudy": phase_study, "regimes": regimes,
            "randomCagr": {"median": rnd_cagrs[100], "p10": rnd_cagrs[20], "p90": rnd_cagrs[180]},
            "results": results, "data": data_info, "notes": notes, "warnings": warnings, "seconds": round(time.time() - t0)}
    json.dump(data, open(OUT, "w"), separators=(",", ":"))
    log(f"Saved backtest.json: {len(results)} portfolios, best {best['name']} Sharpe {best['metrics'].get('sharpe')}, {round(time.time() - t0)}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
