#!/usr/bin/env python3
"""
B2B Lead Finder — CLI Orchestrator

Usage:
    python main.py --niche "dental clinics" --location "Casablanca" --country ma --max 20
    python main.py --search-only --niche "law firms" --location "Rabat"
    python main.py --email-only
    python main.py --verify-only
    python main.py --dry-run --niche "dental clinics" --location "Casablanca"
"""

import argparse
import sys
import time
import random
import yaml
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from src.logger import get_logger, setup_logging
from src.searcher import search_leads
from src.scraper import scrape_lead
from src.verifier import verify_emails, filter_valid_emails
from src import storage
from src.notifier import send_lead_notification, send_summary
from src.mailer import send_batch

logger = get_logger(__name__)

# ─────────────────────────────────────────────
#  Config loader
# ─────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    """Load config.yaml from project root."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded config from {config_path}")
        return config or {}
    except FileNotFoundError:
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

# ─────────────────────────────────────────────
#  Pipeline stages
# ─────────────────────────────────────────────

def run_search(niche: str, location: str, max_results: int, config: dict) -> list[str]:
    """Stage 1: Search for business URLs."""
    logger.info(f"═══ SEARCH: '{niche}' in '{location}' (max {max_results}) ═══")
    urls = search_leads(niche, location, max_results, config)
    logger.info(f"Search complete: {len(urls)} candidate URLs found")
    return urls


def run_scrape(urls: list[str], config: dict) -> list[dict]:
    """Stage 2: Scrape each URL for contact info."""
    logger.info(f"═══ SCRAPE: processing {len(urls)} URLs ═══")
    leads = []
    
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[cyan]Scraping websites...", total=len(urls))
        for i, url in enumerate(urls, 1):
            try:
                lead = scrape_lead(url, config)
                if lead:
                    lead["website"] = url
                    leads.append(lead)
                    logger.info(f"[bold green][OK][/bold green] Found {len(lead['emails'])} email(s) on [bold]{lead['business_name']}[/bold]")
            except Exception as e:
                logger.error(f"[bold red][FAIL][/bold red] Error scraping {url}: {e}")
            progress.update(task, advance=1, description=f"[cyan]Scraped {i}/{len(urls)}...[/cyan]")
            
    logger.info(f"Scraping complete: {len(leads)} leads with emails")
    return leads


def run_verify(leads: list[dict], config: dict) -> list[dict]:
    """Stage 3: Verify scraped emails."""
    verification_config = config.get("verification", {})
    if not verification_config.get("enabled", True):
        logger.info("═══ VERIFY: disabled in config, skipping ═══")
        for lead in leads:
            lead["verified_emails"] = lead.get("emails", [])
            lead["verification_status"] = "unverified"
        return leads

    logger.info(f"═══ VERIFY: checking emails for {len(leads)} leads ═══")
    
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[yellow]Verifying SMTP...", total=len(leads))
        
        for i, lead in enumerate(leads, 1):
            emails = lead.get("emails", [])
            if not emails:
                lead["verified_emails"] = []
                lead["verification_status"] = "invalid"
                progress.update(task, advance=1, description=f"[yellow]Verified {i}/{len(leads)}...[/yellow]")
                continue

            try:
                results = verify_emails(emails, config)
                valid = [r["email"] for r in results if r["status"] in ("valid", "catch_all")]
                invalid = [r["email"] for r in results if r["status"] == "invalid"]
                unverified = [r["email"] for r in results if r["status"] == "unverified"]

                if valid:
                    first_valid_result = next(r for r in results if r["status"] in ("valid", "catch_all"))
                    lead["verification_status"] = first_valid_result["status"]
                elif unverified:
                    lead["verification_status"] = "unverified"
                else:
                    lead["verification_status"] = "invalid"

                lead["verified_emails"] = valid
                
                if valid:
                    logger.info(f"[bold green][OK][/bold green] Validated {len(valid)} email(s) for [bold]{lead.get('business_name', 'Unknown')}[/bold]")
            except Exception as e:
                logger.error(f"[bold red][FAIL][/bold red] Verification error: {e}")
                lead["verified_emails"] = []
                lead["verification_status"] = "unverified"
                
            progress.update(task, advance=1, description=f"[yellow]Verified {i}/{len(leads)}...[/yellow]")

    verified_count = sum(1 for l in leads if l.get("verified_emails"))
    logger.info(f"Verification complete: {verified_count}/{len(leads)} leads have verified emails")
    return leads


def run_store(leads: list[dict], country: str) -> dict:
    """Stage 4: Store leads in SQLite (dedup by domain)."""
    logger.info(f"═══ STORE: saving {len(leads)} leads ═══")
    stats = {"new": 0, "duplicate": 0}

    for lead in leads:
        emails_str = ", ".join(lead.get("emails", []))
        verified_str = ", ".join(lead.get("verified_emails", []))
        verification_status = lead.get("verification_status", "unverified")

        added = storage.add_lead(
            business_name=lead.get("business_name", ""),
            website=lead.get("website", ""),
            emails=emails_str,
            phone=lead.get("phone"),
            country=country,
            verified_emails=verified_str,
            verification_status=verification_status,
        )
        if added:
            stats["new"] += 1
        else:
            stats["duplicate"] += 1

    logger.info(f"Storage complete: {stats['new']} new, {stats['duplicate']} duplicates skipped")
    return stats


def run_screenshot(leads: list[dict], config: dict):
    """Stage 5: Capture screenshots (optional)."""
    screenshots_config = config.get("screenshots", {})
    if not screenshots_config.get("enabled", False):
        logger.info("═══ SCREENSHOTS: disabled in config, skipping ═══")
        return

    logger.info(f"═══ SCREENSHOTS: capturing {len(leads)} sites ═══")
    try:
        from src.screenshotter import capture_screenshot
    except ImportError as e:
        logger.warning(f"Playwright not available, skipping screenshots: {e}")
        return

    for i, lead in enumerate(leads, 1):
        url = lead.get("website", "")
        logger.info(f"[{i}/{len(leads)}] Screenshotting {url}")
        try:
            path = capture_screenshot(url)
            if path:
                logger.info(f"  ✓ Saved: {path}")
            else:
                logger.info(f"  ✗ Screenshot failed")
        except Exception as e:
            logger.error(f"  ✗ Screenshot error for {url}: {e}")


def run_notify(leads: list[dict], config: dict):
    """Stage 6: Send Telegram notifications for new leads."""
    telegram_config = config.get("telegram", {})
    if not telegram_config.get("enabled", False):
        logger.info("═══ NOTIFY: Telegram disabled in config, skipping ═══")
        return

    logger.info(f"═══ NOTIFY: sending Telegram alerts for {len(leads)} leads ═══")
    for lead in leads:
        try:
            send_lead_notification(lead, config)
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")


def run_email(niche: str, config: dict, dry_run: bool = False) -> dict:
    """Stage 7: Send cold emails to verified leads."""
    email_config = config.get("email", {})
    if not email_config.get("enabled", False):
        logger.info("═══ EMAIL: disabled in config (email.enabled: false), skipping ═══")
        return {"sent": 0, "failed": 0, "skipped": 0, "cap_reached": False}

    accounts = email_config.get("accounts", [])
    if not accounts:
        # Fallback for old config
        account = {
            "smtp_host": email_config.get("smtp_host"),
            "smtp_port": email_config.get("smtp_port"),
            "smtp_user": email_config.get("smtp_user"),
            "smtp_password": email_config.get("smtp_password"),
            "sender_name": email_config.get("sender_name"),
            "sender_email": email_config.get("sender_email")
        }
    else:
        # Randomly select an account from the fleet
        import random
        account = random.choice(accounts)
        logger.info(f"═══ EMAIL: Selected fleet account {account.get('sender_email')} ═══")
        
    sender_email = account.get("sender_email", "default")

    if dry_run:
        logger.info("═══ EMAIL: dry-run mode — no emails will be sent ═══")
        unsent = storage.get_unsent_leads(sender_email)
        logger.info(f"  Would send to {len(unsent)} leads (dry-run)")
        return {"sent": 0, "failed": 0, "skipped": len(unsent), "cap_reached": False}

    unsent = storage.get_unsent_leads(sender_email)
    if not unsent:
        logger.info("═══ EMAIL: no unsent leads with verified emails for this sender ═══")
        return {"sent": 0, "failed": 0, "skipped": 0, "cap_reached": False}

    logger.info(f"═══ EMAIL: sending to {len(unsent)} verified leads ═══")
    
    # Inject the selected account into the config for the mailer
    config_for_mailer = config.copy()
    config_for_mailer["email"]["current_account"] = account
    
    stats = send_batch(unsent, niche, config_for_mailer, storage)
    logger.info(f"Email complete: {stats.get('sent', 0)} sent, {stats.get('failed', 0)} failed")
    return stats


def run_reverify(config: dict):
    """Re-verify all unverified emails in the DB."""
    logger.info("═══ RE-VERIFY: checking unverified emails in DB ═══")
    unverified = storage.get_unverified_leads()
    if not unverified:
        logger.info("No unverified leads to re-check")
        return

    logger.info(f"Found {len(unverified)} leads with unverified emails")
    for i, lead in enumerate(unverified, 1):
        emails_str = lead.get("emails", "")
        if not emails_str:
            continue
        emails = [e.strip() for e in emails_str.split(",") if e.strip()]
        logger.info(f"[{i}/{len(unverified)}] Re-verifying {lead.get('business_name', 'Unknown')}")

        try:
            results = verify_emails(emails, config)
            valid = [r["email"] for r in results if r["status"] in ("valid", "catch_all")]

            if valid:
                first_valid = next(r for r in results if r["status"] in ("valid", "catch_all"))
                status = first_valid["status"]
            elif any(r["status"] == "unverified" for r in results):
                status = "unverified"
            else:
                status = "invalid"

            storage.update_verification(
                website=lead["website"],
                verified_emails=", ".join(valid),
                verification_status=status,
            )
            logger.info(f"  → {status}: {len(valid)} valid email(s)")
        except Exception as e:
            logger.error(f"  ✗ Re-verification error: {e}")


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="B2B Lead Finder — find business leads, verify emails, send cold outreach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --niche "dental clinics" --location "Casablanca" --country ma --max 20
  python main.py --niche "law firms" --location "Rabat" --dry-run
  python main.py --search-only --niche "restaurants" --location "Marrakech"
  python main.py --email-only
  python main.py --verify-only
        """,
    )
    parser.add_argument("--niche", type=str, help="Business niche to search for")
    parser.add_argument("--location", type=str, help="Location/city to search in")
    parser.add_argument("--country", type=str, default="", help="Country code (e.g. 'ma', 'us')")
    parser.add_argument("--max", type=int, default=25, dest="max_results", help="Max results per search query (default: 25)")
    parser.add_argument("--search-only", action="store_true", help="Only search + scrape, don't email")
    parser.add_argument("--email-only", action="store_true", help="Only send emails to unsent leads in DB")
    parser.add_argument("--verify-only", action="store_true", help="Re-verify unverified emails in DB")
    parser.add_argument("--dry-run", action="store_true", help="Scrape + log, never actually send email")
    parser.add_argument("--random-cities", type=int, help="Randomly select N cities from config")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    return parser.parse_args()


def main():
    setup_logging()
    args = parse_args()
    config = load_config(args.config)

    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║       B2B Lead Finder — Starting Run         ║")
    logger.info("╚══════════════════════════════════════════════╝")

    # Initialize database
    storage.init_db()

    # ── Verify-only mode ──
    if args.verify_only:
        run_reverify(config)
        storage.export_csv()
        logger.info("Re-verification complete.")
        return

    # ── Email-only mode ──
    if args.email_only:
        niche = (config.get("search", {}).get("niches", [""])[0])
        email_stats = run_email(niche, config, dry_run=args.dry_run)
        storage.export_csv()

        summary_stats = {
            "found": 0,
            "verified": 0,
            "invalid": 0,
            "emailed": email_stats.get("sent", 0),
            "failed": email_stats.get("failed", 0),
            "skipped": email_stats.get("skipped", 0),
        }
        send_summary(summary_stats, config)
        logger.info("Email-only run complete.")
        return

    # ── Full / Search-only pipeline ──
    # Determine niches and locations
    niches = [args.niche] if args.niche else config.get("search", {}).get("niches", [])
    locations = [args.location] if args.location else config.get("search", {}).get("locations", [])
    max_results = args.max_results or config.get("search", {}).get("max_results_per_query", 25)
    country = args.country

    if args.random_cities and len(locations) > args.random_cities:
        import random
        locations = random.sample(locations, args.random_cities)
        logger.info(f"Randomly selected {args.random_cities} cities for this run.")

    if not niches or not locations:
        logger.error("No niches or locations specified. Use --niche and --location flags, or set them in config.yaml")
        sys.exit(1)

    # Aggregate stats across all niche+location combos
    total_stats = {
        "found": 0,
        "verified": 0,
        "invalid": 0,
        "emailed": 0,
        "failed": 0,
        "skipped": 0,
    }

    all_leads = []

    for niche in niches:
        for location in locations:
            logger.info(f"\n{'─' * 50}")
            logger.info(f"Processing: {niche} × {location}")
            logger.info(f"{'─' * 50}")

            # Stage 1: Search
            urls = run_search(niche, location, max_results, config)
            if not urls:
                logger.warning(f"No URLs found for '{niche}' in '{location}', moving on")
                continue

            # Stage 2: Scrape
            leads = run_scrape(urls, config)
            if not leads:
                logger.warning(f"No leads scraped for '{niche}' in '{location}', moving on")
                continue

            # Stage 3: Verify emails
            leads = run_verify(leads, config)

            # Stage 4: Store in DB
            store_stats = run_store(leads, country)

            # Stage 5: Screenshots
            if not args.search_only:
                run_screenshot(leads, config)

            # Stage 6: Telegram notifications
            new_leads = [l for l in leads if l.get("verified_emails")]
            run_notify(new_leads, config)

            # Update totals
            total_stats["found"] += len(leads)
            total_stats["verified"] += sum(1 for l in leads if l.get("verification_status") in ("valid", "catch_all"))
            total_stats["invalid"] += sum(1 for l in leads if l.get("verification_status") == "invalid")

            all_leads.extend(leads)
            
            # Live save to CSV after every location finishes
            storage.export_csv()
            # Also save to a city-specific CSV
            current_city_websites = [l.get("website") for l in leads if l.get("website")]
            if current_city_websites:
                storage.export_csv_for_batch(current_city_websites, location)
            logger.info(f"Live saved results to CSV after {location}.")

    # Stage 7: Send emails (unless search-only or dry-run)
    if not args.search_only:
        niche_for_email = niches[0] if niches else ""
        email_stats = run_email(niche_for_email, config, dry_run=args.dry_run)
        total_stats["emailed"] = email_stats.get("sent", 0)
        total_stats["failed"] = email_stats.get("failed", 0)
        total_stats["skipped"] = email_stats.get("skipped", 0)

    # Final summary using Rich Table
    from rich.console import Console
    from rich.table import Table
    console = Console()
    table = Table(title="B2B Lead Finder - Run Summary", style="cyan")
    table.add_column("Metric", style="white")
    table.add_column("Count", justify="right", style="bold green")

    table.add_row("[*] Found", str(total_stats['found']))
    table.add_row("[+] Verified", str(total_stats['verified']))
    table.add_row("[-] Invalid", str(total_stats['invalid']))
    table.add_row("[@] Emailed", str(total_stats['emailed']))
    table.add_row("[!] Failed", str(total_stats['failed']))
    table.add_row("[>] Skipped", str(total_stats['skipped']))
    
    console.print(table)

    # Telegram summary
    send_summary(total_stats, config)

    if args.dry_run:
        logger.info("🏁 Dry-run complete — no emails were sent.")
    else:
        logger.info("🏁 Run complete.")


if __name__ == "__main__":
    main()
