# Owl Hours automation kit: approve with one click

**Version 2 (Nov 26, 2026).** What changed is listed at the bottom.

Your data updates itself, your letter drafts itself, and nothing goes out until you approve it.

## The weekly cycle
1. **Every 15 minutes (market hours):** ETF prices refresh at the top of your page.
2. **Every weekday after the close:** macro, crypto, price history, moving averages, suggested support and resistance and suggested sector scores are pulled, and a dated snapshot is saved.
3. **Wednesday morning:** the system builds your letter (4-page PDF) from that data. It writes a mechanical headline, the three-part read, the sector scoreboard, the technical page and the calendar. Your quote, question of the day and fun fact rotate from `library.json`, or come from `editorial.json` if you fill them in.
4. **You get an email from GitHub:** a new issue titled "Draft ready" with a link to the draft PDF. It lists which parts the machine wrote, so you know what still needs your words. Older open drafts close themselves.
5. **You approve with one click:** close the issue as **completed**. The clean letter is built at that moment from exactly the draft you read, then published to your archive page (`issues/index.html`) and `feed.xml`. Close it as **not planned** to decline.
6. **Your email tool sends it:** most email platforms can send a campaign when an RSS feed gets a new item. Point your tool's RSS campaign at `feed.xml`. Check your plan includes this. If it does not, download the PDF from the archive and attach or link it yourself.

If the data is stale or incomplete, no letter is built. You get an issue titled "Draft blocked" instead, with the reasons.

## What is in this folder
| File | Purpose |
|---|---|
| `index.html` | Your Owl Hours page with the live price strip and daily-data panel |
| `config.json` | Brand name, site address, sector proxies, thresholds, freshness limit |
| `editorial.json` | **The one file you edit.** Headline, reads, quote, question, fun fact, events, "what would change my mind", manual ISM and dollar index, your own sector calls |
| `library.json` | Rotating quotes, fun facts and questions used when `editorial.json` is blank |
| `fetch_quotes.py`, `.github/workflows/quotes.yml` | 15-minute price job |
| `daily_job.py`, `.github/workflows/daily.yml` | Daily data and suggestions |
| `build_draft.py` | Daily data-pack PDF and markdown (optional extras) |
| `build_letter.py`, `.github/workflows/weekly.yml` | Weekly letter draft and approval issue |
| `publish.py`, `.github/workflows/approve.yml` | Builds the clean letter and publishes it when you approve |
| `.github/push.sh` | Saves each job's results, retrying if two jobs finish at once |
| `latest.json`, `snapshots/`, `draft/`, `issues/`, `issues.json`, `feed.xml` | Results land here. `draft/context.json` freezes every number and line in the draft |

## Accounts and keys (all free tiers)
1. **GitHub:** hosts everything and runs the schedules. Use a public repository for free GitHub Pages.
2. **Finnhub** key saved as secret `FINNHUB_API_KEY` (15-minute prices).
3. **Twelve Data** key saved as secret `TWELVEDATA_API_KEY` (daily history).
4. FRED and CoinGecko need no key.

## Setup (about 30 to 40 minutes, no coding)
1. Create a public GitHub repository. In Settings > Secrets and variables > Actions add the two secrets.
2. Upload all files (Add file > Upload files). If the hidden `.github` folder does not upload, use Add file > Create new file, type `.github/workflows/<name>.yml`, and paste each workflow file's contents. There are five workflows.
3. Settings > Pages > Deploy from a branch > main > root.
4. In `config.json`, set `"site_url"` to your Pages address (for example `https://yourname.github.io/yourrepo`) so the feed has full links. Set `"brand"` if you want a different name. Paste your firm's approved disclosure into `"firm_disclosure"`.
5. In Settings > Actions > General, under Workflow permissions, choose **Read and write permissions**.
6. Run once from the Actions tab: Refresh quotes, then Daily data and draft, then Weekly letter draft.
7. Check your email for the "Draft ready" issue. Open the draft PDF. Close the issue as completed. Confirm `issues/index.html` now lists the letter.

## Editing the letter
Open `editorial.json` on GitHub (pencil icon), change any text, save, then run **Weekly letter draft** again. Leave a field blank to let the system write it. Keep straight quotes and commas intact. Add upcoming events under `events`.

## Safety checks built in
- **Freshness guard:** no draft if data is older than `max_data_age_hours` (72 by default), or if too few series arrive.
- **Failed sources** are listed as warnings in the issue instead of silently dropped.
- **No clean copy before approval.** Only the DRAFT-marked PDF exists until you approve. The clean one is built from `draft/context.json` at approval, so it matches what you read word for word.
- **Stale approvals are refused.** Closing an old issue cannot publish a newer draft you have not read.
- **Honest labels.** Automated sector readings are called "sector momentum" (5-day return versus the S&P 500), never "my calls". Anything you set in `sector_overrides` is marked "(author)".
- **Nothing publishes without your approval.** Closing as completed is the only action that publishes.

## Not covered yet
- The AI spending table, the calendar and the neo-cloud sector score are manual (use `ai_notes`, `events` and `sector_overrides`).
- ISM, the dollar index and Fed odds are licensed data. Enter ISM and the dollar index in `manual_macro`.
- The headline and reads are mechanical templates. They are a starting point, and you should rewrite them when the story needs your judgment.

## Good to know
- **Not tested against the live services.** I tested the code with simulated data. The first real runs may need small fixes if a provider changed its format. The Actions log shows what failed.
- **Public repository:** everything in it is publicly visible, including the DRAFT PDF, `draft/context.json` and snapshots, before you approve. To keep drafts private, use a private repository with GitHub Pro (Pages on a private repo needs a paid plan). A reader archive that needs a password requires paid hosting or a developer.
- **Data terms:** the free Finnhub and Twelve Data plans are for personal use, and the FRED high-yield spread is ICE data with its own limits. Check each provider's terms, or move to a plan that allows redistribution, before publishing their numbers to readers.
- **Licensing and compliance:** if you are registered with a firm, a public newsletter is likely an outside business activity and a public communication. Disclose it to your firm and get its written approval before publishing. Closing the issue is your release step, not your firm's review, and you cannot approve your own communications. Keep this project off work email and work devices.
- **GitHub schedules are best effort** and can run a few minutes late. If runs stop, press Enable workflow in the Actions tab.

## What changed in version 2
- Clean PDF is built only at approval, from the frozen draft. Older drafts close themselves, and approving a stale issue is refused.
- Every job pulls before pushing and retries, so jobs that finish together no longer lose saves.
- Letter labels: "sector momentum" instead of "my sector calls"; author overrides marked; DRAFT watermark on every draft page.
- "What would change my mind" comes from `editorial.json` (left out when empty) instead of four fixed lines.
- Stale November events and unverified Fed claims removed from `editorial.json`. Add your own, confirmed.
- Optional `firm_disclosure` in `config.json` prints on the letter and archive.
- Page: saves in your browser on GitHub Pages (or your claude.ai record when opened there), with Backup and Restore. All downloads work on GitHub Pages. NYSE holidays and early closes through 2028. Opens blank instead of on an old opinion. Asks before replacing a same-day snapshot. Crypto and metals no longer count toward the macro read's three-signal minimum. Calendar loads from `editorial.json`.
- Not done yet: grading past calls against what sectors actually did (the scoreboard).
