# 🚀 AI B2B Lead Finder (Cloud Autopilot Edition)

An fully automated, cloud-hosted B2B lead generation and cold outreach tool.  
Designed to run 24/7 on **GitHub Actions** completely for free. It searches Google Maps/Bing → scrapes business websites → **verifies emails (5-layer check)** → stores them in SQLite → and sends cold outreach using an **SMTP Fleet rotation**.

**Zero paid APIs. Zero subscriptions. Runs entirely in the cloud on autopilot.**

---

## 🔥 Key Features

1. **GitHub Actions Autopilot**: Scheduled to run every hour (`0 * * * *`). It automatically wakes up, scrapes up to 50 leads per run, commits the new leads to the database, and goes back to sleep.
2. **High-Volume Scaling (600+ Emails/Day)**: By running hourly, the system accumulates ~1,200 leads a day, easily providing enough verified targets to hit 600+ emails per day.
3. **SMTP Fleet Rotation**: Avoid spam filters and sending limits by rotating through a fleet of SMTP accounts (e.g., 4 free Brevo accounts). The system automatically selects an account for each batch.
4. **Persistent State Tracking**: The `leads.db` SQLite database is force-tracked by Git. GitHub Actions commits the database back to the repository after every run, ensuring you never email the same person twice.
5. **5-Layer Verification**: Checks syntax, DNS, MX records, SMTP RCPT TO, and Catch-All servers before sending a single email.

---

## ⚡ 5-Minute Cloud Setup

### 1. Fork or Clone the Repository
Push this repository to your own private GitHub account.

### 2. Set Up Your SMTP Fleet
Create free SMTP accounts (e.g., Brevo) to use for sending emails. Each Brevo account allows 300 emails/day. With 4 accounts, you can send 1,200 emails/day for free.

### 3. Add GitHub Secrets
Go to your GitHub Repository -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.

Create a secret named `CONFIG_YAML` and paste your entire configuration file into it.

Example `CONFIG_YAML`:
```yaml
search:
  niches:
    - "dental clinics"
    - "law firms"
    - "real estate agencies"
  locations:
    - "New York"
    - "London"
    - "Toronto"
  max_results_per_query: 20

email:
  enabled: true
  daily_send_cap: 200
  accounts:
    - smtp_host: "smtp-relay.brevo.com"
      smtp_port: 587
      smtp_user: "your_brevo_login_1@domain.com"
      smtp_password: "your_password_1"
      sender_name: "Your Name"
      sender_email: "verified_sender_1@domain.com"
    - smtp_host: "smtp-relay.brevo.com"
      smtp_port: 587
      smtp_user: "your_brevo_login_2@domain.com"
      smtp_password: "your_password_2"
      sender_name: "Your Name"
      sender_email: "verified_sender_2@domain.com"
```

### 4. Enable GitHub Actions
Go to the **Actions** tab in your repository and click **"I understand my workflows, go ahead and enable them."**

The workflow (`.github/workflows/scraper.yml`) will automatically trigger every hour.

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

---

## 🛠️ Local Testing & CLI Reference

If you want to run the tool locally on your own machine instead of the cloud:

```bash
pip install -r requirements.txt
playwright install chromium
```

| Command | Description |
|------|-------------|
| `python main.py --niche "gyms" --location "Miami"` | Full pipeline: search, verify, email |
| `python main.py --search-only --niche "law firms"` | Search + scrape only, no email |
| `python main.py --email-only` | Send emails to unsent verified leads |
| `python main.py --random-cities 1 --max 50` | Picks 1 random city from config and scrapes 50 leads |
| `python main.py --dry-run` | Full pipeline but no actual emails |

---

## ⚖️ Legal Notice

This tool is for **legitimate business outreach only**. You are responsible for:
- Complying with CAN-SPAM, GDPR, and local anti-spam laws
- Only contacting businesses with publicly listed contact information
- Honoring unsubscribe requests promptly
- Using reasonable send volumes

The default email template includes a mandatory unsubscribe/opt-out line.
