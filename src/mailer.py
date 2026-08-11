import os
import smtplib
import random
import time
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import urllib.request
import urllib.error
from src.logger import get_logger
from src.email_templates import get_random_subject, get_random_template

logger = get_logger(__name__)

def strip_tags(html: str) -> str:
    """Basic HTML tag stripping for text fallback."""
    return re.sub('<[^<]+>', '', html)

def rewrite_email_with_openrouter(html_content: str, api_key: str, model: str = "nvidia/nemotron-3-super-120b-a12b:free") -> str:
    """Uses OpenRouter to slightly spin/rewrite the HTML email to ensure uniqueness."""
    if not api_key:
        return html_content
    
    logger.info("Calling OpenRouter to generate a unique email variant...")
    system_prompt = (
        "You are an expert copywriter. Your task is to slightly rewrite the provided HTML email "
        "to ensure it is unique, avoiding spam filters. "
        "CRITICAL RULES:\n"
        "1. DO NOT change the HTML structure, layout, or CSS classes.\n"
        "2. DO NOT change any links (href).\n"
        "3. Only rewrite the actual text (sentences, phrasing, greetings).\n"
        "4. Keep the same core message, pricing (€25), and features.\n"
        "5. Output ONLY the raw rewritten HTML code, starting with <!DOCTYPE html>. No markdown formatting, no explanations."
    )
    
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": html_content}
        ]
    }
    
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/leadfinder",
            "X-Title": "B2B Lead Finder",
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"].strip()
            # Remove markdown code fences if present
            if content.startswith("```html"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return content.strip()
    except Exception as e:
        logger.error(f"OpenRouter rewrite failed, falling back to base template: {e}")
        return html_content

def send_email(lead: dict, niche: str, config: dict) -> bool:
    """
    Sends an email to the lead's first verified email.
    
    Args:
        lead: Dictionary with 'business_name', 'website', 'verified_emails'.
        niche: The niche to replace in the template.
        config: Configuration dictionary.
        
    Returns:
        True on success, False on failure.
    """
    email_config = config.get('email', {})
    if not email_config.get('enabled', False):
        logger.info(f"Email sending disabled. Skipping {lead.get('business_name')}.")
        return True
        
    verified_emails = lead.get('verified_emails', '')
    if not verified_emails:
        logger.warning(f"No verified emails for {lead.get('business_name')}. Cannot send email.")
        return False
        
    # Get first email
    to_email = verified_emails.split(',')[0].strip()
    if not to_email:
        logger.warning(f"Parsed empty email for {lead.get('business_name')}. Cannot send.")
        return False

    smtp_host = email_config.get('smtp_host')
    smtp_port = email_config.get('smtp_port')
    smtp_user = email_config.get('smtp_user')
    smtp_password = email_config.get('smtp_password')
    template_path = email_config.get('template_path')
    sender_name = email_config.get('sender_name', 'Lead Bot')
    sender_email = email_config.get('sender_email', smtp_user)
    
    if not all([smtp_host, smtp_port, smtp_user, smtp_password, template_path]):
        logger.error("Incomplete email configuration.")
        return False

    business_name = lead.get('business_name', 'Business Owner')
    website = lead.get('website', '')
    
    try:
        # Load template from file if available, else fallback
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_html = f.read()
        except Exception:
            template_html = get_random_template()
            
        subject = get_random_subject(business_name, niche)
        
        # Replace placeholders in HTML
        html_content = template_html.replace('{{business_name}}', business_name)
        html_content = html_content.replace('{{niche}}', niche)
        html_content = html_content.replace('{{sender_name}}', sender_name)
        html_content = html_content.replace('{{website}}', website)
        
        # Spin with OpenRouter if configured
        openrouter_key = email_config.get('openrouter_api_key')
        openrouter_model = email_config.get('openrouter_model', 'google/gemma-2-9b-it:free')
        if openrouter_key:
            html_content = rewrite_email_with_openrouter(html_content, openrouter_key, openrouter_model)
        
        text_content = strip_tags(html_content)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        # Use the registered sender email for Brevo (not the SMTP login handle)
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = to_email

        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        msg.attach(part1)
        msg.attach(part2)

        server = None
        try:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
            logger.info(f"Successfully sent email to {to_email}")
            return True
        except Exception as e:
            logger.error(f"SMTP error while sending email to {to_email}: {e}")
            return False
        finally:
            if server:
                try:
                    server.quit()
                except:
                    pass
    except Exception as e:
        logger.error(f"Error preparing or sending email for {business_name}: {e}")
        return False

def send_batch(leads: list[dict], niche: str, config: dict, db_module) -> dict:
    """
    Sends emails to multiple leads respecting the daily cap.
    
    Args:
        leads: List of lead dictionaries.
        niche: Niche for template.
        config: Configuration dictionary.
        db_module: Database module to interact with send counts.
        
    Returns:
        A dictionary with statistics: sent, failed, skipped, cap_reached.
    """
    stats = {'sent': 0, 'failed': 0, 'skipped': 0, 'cap_reached': False}
    email_config = config.get('email', {})
    
    if not email_config.get('enabled', False):
        logger.info("Email sending disabled for batch.")
        stats['skipped'] = len(leads)
        return stats

    daily_cap = email_config.get('daily_send_cap', 50)
    min_delay = email_config.get('min_delay_seconds', 30)
    max_delay = email_config.get('max_delay_seconds', 120)

    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        task = progress.add_task("[magenta]Sending emails...", total=len(leads))
        
        for i, lead in enumerate(leads):
            try:
                current_count = db_module.get_today_send_count()
                if current_count >= daily_cap:
                    logger.info(f"Daily send cap ({daily_cap}) reached.")
                    stats['cap_reached'] = True
                    stats['skipped'] += (len(leads) - i)
                    break
                    
                success = send_email(lead, niche, config)
                if success:
                    db_module.mark_emailed(lead.get('website', ''))
                    db_module.increment_send_count()
                    stats['sent'] += 1
                else:
                    db_module.mark_failed(lead.get('website', ''))
                    stats['failed'] += 1
                    
                progress.update(task, advance=1, description=f"[magenta]Sent {i}/{len(leads)}...[/magenta]")
                
                # Delay between sends if there are more to process
                if i < len(leads) - 1 and not stats.get('cap_reached', False):
                    delay = random.uniform(min_delay, max_delay)
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"[bold red][FAIL][/bold red] Unexpected error in batch send for lead {lead.get('business_name')}: {e}")
                stats['failed'] += 1
                if hasattr(db_module, 'mark_failed'):
                    try:
                        db_module.mark_failed(lead.get('website', ''))
                    except:
                        pass
                progress.update(task, advance=1)

    return stats
