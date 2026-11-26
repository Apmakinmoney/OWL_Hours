"""Builds the draft files from latest.json: a markdown draft for the letter and a PDF data pack.
Run after daily_job.py. Needs reportlab (pip install reportlab). Nothing here is published; the author reviews and writes the narrative."""
import json, os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

NAMES = {"y10": "10-year Treasury yield (%)", "y2": "2-year Treasury yield (%)", "curve": "Yield curve, 10y minus 2y (pts)",
         "hy": "High-yield credit spread (%)", "oil": "Oil, WTI ($)", "brent": "Oil, Brent ($)", "vix": "VIX",
         "btc": "Bitcoin ($)", "eth": "Ether ($)", "xrp": "XRP ($)", "gold": "Gold (GLD direction)", "silver": "Silver (SLV direction)"}
SECT = {"FIN": "Financials", "REIT": "Real estate", "DISC": "Consumer discretionary", "TECH": "Tech and software", "CYB": "Cybersecurity",
        "SEMI": "Semiconductors", "COMM": "Communication services", "IND": "Industrials", "MAT": "Materials", "ENGY": "Energy",
        "GOLD": "Gold miners", "STPL": "Consumer staples", "HLTH": "Healthcare", "UTIL": "Utilities"}
WORD = {1: "rising", 0: "flat", -1: "falling", None: "n/a"}
SCORE = {2: "rising hard", 1: "rising", 0: "flat", -1: "falling", -2: "falling hard"}


def fmt(v, nd=2):
    return "n/a" if v is None else f"{v:,.{nd}f}"


def build(path="latest.json", outdir="draft"):
    d = json.load(open(path))
    day = d["asOf"][:10]
    os.makedirs(outdir, exist_ok=True)
    macro, etf, sect = d.get("macro", {}), d.get("etf", {}), d.get("sectors", {})

    # ---- markdown draft ----
    L = [f"# Owl Hours draft: {day}", "", "_Auto-generated from public data. Write the headline and the read yourself, check every number, and get any required approval before publishing._", "",
         "## Headline (you write this)", "[Write the one-line story here]", "",
         "## The read in three parts (you write this)", "1. What changed:", "2. What the Fed or data said:", "3. What doesn't fit:", "",
         "## Macro signals"]
    for k, m in macro.items():
        L.append(f"- {NAMES.get(k, k)}: {fmt(m.get('level'))} ({WORD.get(m.get('dir'))})")
    L += ["", "## Suggested sector momentum (relative to the S&P 500 ETF over 5 days)"]
    for k, v in sect.items():
        L.append(f"- {SECT.get(k, k)} ({v['proxy']}): {SCORE[v['suggested']]} ({v['relReturnPct']:+.2f} pts)")
    L += ["", "## ETF levels (suggestions to review)"]
    for sym, e in etf.items():
        L.append(f"- {sym}: close {fmt(e['c'])}, 50-day {fmt(e['m50'])}, 200-day {fmt(e['m200'])}, support {fmt(e['s1'])} / {fmt(e['s2'])}, resistance {fmt(e['r1'])} / {fmt(e['r2'])}")
    if d.get("warnings"):
        L += ["", "## Data warnings"] + [f"- {w}" for w in d["warnings"]]
    L += ["", "## Before publishing", "- Which sector calls do I disagree with, and why?", "- What would change my mind?", "- Which upcoming event could break my call?",
          "", "_For education and discussion, not investment advice._"]
    open(os.path.join(outdir, f"Owl-Hours-draft-{day}.md"), "w").write("\n".join(L))

    # ---- PDF data pack ----
    NAVY = HexColor("#0C1430"); BRASS = HexColor("#E0B25B"); INK = HexColor("#14213D"); MUTED = HexColor("#5B6784"); LINE = HexColor("#CBD3E2")
    S = lambda n, sz=9, ld=12, f="Helvetica", c=INK: ParagraphStyle(n, fontName=f, fontSize=sz, leading=ld, textColor=c)
    cell, hd = S("c", 8.8, 11.5), S("h", 8.6, 11, "Helvetica-Bold", MUTED)

    def table(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRASS), ("LINEBELOW", (0, 1), (-1, -1), .5, LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 3)]))
        return t

    def deco(c, doc):
        c.saveState(); c.setFillColor(NAVY); c.rect(0, 792 - 46, 612, 46, fill=1, stroke=0)
        c.setFillColor(HexColor("#FFFFFF")); c.setFont("Times-Bold", 17); c.drawString(54, 792 - 30, "Owl Hours")
        c.setFillColor(HexColor("#B9C3E3")); c.setFont("Helvetica", 9.4); c.drawRightString(612 - 54, 792 - 29, f"Daily data pack: DRAFT for review, {day}")
        c.setFillColor(MUTED); c.setFont("Helvetica", 8); c.drawString(54, 32, "Auto-generated from public data. Not investment advice. Verify before publishing."); c.drawRightString(612 - 54, 32, str(doc.page)); c.restoreState()

    P = lambda t, st=cell: Paragraph(t, st)
    story = [Paragraph("Daily data pack", S("t", 22, 26, "Times-Bold")), Spacer(1, 4),
             Paragraph("Suggestions only. The author reviews, edits and approves everything. Sector scores compare each sector ETF's 5-day return with the S&amp;P 500 ETF.", S("d", 9.6, 13.5, c=MUTED)), Spacer(1, 10)]
    rows = [[P("Signal", hd), P("Level", hd), P("Direction", hd), P("Source", hd)]]
    for k, m in macro.items():
        rows.append([P(f"<b>{NAMES.get(k, k)}</b>"), P(fmt(m.get("level"))), P(WORD.get(m.get("dir"))), P(m.get("source", ""))])
    story += [Paragraph("Macro and crypto", S("h2", 14, 18, "Times-Bold")), Spacer(1, 4), table(rows, [190, 80, 80, 170]), Spacer(1, 12)]
    rows = [[P("ETF", hd), P("Close", hd), P("50-day", hd), P("200-day", hd), P("Support", hd), P("Resistance", hd)]]
    for sym, e in etf.items():
        rows.append([P(f"<b>{sym}</b>"), P(fmt(e["c"])), P(fmt(e["m50"])), P(fmt(e["m200"])), P(f"{fmt(e['s1'])}<br/>{fmt(e['s2'])}"), P(f"{fmt(e['r1'])}<br/>{fmt(e['r2'])}")])
    story += [Paragraph("ETF levels", S("h2b", 14, 18, "Times-Bold")), Spacer(1, 2),
              Paragraph("ETF prices differ from index levels. Suggested support and resistance come from recent swing highs and lows and the 50 and 200-day averages.", S("n", 8.6, 11.5, c=MUTED)), Spacer(1, 4),
              table(rows, [60, 90, 90, 90, 100, 100]), Spacer(1, 12)]
    rows = [[P("Sector", hd), P("Proxy", hd), P("Vs. S&amp;P 500, 5 days", hd), P("Suggested", hd)]]
    for k, v in sorted(sect.items(), key=lambda kv: -kv[1]["relReturnPct"]):
        rows.append([P(f"<b>{SECT.get(k, k)}</b>"), P(v["proxy"]), P(f"{v['relReturnPct']:+.2f} pts"), P(SCORE[v["suggested"]])])
    story += [Paragraph("Suggested sector momentum", S("h2c", 14, 18, "Times-Bold")), Spacer(1, 4), table(rows, [180, 70, 140, 110])]
    if d.get("warnings"):
        story += [Spacer(1, 10), Paragraph("Data warnings", S("h2d", 12, 15, "Times-Bold"))] + [Paragraph("- " + w, S("w", 8.6, 11.5, c=MUTED)) for w in d["warnings"]]
    SimpleDocTemplate(os.path.join(outdir, f"Owl-Hours-data-pack-{day}.pdf"), pagesize=letter, topMargin=70, bottomMargin=56, leftMargin=54, rightMargin=54,
                      title=f"Owl Hours data pack {day}").build(story, onFirstPage=deco, onLaterPages=deco)
    print(f"wrote draft/Owl-Hours-draft-{day}.md and the data pack PDF")


if __name__ == "__main__":
    build()
