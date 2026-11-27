"""Shared clock math for the robots: the same scoring and needle the app uses."""
import math

ANG = {"FIN": 8, "REIT": 22, "DISC": 36, "TECH": 52, "CYB": 66, "SEMI": 94, "COMM": 112, "IND": 132, "MAT": 165,
       "ENGY": 200, "GOLD": 222, "STPL": 240, "HLTH": 280, "UTIL": 320}
NAMES = {"FIN": "Financials", "REIT": "Real estate", "DISC": "Discretionary", "TECH": "Tech", "CYB": "Cybersecurity", "SEMI": "Semiconductors",
         "COMM": "Communication", "IND": "Industrials", "MAT": "Materials", "ENGY": "Energy", "GOLD": "Gold miners", "STPL": "Staples",
         "HLTH": "Healthcare", "UTIL": "Utilities"}
PHASES = [("Recovery", "Dawn", 0, 90), ("Expansion", "Midday", 90, 180), ("Late cycle", "Dusk", 180, 270), ("Contraction", "Night", 270, 360)]
DEFENSIVE = ["STPL", "HLTH", "UTIL"]


def phase(a):
    for p in PHASES:
        if p[2] <= a % 360 < p[3]: return p
    return PHASES[0]


def score_z(z):
    return 2 if z >= 1.2 else 1 if z >= 0.4 else -2 if z <= -1.2 else -1 if z <= -0.4 else 0


def from_latest(latest, wt=0.2, wr=0.8):
    """z and scores per sector from latest.json (rel1 and rel20 are % vs SPY)."""
    z = {}
    for sid, s in (latest.get("sectors") or {}).items():
        if sid not in ANG: continue
        r1, r20 = s.get("rel1"), s.get("rel20")
        if r1 is not None and r20 is not None: z[sid] = wt * r1 + wr * r20 / 3
        elif r1 is not None: z[sid] = r1
        elif r20 is not None: z[sid] = r20 / 3
    return z, {k: score_z(v) for k, v in z.items()}


def needle(m):
    x = y = tot = 0.0
    for sid, v in m.items():
        if v and sid in ANG:
            x += v * math.sin(math.radians(ANG[sid])); y += v * math.cos(math.radians(ANG[sid])); tot += abs(v)
    if tot == 0: return None, 0.0
    return math.degrees(math.atan2(x, y)) % 360, math.hypot(x, y) / tot


def clarity_word(c):
    return "clear" if c >= 0.6 else "moderate" if c >= 0.35 else "mixed"
