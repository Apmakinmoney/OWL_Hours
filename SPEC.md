# Owl Hours — Product Spec (running)

## Round 1 answers (2026-11-26)

**First open & guide**
1. Guide: both — first-time tour + "?" button on the clock
2. Tour format: short video
3. Owl teaches it (speech bubbles)
4. App opens on the Clock showing the MARKET's needle

**Clock**
5. Sector % shown on tap only
6. Subtle motion
7. Price boxes stay on top

**Owl**
8. Daily line + speaks on changes
9. Tone: professor
10. Owl styles to add: Wall St suit, Gold bar, Samurai, Pixel/8-bit, Crypto (with Scholar + Night = 7 total)

**Sectors**
11. Keep 5 call levels (++ + 0 − −−)
12. Tap a sector → one line on why it matters in the cycle
13. Custom tickers under sectors — later

**Macro**
14. One-line meaning under each number
15. Crypto updates hourly
16. Add jobs report, CPI, Fed meeting dates

**Record / scoreboard**
17. Grade calls right/wrong on direction
18. Leaderboard — later
19. Streaks + badges — yes

**Letter**
20. Show latest Market Talks issue in Letter tab
21. Subscribe from inside the app

**Alerts**
22. Market open/close + user picks their own

**Brand**
23. Small "by The Market Talks"
24. Dark only for now

**Business**
25. Free now, paid tier later

## Round 2 answers (2026-11-26)

**Paid tier & accounts**
26. Paid tier: $10/mo
27. Paid perks: custom alerts, full history + replay, Options Flow tab
28. Sign-in: email magic link
29. Calls sync across devices

**Clock & owl**
30. Share button → branded image card of today's clock
31/34. Owl daily line = investor wisdom / Market Wizards-style lesson, shown before open (~8 am CT)
32. Top 3 sectors driving the needle shown under the clock
33. Timeframe switch — no preference (default: Today/Week/Month)
35. Daily lesson: random rotation
42. Haptics only (note: iPhone web apps can't vibrate — works on Android / future App Store app)
43. Owl voice reads daily line — soon

**Features**
36. Options Flow tab — Phase E, paid
39. Learn section (market-cycle lessons) in Letter tab
40. Earnings calendar in Macro
41. Watchlist — later
44. Friday weekly recap card
45. Community — later
48. No you-vs-market chart on Record

**Platform & brand**
37. Web app now, App Store later
38. Domain: owl.themarkettalks.org
46. Privacy-friendly usage tracking
47. Text size follows phone setting
49. Small footer: educational tool, not advice

**Launch**
50. First beta testers in ~2 weeks (≈ Dec 10, 2026)

## Built — Phase B1 (2026-11-26)
Owl tour (story-style, auto-advance) + "How to read it" button · Owl lesson of the day (36 lessons, random daily rotation, owl says it once/day) · "Pulling the needle" top-3 drivers · Sector tap card (ETF, today vs S&P, 20-day, why it matters) · Macro one-liners · Share card PNG · Scoreboard (hit rate, streaks, 6 badges) · "by The Market Talks" byline + footer · Haptics on Android
Next: weekly Friday recap, hourly crypto, CPI/jobs/Fed dates, earnings calendar, Learn section, sync + sign-in, more owls.

## Built — Phase B2 data pack (2026-11-26)
Hourly crypto robot (crypto.yml → crypto.json, BTC/ETH/XRP + 24h) · Calendar robot in Daily (calendar_job.py → calendar.json): Fed decision days (Fed revised 2027 schedule, Nov 12 2026), CPI/Jobs/GDP/PCE/Retail dates from FRED, big-name earnings 14 days from Finnhub · Latest prints: CPI YoY, unemployment, payrolls · "Next big event" chip on Clock · Friday weekly recap (Clock Fri close→Mon open, always on Record; owl announces once/week)

## Round 3 answers (2026-11-26) — Layer 3 (+1)
51. Level chips on the price boxes · 52. Levels for SPY/QQQ/DIA/IWM · 53. Owl calls out crossings · 54. Tap box → 3-month mini chart with levels
55. Metals card on Macro tab · 56. Gold/silver ratio, GDX vs metal, platinum + palladium, 50/200-day · 57. Per ounce only
58. Letter tab renamed Learn (newsletter tools inside) · 59. Lessons owl-narrated + animated · 60. Quizzes beginner → pro · 61. Audience: both beginners and traders · 62. Tap-to-define glossary
63. Sector heatmap · 64. Top holdings per sector · 65. Small fear meter (VIX + credit) on Clock · 66. Historical analogs — later
67. Optional "why" note per call · 68. Auto-draft issue from week's data · 69. Recap share image · 70. New owls now: Wall St, Gold bar, Superhero (original design)
71. Offline mode · 72. Owl "what changed today" after close · 73. Sector of the week · 74. Free basic voice now, premium voice paid later
75. Build ALL of Layer 3

## Built — Layer 3 (2026-11-26)
Level chips on price boxes + tap for 3-month chart (200d/50d/support/resistance) · Owl calls 50/200-day crossings · Fear meter (VIX + HY spread) · Owl's after-close wrap · Precious metals card on Macro (spot gold/silver/platinum via Twelve Data, palladium falls back to PALL ETF if spot unavailable; gold/silver ratio; GDX vs gold) · Sector heatmap (today/5d/20d) + sector of the week + big-name holdings + "Make my call" · Learn tab (Letter renamed): 6 owl-narrated lessons w/ animated clock + 3-question quizzes beginner→pro, 3 new badges, glossary (28 terms, tap-to-define across app) · Free owl voice (speechSynthesis), toggle on Record + in lessons · Auto-draft adds weekly recap, calendar, metals, lesson · Recap share image · 3 new owls: Wall St, Gold bar, Super owl · Offline mode (sw.js) · Fixed calendar label clash from data pack

## Round 4 answers (2026-11-26) — modes + Layer 4
76. Owner unlock: tap owl 7 times + code · 77. Owner-only: newsletter desk + checklist, daily data panel/robot warnings, backup/restore/CSV, compliance items
78. Customers' Learn tab shows latest Market Talks issue + archive · 79. Owner dashboard (robot status, run times, warnings, GitHub links)
80. Customers see Market + The Owl's call by default; optional "make my own calls" game for scoreboard · 81. Name: "The Owl's call" · 82. Show owner's one-line why · 83. Show owner's track record publicly
84. Accounts: Supabase · 85. Payments: Stripe · 86. 7-day trial · 87. $100/yr plan (plus $10/mo)
FEEDBACK: more detailed/futuristic visuals — clock that pops (more color/detail), collective heatmap, richer 3-month record chart
88. Vibe: Bloomberg terminal, data-dense · 89. Treemap sized by sector weight · 90. Record chart: phase bands + glow trail
91/92. Newsletter platform: none yet, decide later · 93. Domain registrar: not sure (check before owl.themarkettalks.org)
94. Email REQUIRED for free accounts · 95. Push: daily lesson + snapshot of the day · 96. Weekly recap email, free users too
97. Beta: coworkers + Market Talks readers · 98. Floating feedback button everywhere · 99. GoatCounter analytics
100. Owner GitHub key for publishing The Owl's call — later

## Plan
Layer 3.5: customer/owner modes, Owl's call (publish needs key), Bloomberg-style visual upgrade (clock, treemap, record chart), floating feedback, GoatCounter.
Layer 4: Supabase email sign-in (required), sync, Stripe ($10/mo, $100/yr, 7-day trial), push (lesson + daily snapshot), weekly email, domain, newsletter platform.

## Built — Layer 3.5 (2026-11-26)
Customer mode default; owner mode = tap top owl 7× + code (hash in page; code given to owner privately). Owner-only: daily data panel, presets, backup/restore/CSV, macro editorial tools (AI tracker, manual technical levels), newsletter desk. Customers: macro read-only, Sectors controls hidden until "Make your own calls" game is on.
The Owl's call: owlcall.json (published from Sectors in owner mode via GitHub key, or download + upload). Shows as a view on the clock, a card on Clock, OWL column on the sector board. Owner hit rate NOT shown publicly (owner decision).
Owner dashboard (Record): robot freshness, warnings, GitHub links, publishing key, switch to customer view.
Terminal visuals: % labels + glow on wheel pips, needle glow, terminal data strip, treemap "Market map" sized by approx S&P weights + themes row, monospace sector board, record chart w/ glow trail + pulse.
Floating feedback button (mailto when FEEDBACK_EMAIL set; copies text until then). GoatCounter (code owlhours) + tab events. Learn tab shows latest Market Talks issue + archive from issues.json.

## Built — Layer 3.75 (2026-11-27) beginner pass
Clock-first layout (wheel at top, cards below) · removed % labels on wheel and the terminal strip · driver chips show sector name + ▲/▼ only · customers get plain words (no degrees; clarity → Clear/Moderate/Mixed; drift → one sentence; session box + drift window owner-only) · CNBC-style auto-running ticker under the clock: SPY/QQQ/DIA/IWM + level chip, 14 sector ETFs, gold (spot), silver ETF, BTC; tap index → chart · 4 price boxes now owner-only · tour cut to 4 steps · Macro: calendar + prints first, customers see static arrows, empty level boxes hidden, only highlighted environments shown, neutral wording · Record: scoreboard + snapshot table only when playing · metals show $ + per oz / per ETF share · smaller feedback button

## Round 5 + Built — Layer 3.8 (2026-11-27) watchlist
Owner top 5: NVDA, SPCX (SpaceX, public since Jun 2026), TSLA, LLY, MSFT — owner mode only. Customers start with SPY, QQQ, VIX, UUP (dollar), GLD, SLV, AAPL, MSFT, AMZN, NVDA. Active watchlist up to 10: add from ~35 names, remove, reorder; 11th asks which to drop. Condensed rows (ticker badge in sector color, name, top headline, price, day %); tap → detail sheet with swipeable tabs Overview (valuation+growth, plain-English P/E hint, 52-wk range, vs sector 20d, profile) · Chart (3 mo, 50d, 52w hi/lo) · Analysts · Earnings (beats/misses + next date) · News (3, open at source). Owl comments on 3%+ moves once a day. Neon market map + neon board. Ticker on Clock and Sectors (Sectors adds watchlist names); ETH + XRP added. Big deals (M&A) top 5 + show more on Macro.
Robots: fetch_quotes.py now also quotes the watchlist universe every 15 min (0.9s spacing); new companies_job.py + companies.yml hourly (weekdays 12–22 UTC at :20, weekends once): headlines + mergers hourly; valuation/profile/analysts/earnings (Finnhub) and 65-day closes (Twelve Data) once a day.
Later: search any US stock (Layer 4 server).

## Round 6 + Built — Layer 3.95a (2026-11-27) proof engine + modes
Goal: prove an edge (hedge-fund grade later), keep the education tool. Claim tested first: favored sectors beat the S&P over 1 month, vs SPY, equal-weight, momentum (top 3 by 3 mo) and random picks; ~10y history; only sectors that existed; models A (top 3), B (needle's phase), C (defensive switch); monthly rebalance; 0.05% costs; walk-forward; 3 preset blends; clarity filter on/off; metrics: excess, Sharpe, max DD, hit rate.
Risk tiers: highest risk, aggressive, moderately aggressive, moderate, conservatively moderate, conservative, retirement income (sleeve % vs AGG/SHY/GLD/dividend ETFs, sectors held, drawdown guard). Hard assets (owner is a big gold/silver fan): clock-steered metals mix + metals core/miners switch, vs GLD and 50/50.
Macro inputs: v2. Quant: risk targeting, factor (momentum+low vol+trend), k-means regimes now; value/quality + ML later (3.95b). Paper portfolios live from start, owner-only. Results: owner Lab + shareable report later. Weekly re-run (Saturday). If it fails vs momentum: change design + retest, keep education.
Plan: ~2 weeks owner-only testing, then ~15 trader friends get the Owl's daily read (7:30 am CT, app + email via Gmail secrets GMAIL_USER, GMAIL_APP_PASSWORD, READ_TO).
Modes: owl 7-tap → code → Client / Boss / Engineering (Engineering adds Lab tab).
Files: backtest_job.py + backtest.yml (weekly), clockmath.py, paper_job.py (in daily.yml), read_job.py + morning.yml.

## First real backtest (run 2026-11-27, Mar 2017–Oct 2026, 115 months)
SPY 14.6% CAGR / Sharpe 0.78. Equal-weight 15.8 / 0.86. Momentum 12.8 / 0.61. Random 3-sector median 14.3%.
Owl A (top 3 strongest) 11–15% — loses to SPY and random: the clock's dots are NOT a good 1-month stock-picker.
Owl B (needle's phase) 13.5–17.4%, Sharpe up to 0.92; walk-forward 16.5% / 0.84 — the one promising model; trend-heavy blends beat the base blend.
Owl C (defensive switch) 10.6–13.2% — going defensive in Dusk/Night cost money.
Phase study: after Night, SPY next month +2.44% avg, up 76% (21 months) while Night's home sectors lagged −1.32% — Night behaved contrarian-bullish in this decade.
Hard assets: clock steering didn't beat simply holding gold (12.3% / 0.68). Factor ≈ SPY. 12% vol target too tight.
Bug found: drawdown guard never released (moderately aggressive stuck in Treasuries); fixed with shadow-drawdown hysteresis in backtest + paper.
Caveats: one strong tech-led bull decade, small sample, many variants tested.

## Round 7 (2026-11-27) — 3.95b grill (30 + 10 hard)
Look & feel: slide transitions + swipe between tabs · Macro → clean cards with value + trend sparkline · sector board → ranked glowing bars · Sectors order: map first · game calls → compact sliders grid · press feedback, shimmer loading, pull-to-refresh.
Clock is THE product: merge weekly recap + needle history into Clock; Record tab becomes Profile/settings (owl, voice, game). Under clock: ticker → daily read → accordion for the rest. Clock innovations: drag time-travel scrubber (90d), needle momentum arrow, tap needle → "why" layers (sectors/macro/breadth), forecast cone (owner/Lab first).
Model: reweight clock to 20/80 today vs 20-day trend · Owl B NOT headline yet (wait for proof) · Night framing → "fear is high; watch for the turn" · longer backtest (2000–02, 2007–09 via older funds) · 3-month horizon · needle direction signal · macro as separate test rows · tiers rebuilt on Owl B + vol sizing per tier · metals: gold/silver ratio rules + real-yield/dollar signals · weekly factsheets · Lab glow charts · options-flow (put/call, unusual activity) as Lab-tested sentiment layer.
Strategy: buyers now = advisors/RIAs + active retail traders + newsletter audience (education = give-back); funds = later product. Weekly decision the clock serves: which sectors to tilt toward/away. Proof bar before funds: 6 months live paper. Kill rule: decide then (pushed back). Data: stay free; commercial data licensing needed before charging (later). Framing: both research and signals by user type (flagged). Advisor hook: all-in-one concierge snapshot (client updates, market read, strategy) + trader view. Owner time: 5–10 hrs/week.
Build order: look & feel first, then Lab tests.

## Built — 3.95b (2026-11-27)
Part 1: slide transitions + swipe tabs, press feel, pull-to-refresh, shimmer loading · Clock-first: under the clock = momentum line + time-travel scrubber, ticker, daily read, then accordion (Owl's call, Today's wrap, Weekly recap, Needle history, Market mood, Lesson, owner: index ETFs) · momentum arrow on wheel · tap needle → "why" sheet (sectors for/against, breadth, macro context) · Record → Profile (game, owl, voice, snapshots/backups) · Macro "at a glance" cards w/ sparklines (daily_job saves 60-pt FRED spark) · Sectors: map first, glowing ranked bars, game slider grid · clock blend 20/80 everywhere (app, daily_job, clockmath) · plain words on mini dial for customers · Night read reframed ("fear is high; watch for the turn").
Bot office (Engineering → Lab): Sims-style room, 8 little people (Quinn quotes, Dana daily, Cal calendar, Penny paper, Coco crypto, Rex companies, Sage backtest, Wren writer) walking/typing/napping by status, plumbob diamonds, tap for report + roster.
Part 2: backtest from 1999 (two Twelve Data windows) + FRED macro history · default blend trend · phase study adds 3-month · direction study + Owl D (needle direction) · Owl B held 3 months · macro filter rows (credit, VIX, curve) · tiers on Owl B + per-tier vol caps · metals: gold/silver ratio rule, real-yield + dollar rule · bt_stats.py: arch SPA + StepM "real or luck", MAPIE split-conformal forecast cone · Lab: luck verdict, cone, direction table, macro tests tab, printable factsheets. Options-flow layer: pending a data source.

## 3.97 Owl Hours HQ (built 2026-11-27, Lab only)
- Rooms you swipe between: Open floor, Exec suite, Trading floor, Research lab, Web & data, People & CRM, Engineering. 34 people, mixed skin tones. CEO (owner) wears the crown; nobody outranks the CEO.
- office_job.py: Chief of Staff (Morgan) report 7:00 am + 4:30 pm CT weekdays, Saturday review. Desks: Watchlist (Jules), Metals (Sterling), Risk (Ray), Website (Webb), Data QA (Ada), HR (Harper, weekly), Innovation (Nova, weekly). CRM (Cruz) on hold until accounts.
- Talking to the office: free rule-based chat in the Lab (local history) + email replies via inbox.yml every 30 min, CEO address only. AI answers later (no paid key for now).
- Engineering: Atlas + 5 engineers + 10 coders. changes.json holds every change request (what / why / files / risk). Nothing ships without CEO approval; APPROVED/DENIED emails log to approvals.json.
- Email goes to thearchitectceo@gmail.com (secrets GMAIL_USER, GMAIL_APP_PASSWORD, READ_TO).
