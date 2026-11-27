"""The Owl's daily read: a plain-English morning note on what the clock says, ready ~7:30 am Central.

Writes dailyread.json for the app, and emails it when GMAIL_USER, GMAIL_APP_PASSWORD and READ_TO are set
(READ_TO = comma-separated addresses; everyone is BCC'd). Built only from yesterday's close and the calendar.
"""
import json, os, smtplib, sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo
import clockmath as cm

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dailyread.json")
SITE = "https://apmakinmoney.github.io/OWL_Hours/"
NEXT = {"Recovery": "Expansion", "Expansion": "Late cycle", "Late cycle": "Contraction", "Contraction": "Recovery"}
HOUR = {p[0]: p[1] for p in cm.PHASES}


def load(name, default=None):
    try: return json.load(open(os.path.join(HERE, name)))
    except Exception: return default


def where_in(ang):
    p = cm.phase(ang); f = (ang - p[2]) / 90
    return "early" if f < 1 / 3 else "middle" if f < 2 / 3 else "late"


def build(now):
    latest, hist = load("latest.json", {}), load("history.json", [])
    cal, cry = load("calendar.json", {}), load("crypto.json", {})
    z, m = cm.from_latest(latest)
    ang, cl = cm.needle(m)
    if ang is None: return None
    ph = cm.phase(ang); pos = where_in(ang); word = cm.clarity_word(cl)
    nxt = NEXT[ph[0]]
    title = f"{ph[1]} ({ph[0].lower()}), {pos}" + (" — leaning toward " + HOUR[nxt] if pos == "late" else "") + f" · {word} signals"
    strong = [s for s in m if m[s] == 2]; weak = [s for s in m if m[s] == -2]
    by_phase = {}
    for s in strong: by_phase.setdefault(cm.phase(cm.ANG[s])[0], []).append(cm.NAMES[s])
    lines = []
    if by_phase:
        lines.append("Strongest vs the S&P: " + "; ".join(f"{', '.join(v)} ({HOUR[k]})" for k, v in by_phase.items()) + ".")
    if weak: lines.append("Weakest: " + ", ".join(cm.NAMES[s] for s in weak) + ".")
    if word == "mixed":
        lines.append("The sectors are pulling in different directions, so the needle is a low-conviction read. Wait for agreement before trusting one strong day.")
    elif word == "clear":
        lines.append("The sectors largely agree, so this is a higher-conviction read than usual.")
    prev = next((h for h in reversed(hist) if h.get("date") and h["date"] < (latest.get("asOf", "")[:10] or "9999")), None)
    if prev and prev.get("m"):
        flips = [f"{cm.NAMES[s]} {'+' if m[s] > 0 else '−' if m[s] < 0 else 'flat'}{'+' if abs(m[s]) == 2 else ''}" for s in m
                 if s in prev["m"] and (m[s] > 0) != (prev["m"][s] > 0) and m[s] != prev["m"][s]]
        if flips: lines.append("Flipped since the prior close: " + ", ".join(flips[:5]) + ".")
    home_next = [s for s in cm.ANG if cm.phase(cm.ANG[s])[0] == nxt]
    watch = [f"Next on the clock is {HOUR[nxt]} ({nxt.lower()}). Its leaders are {', '.join(cm.NAMES[s] for s in home_next)}. "
             f"If they keep strengthening while today's leaders fade, the needle moves on."]
    vix = ((latest.get("macro") or {}).get("vix") or {}).get("level")
    if isinstance(vix, (int, float)):
        watch.append(f"VIX {vix:.1f}: " + ("calm" if vix < 15 else "normal" if vix < 20 else "nervous" if vix < 30 else "fearful") + " options market.")
    today = now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    events = [e for e in (cal.get("events") or []) if e.get("date") == today]
    ev = [(e.get("symbol") + " earnings" if e.get("kind") == "earnings" else e.get("title")) + (f" ({e['time']})" if e.get("time") else "") for e in events][:8]
    coins = (cry.get("coins") or {})
    crypto = ", ".join(f"{k.upper()} {v['chg24']:+.1f}%" for k, v in coins.items() if isinstance(v.get("chg24"), (int, float)))
    return {"date": today, "asOf": now.isoformat(timespec="seconds"), "title": title, "angle": round(ang, 1), "clarity": round(cl, 2),
            "lines": lines, "watch": watch, "events": ev, "crypto": crypto, "basedOn": latest.get("asOf")}


def email(read):
    user, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "READ_TO"))
    if not (user and pw and to): print("Email not set up; skipping send.", flush=True); return
    rcpt = [a.strip() for a in to.split(",") if a.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Owl's daily read: {read['title']}"
    msg["From"] = f"Owl Hours <{user}>"; msg["To"] = user
    body = [read["title"], ""] + read["lines"] + ["", "What to watch:"] + ["- " + w for w in read["watch"]]
    if read["events"]: body += ["", "On the calendar today:"] + ["- " + e for e in read["events"]]
    if read["crypto"]: body += ["", "Crypto (24h): " + read["crypto"]]
    body += ["", "Open the clock: " + SITE, "", "Educational market commentary from The Market Talks, not investment advice. Reply 'stop' to unsubscribe."]
    txt = "\n".join(body)
    html = "<div style='font-family:Georgia,serif;max-width:560px'><h2 style='margin:0 0 8px'>" + read["title"] + "</h2>" + \
           "".join(f"<p>{l}</p>" for l in read["lines"]) + "<h3>What to watch</h3><ul>" + "".join(f"<li>{w}</li>" for w in read["watch"]) + "</ul>" + \
           ("<h3>On the calendar today</h3><ul>" + "".join(f"<li>{e}</li>" for e in read["events"]) + "</ul>" if read["events"] else "") + \
           (f"<p>Crypto (24h): {read['crypto']}</p>" if read["crypto"] else "") + \
           f"<p><a href='{SITE}'>Open the clock</a></p><p style='color:#777;font-size:12px'>Educational market commentary from The Market Talks, not investment advice. Reply 'stop' to unsubscribe.</p></div>"
    msg.attach(MIMEText(txt, "plain")); msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw); s.sendmail(user, [user] + rcpt, msg.as_string())
    print(f"Emailed {len(rcpt)} readers.", flush=True)


def main(now=None, send=True):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo("America/Chicago"))
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and local.hour != 7:
        print("Not 7 am Central yet (daylight-saving duplicate run); skipping.", flush=True); return 0
    read = build(now)
    if not read: print("No clock read available.", flush=True); return 0
    old = load("dailyread.json", {})
    json.dump(read, open(OUT, "w"), indent=1)
    print(read["title"]); [print(" ", l) for l in read["lines"] + read["watch"]]
    if send and old.get("date") != read["date"]:
        try: email(read)
        except Exception as e: print(f"Email failed: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
