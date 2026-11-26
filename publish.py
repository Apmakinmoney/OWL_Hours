"""Runs when you approve a draft (close the approval issue as completed).
Builds the clean letter from draft/context.json (exactly what you reviewed), saves it in issues/, then rebuilds
issues/index.html (the reader archive), issues.json and feed.xml (for RSS-to-email tools).

Safety: it refuses to publish if the issue you closed is for a different date than the current draft,
so closing an old issue can never publish a newer, unreviewed draft."""
import json, os, sys, html
from datetime import datetime, timezone
from email.utils import format_datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CFG = json.load(open(os.path.join(HERE, "config.json")))
BRAND, SITE = CFG.get("brand", "Market Talks"), CFG.get("site_url", "").rstrip("/")


def main():
    meta = json.load(open(os.path.join(HERE, "draft", "meta.json")))
    title = os.environ.get("ISSUE_TITLE", "")
    if title and meta["date"] not in title:
        sys.exit(f"Not publishing: the issue you closed ({title!r}) is not for the current draft ({meta['date']}). "
                 "Approve the newest 'Draft ready' issue instead.")
    import build_letter
    os.makedirs(os.path.join(HERE, "issues"), exist_ok=True)
    name = f"{BRAND.replace(' ', '-')}-{meta['date']}.pdf"
    build_letter.render_final(os.path.join(HERE, "issues", name))
    idx = os.path.join(HERE, "issues.json")
    items = json.load(open(idx)) if os.path.exists(idx) else []
    items = [i for i in items if i["date"] != meta["date"]]
    items.append({"date": meta["date"], "headline": meta["headline"], "dek": meta["dek"], "pdf": f"issues/{name}",
                  "approved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "approved_via": title or "manual run"})
    items.sort(key=lambda i: i["date"], reverse=True)
    json.dump(items, open(idx, "w"), indent=2)
    url = lambda p: f"{SITE}/{p}" if SITE else p
    rows = "\n".join(f'<li><a href="{html.escape(i["pdf"].split("/",1)[1])}"><strong>{html.escape(i["headline"])}</strong></a><br><span>{i["date"]}. {html.escape(i["dek"])}</span></li>' for i in items)
    disc = html.escape(CFG.get("firm_disclosure") or "")
    open(os.path.join(HERE, "issues", "index.html"), "w").write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(BRAND)} archive</title><style>body{{font:16px/1.5 system-ui,sans-serif;max-width:680px;margin:40px auto;padding:0 18px;color:#14213d}}h1{{font-family:Georgia,serif}}li{{margin:0 0 18px;list-style:none}}span{{color:#5b6784;font-size:14px}}a{{color:#14213d}}ul{{padding:0}}small{{color:#5b6784}}</style></head>
<body><h1>{html.escape(BRAND)}</h1><p>Past issues. For education and discussion only, not investment advice.</p><ul>{rows}</ul><small>{disc}</small></body></html>""")
    feed = "".join(f"<item><title>{html.escape(i['headline'])}</title><link>{html.escape(url(i['pdf']))}</link><guid>{html.escape(url(i['pdf']))}</guid>"
                   f"<pubDate>{format_datetime(datetime.strptime(i['date'], '%Y-%m-%d').replace(hour=12, tzinfo=timezone.utc))}</pubDate><description>{html.escape(i['dek'])}</description></item>" for i in items[:20])
    open(os.path.join(HERE, "feed.xml"), "w").write(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{html.escape(BRAND)}</title><link>{html.escape(url("issues/index.html"))}</link><description>Weekly market cycle letter</description>{feed}</channel></rss>')
    print("published", name)


if __name__ == "__main__":
    main()
