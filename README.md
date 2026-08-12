# 🔍 B2B Lead Finder — Local Autopilot

A self-hosted, **zero-cost** B2B lead generation and cold outreach tool.  
Searches DuckDuckGo/Bing → scrapes business websites → **verifies emails (5-layer check)** → stores in SQLite → optional screenshots → Telegram alerts → SMTP cold outreach.

**No paid APIs. No subscriptions. Runs entirely on your machine.**

---

## ⚡ 5-Minute Setup (Windows)

### 1. Install Python

Download Python 3.10+ from [python.org](https://www.python.org/downloads/).  
✅ Check **"Add Python to PATH"** during install.

### 2. Clone / Download

```bash
cd Desktop
git clone <repo-url> "AI B2B Lead Finder"
cd "AI B2B Lead Finder"
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright (for screenshots — optional)

```bash
playwright install chromium
```

### 5. Configure

Open `config.yaml` in any text editor and set:

| Setting | What to change |
|---------|---------------|
| `search.niches` | Your target industries, e.g. `["dental clinics", "law firms"]` |
| `search.locations` | Target cities, e.g. `["Casablanca", "Rabat"]` |
| `telegram.bot_token` | Your Telegram bot token (optional) |
| `telegram.chat_id` | Your Telegram chat ID (optional) |
| `email.smtp_user` | Your Gmail address (only if sending emails) |
| `email.smtp_password` | Your Gmail app password (only if sending emails) |

> ⚠️ **Email sending is OFF by default.** You must set `email.enabled: true` to send emails. We recommend running `--dry-run` first.

### 6. First Run (Dry Run — Recommended!)

```bash
python main.py --niche "dental clinics" --location "Casablanca" --country ma --max 10 --dry-run
```

This will:
- ✅ Search for businesses
- ✅ Scrape contact info
- ✅ Verify emails (syntax + DNS + MX + SMTP)
- ✅ Save leads to database
- ✅ Export CSV
- ❌ **NOT** send any emails

Check your results in `data/results.csv`.

---

## 🚀 Usage

### Full Pipeline

```bash
python main.py --niche "dental clinics" --location "Casablanca" --country ma --max 20
```

### Search + Scrape Only (no email)

```bash
python main.py --search-only --niche "law firms" --location "Rabat" --country ma
```

### Email Only (send to unsent verified leads in DB)

```bash
python main.py --email-only
```

### Re-verify Unverified Emails

```bash
python main.py --verify-only
```

### Dry Run (scrape + verify, no email)

```bash
python main.py --dry-run --niche "restaurants" --location "Marrakech"
```

### Use Config Defaults (reads niches/locations from config.yaml)

```bash
python main.py --dry-run
```

---

## 📧 Email Verification (5 Layers)

Every scraped email passes through a **5-layer verification pipeline** before it's ever sent to:

| Layer | Check | Rejects |
|-------|-------|---------|
| 1. **Syntax** | RFC 5322 format validation | Malformed addresses |
| 2. **DNS** | Domain A/AAAA record exists | Dead/typo domains |
| 3. **MX Records** | Domain has mail servers | Domains that can't receive email |
| 4. **SMTP RCPT TO** | Mailbox exists (no email sent) | Non-existent mailboxes |
| 5. **Catch-All** | Tests random address on domain | Flags catch-all servers |

**Verification statuses:**
- `valid` — mailbox confirmed to exist ✅
- `catch_all` — server accepts all addresses (higher bounce risk) ⚠️
- `invalid` — confirmed non-existent ❌ (never emailed)
- `unverified` — check was inconclusive, retried on next run 🔄

> **ISP blocks port 25?** Set `verification.skip_smtp_check: true` in `config.yaml` — layers 1-3 still protect you.

---

## 📂 Project Structure

```
lead-bot/
├── main.py                 # CLI orchestrator
├── config.yaml             # Your settings (never commit this!)
├── requirements.txt        # Pinned dependencies
├── README.md
├── .gitignore
├── src/
│   ├── searcher.py         # DuckDuckGo/Bing search
│   ├── scraper.py          # Website scraping for contacts
│   ├── verifier.py         # 5-layer email verification
│   ├── storage.py          # SQLite database + dedup
│   ├── screenshotter.py    # Playwright screenshots
│   ├── notifier.py         # Telegram bot alerts
│   ├── mailer.py           # SMTP sending with caps
│   └── logger.py           # Console + file logging
├── data/
│   ├── leads.db            # SQLite database
│   ├── results.csv         # Human-readable export
│   └── screenshots/        # Site screenshots
├── templates/
│   └── pitch_email.html    # Cold email template (edit before sending!)
└── logs/
    └── run.log             # Rotating log file
```

---

## 🔒 Safety Features

- **Email OFF by default** — must explicitly enable in config
- **Daily send cap** (default 30/day) — persisted in SQLite, works across restarts
- **Email verification** — only verified emails are ever sent to
- **Dedup by domain** — never emails the same business twice
- **Unsubscribe footer** — CAN-SPAM/GDPR compliant in every email
- **Respectful scraping** — randomized delays, rotating user agents, robots.txt
- **Crash-proof** — every external call wrapped in try/except, failures logged and skipped

---

## 📱 Telegram Setup (Optional)

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot → copy the **bot token**
3. Message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your **chat ID**
4. Add both to `config.yaml`:
   ```yaml
   telegram:
     enabled: true
     bot_token: "123456:ABC-DEF..."
     chat_id: "987654321"
   ```

---

## 📧 Gmail Setup (for sending emails)

1. Enable 2-Factor Authentication on your Gmail
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate an app password for "Mail"
4. Add to `config.yaml`:
   ```yaml
   email:
     enabled: true
     smtp_user: "you@gmail.com"
     smtp_password: "your-16-char-app-password"
     sender_name: "Your Name"
   ```
5. **Edit `templates/pitch_email.html`** with your actual value proposition before sending!

---

## ⚖️ Legal Notice

This tool is for **legitimate business outreach only**. You are responsible for:
- Complying with CAN-SPAM, GDPR, and local anti-spam laws
- Only contacting businesses with publicly listed contact information
- Honoring unsubscribe requests promptly
- Using reasonable send volumes

The default email template includes a mandatory unsubscribe/opt-out line.

---

## 📋 CLI Reference

| Flag | Description |
|------|-------------|
| `--niche "..."` | Business niche to search |
| `--location "..."` | City/region to search in |
| `--country XX` | Country code (e.g. `ma`, `us`) |
| `--max N` | Max results per query (default: 25) |
| `--search-only` | Search + scrape only, no email |
| `--email-only` | Send emails to unsent verified leads |
| `--verify-only` | Re-verify unverified emails |
| `--dry-run` | Full pipeline but no actual emails |
| `--config PATH` | Path to config file (default: config.yaml) |
