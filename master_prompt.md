# Master Prompt — Autonomous Local B2B Lead Finder & Cold Emailer

Paste this whole thing into Claude Code / Gemini CLI as the starting instruction.
It builds on top of the existing `lead_finder.py` script (already working: search
→ scrape → CSV). This prompt turns it into the full autopilot version.

---

## PROJECT BRIEF

Build a self-hosted, local-first B2B lead generation and cold outreach tool in
Python. It must run entirely on a normal Windows/Mac/Linux machine with no paid
APIs and no ongoing subscription costs. The user already has a working MVP
(`lead_finder.py`) that searches DuckDuckGo for a niche+location, scrapes
business websites for contact emails, and appends results to `results.csv`.
Extend this into a full pipeline with screenshots, Telegram alerts, and
automated SMTP outreach, while keeping everything modular so each stage can
run independently or be disabled via config.

## GOALS (in priority order)

1. Reliability over speed — must not crash on a bad site, timeout, or malformed
   HTML. Every network call wrapped in try/except, every failure logged and
   skipped, never fatal.
2. Zero paid dependencies — no Google Places API, no Hunter.io, no SerpAPI.
   Free search sources only (DuckDuckGo HTML, Bing HTML as fallback).
3. Respectful scraping — randomized delays, rotating user agents, honor
   robots.txt where reasonably possible, configurable rate limits.
4. Idempotent — running twice never double-emails or double-logs the same
   lead. Dedup by domain in a local SQLite or CSV-based seen-list.
5. Config-driven — one `config.yaml` (or `.env`) controls niche list,
   locations, daily send caps, SMTP creds, Telegram bot token, email template.
6. Observable — every run produces a clear console log and a Telegram
   summary ("Found 12 leads, sent 8 emails, 2 failed, 2 skipped as duplicates").

## ARCHITECTURE

Modular pipeline, each stage a separate Python module, orchestrated by a
`main.py` that runs the full cycle or accepts flags to run stages individually
(`--search-only`, `--email-only`, etc.):

```
lead-bot/
├── main.py                # orchestrator / CLI entrypoint
├── config.yaml             # user-editable settings (see below)
├── requirements.txt
├── README.md                # 5-minute setup guide, Windows-first
├── src/
│   ├── searcher.py         # niche+location -> list of candidate URLs
│   ├── scraper.py          # url -> {business_name, emails, phone?}
│   ├── screenshotter.py    # url -> saved PNG (playwright, headless)
│   ├── storage.py          # SQLite: leads table, dedup, status tracking
│   ├── notifier.py         # Telegram bot alerts
│   ├── mailer.py           # SMTP sending with template + throttling
│   └── logger.py           # unified logging to console + file
├── data/
│   ├── leads.db            # SQLite database (replaces plain CSV as source of truth)
│   ├── results.csv          # human-readable export, regenerated from DB
│   └── screenshots/
└── templates/
    └── pitch_email.html      # editable cold email template with {{business_name}} etc.
```

## STAGE-BY-STAGE REQUIREMENTS

### 1. Searcher (`src/searcher.py`)
- Input: niche (str), location (str), max_results (int)
- Query DuckDuckGo HTML endpoint (already implemented in the MVP — port it
  over as-is). Add a Bing HTML fallback if DuckDuckGo returns zero results
  (rate-limit resilience).
- Return deduplicated list of root domains, filtering out social media,
  directories (yelp, yellowpages, facebook, linkedin) and marketplaces —
  we want the business's own website.

### 2. Scraper (`src/scraper.py`)
- Reuse and extend the MVP's `extract_emails` / `find_contact_page` logic.
- Also extract: business name (title/og:site_name), phone number (regex),
  and a 1-line "about" snippet (first meaningful `<p>` or meta description)
  for later personalizing the email.
- Return `None` cleanly if no email found — never raise.

### 3. Screenshotter (`src/screenshotter.py`)
- Use `playwright` (headless Chromium) to capture a full-page screenshot of
  the homepage. Save as `data/screenshots/{domain}.png`.
- Must handle timeouts gracefully (10s max per site) and skip on failure
  without blocking the rest of the pipeline.
- This stage is optional and toggleable in config (`enable_screenshots: true`).

### 4. Storage (`src/storage.py`)
- SQLite table `leads`: id, date_found, business_name, website, emails,
  phone, country, screenshot_path, status (new/emailed/failed/skipped),
  emailed_at.
- `website` is UNIQUE — this is the dedup key.
- Provide functions: `add_lead()`, `mark_emailed()`, `get_unsent_leads()`,
  `export_csv()` (writes `data/results.csv` from the DB for human viewing,
  matching columns: Date, Business Name, Website, Emails, Country).

### 5. Notifier (`src/notifier.py`)
- Simple Telegram bot integration via `python-telegram-bot` or raw
  `requests` to the Bot API (no paid tier needed — free Telegram bot).
- Send a message per new lead found (business name + email), and a summary
  message at the end of each run.
- Bot token and chat ID read from `config.yaml`. Must not crash the run if
  Telegram is unreachable — log and continue.

### 6. Mailer (`src/mailer.py`)
- SMTP sending (works with Gmail app password, or any SMTP provider) using
  `smtplib` + `email.mime`.
- Load `templates/pitch_email.html`, fill in placeholders
  (`{{business_name}}`, `{{niche}}`, etc.).
- **Hard daily send cap** from config (default 30/day) to protect sender
  reputation and stay under spam thresholds — track sends via the DB, not
  an in-memory counter, so it persists across restarts.
- Random delay between sends (config: min/max seconds).
- Mark each lead `emailed` / `failed` in the DB immediately after each send
  attempt (don't batch-update at the end — a crash mid-run shouldn't lose
  progress).
- Include a plain-text unsubscribe/opt-out line in every email template by
  default (legal requirement in most jurisdictions for commercial email —
  CAN-SPAM/GDPR).

### 7. Orchestrator (`main.py`)
CLI flags:
```
python main.py --niche "dental clinics" --location "Casablanca" --country ma --max 20
python main.py --search-only ...
python main.py --email-only          # just flush unsent leads from DB
python main.py --dry-run             # scrape + log, never actually send email
```
Full-cycle flow: search → scrape → (optional) screenshot → store in DB →
notify via Telegram → send emails (respecting daily cap) → export CSV →
final Telegram summary.

## CONFIG FILE (`config.yaml`)

```yaml
search:
  niches: ["dental clinics", "law firms"]
  locations: ["Casablanca", "Rabat"]
  max_results_per_query: 25

scraping:
  min_delay_seconds: 1.5
  max_delay_seconds: 3.5
  timeout_seconds: 10

screenshots:
  enabled: true

telegram:
  enabled: true
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"

email:
  enabled: false        # off by default — user must explicitly opt in
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  smtp_user: "you@example.com"
  smtp_password: "app_password_here"
  daily_send_cap: 30
  min_delay_seconds: 30
  max_delay_seconds: 90
  template_path: "templates/pitch_email.html"
  sender_name: "Your Name"
```

## NON-NEGOTIABLE SAFETY / QUALITY RULES

- `email.enabled` defaults to `false`. The tool must never send real emails
  on a first run without the user explicitly flipping this on — this
  prevents accidental spam runs during testing.
- Never hardcode credentials in source files — everything sensitive lives in
  `config.yaml`, which must be listed in `.gitignore`.
- Respect the daily send cap even across multiple `main.py` invocations in
  the same day (persisted in SQLite, not memory).
- Every external call (search, scrape, screenshot, Telegram, SMTP) is
  wrapped so one failure never crashes the whole run.
- Log everything to both console and a rotating `logs/run.log` file.

## DELIVERABLES FOR THIS SESSION

1. Full folder structure and all files listed above, working end to end.
2. `requirements.txt` pinned to specific versions.
3. `README.md`: Windows-first, 5-minute setup — Python install, pip install,
   config.yaml walkthrough, first dry run, then first real run.
4. A `--dry-run` mode that's the default recommended first command in the
   README so the user can validate lead quality before ever sending email.

Build it incrementally: get search + scrape + CSV export solid first
(this already exists as a rough MVP — refactor it into `src/searcher.py` and
`src/scraper.py`), then layer in storage/dedup, then screenshots, then
Telegram, then SMTP last. Test each stage in isolation before wiring the
full orchestrator.
