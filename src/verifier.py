import re
import random
import smtplib
import time
from collections import defaultdict
import dns.resolver
from src.logger import get_logger

logger = get_logger(__name__)

def verify_email(email: str, config: dict = None) -> dict:
    """
    Verifies an email address using a 5-layer verification system.
    Returns: {"email": str, "status": str, "mx_host": str|None, "response_code": int|None, "is_catch_all": bool}
    Status can be: "valid", "invalid", "unverified", "catch_all"
    """
    if config is None:
        config = {}

    result = {
        "email": email,
        "status": "unverified",
        "mx_host": None,
        "response_code": None,
        "is_catch_all": False
    }

    # Layer 1: Syntax Validation
    if not isinstance(email, str):
        result["status"] = "invalid"
        logger.debug(f"Invalid type for email: {email}")
        return result

    email = email.strip().lower()
    result["email"] = email
    
    # RFC 5322 regex approximation
    syntax_pattern = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    if not re.match(syntax_pattern, email) or '..' in email.split('@')[0] or email.startswith('.') or email.endswith('.'):
        result["status"] = "invalid"
        logger.debug(f"Syntax validation failed for email: {email}")
        return result

    domain = email.split('@')[1]

    # Layer 2: Domain Existence (DNS A/AAAA)
    try:
        dns.resolver.resolve(domain, 'A')
    except dns.resolver.NXDOMAIN:
        result["status"] = "invalid"
        logger.debug(f"Domain NXDOMAIN for email: {email}")
        return result
    except Exception as e:
        logger.warning(f"Domain existence check error for {email}: {e}")
        # transient error, proceed or mark unverified. The spec says "return status='unverified'" if timeout/error
        result["status"] = "unverified"
        return result

    # Layer 3: MX Record Check
    mx_hosts = []
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        # Sort by priority
        mx_records = sorted(answers, key=lambda r: r.preference)
        mx_hosts = [r.exchange.to_text().rstrip('.') for r in mx_records]
    except dns.resolver.NoAnswer:
        # Fall back to A record
        try:
            dns.resolver.resolve(domain, 'A')
            mx_hosts = [domain]
        except Exception:
            result["status"] = "invalid"
            logger.debug(f"No MX and no A record for domain: {domain}")
            return result
    except dns.resolver.NXDOMAIN:
        result["status"] = "invalid"
        logger.debug(f"NXDOMAIN during MX check for domain: {domain}")
        return result
    except Exception as e:
        logger.warning(f"MX record check error for {email}: {e}")
        result["status"] = "unverified"
        return result

    if not mx_hosts:
        result["status"] = "invalid"
        logger.debug(f"No MX hosts found for email: {email}")
        return result

    best_mx = mx_hosts[0]
    result["mx_host"] = best_mx

    # Layer 4: SMTP Mailbox Verification
    verification_config = config.get('verification', {})
    if verification_config.get('skip_smtp_check', False):
        result["status"] = "valid"  # Assuming valid if MX exists and skipping SMTP
        logger.debug(f"Skipping SMTP check for email: {email}")
        return result

    timeout_seconds = verification_config.get('timeout_seconds', 10)
    delay_seconds = verification_config.get('delay_seconds', 2)

    mailbox_valid = False
    
    for mx_server in mx_hosts:
        smtp = None
        try:
            smtp = smtplib.SMTP(timeout=timeout_seconds)
            smtp.connect(mx_server, 25)
            smtp.ehlo('verify.local')
            smtp.mail('verify@verify.local')
            
            code, msg = smtp.rcpt(email)
            result["response_code"] = code
            
            if code in (250, 251):
                mailbox_valid = True
                result["status"] = "valid"
                logger.debug(f"SMTP RCPT accepted for email: {email} on MX: {mx_server}")
                break  # Successful check
            elif code in (550, 551, 552, 553, 554):
                result["status"] = "invalid"
                logger.debug(f"SMTP RCPT rejected ({code}) for email: {email} on MX: {mx_server}")
                break  # Definitely invalid
            elif code in (421, 450, 451, 452):
                result["status"] = "unverified"
                logger.debug(f"SMTP greylisted ({code}) for email: {email} on MX: {mx_server}")
                break
            else:
                result["status"] = "unverified"
                logger.debug(f"SMTP unknown response ({code}) for email: {email} on MX: {mx_server}")
                break
                
        except Exception as e:
            logger.debug(f"SMTP connection failed to {mx_server} for {email}: {e}")
            continue  # Try next MX server
        finally:
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass

    if result["status"] == "unverified" and not mailbox_valid:
        # Either all connections failed, or greylisted
        return result

    if result["status"] == "invalid":
        return result

    # Layer 5: Catch-All Detection
    # Only run if Layer 4 returned a valid mailbox
    if mailbox_valid:
        random_test = f"xq7z9test{random.randint(10000, 99999)}@{domain}"
        smtp = None
        try:
            time.sleep(delay_seconds)  # Delay between checks on the same server
            smtp = smtplib.SMTP(timeout=timeout_seconds)
            smtp.connect(best_mx, 25)
            smtp.ehlo('verify.local')
            smtp.mail('verify@verify.local')
            
            code, msg = smtp.rcpt(random_test)
            
            if code == 250:
                result["status"] = "catch_all"
                result["is_catch_all"] = True
                logger.debug(f"Domain {domain} is catch-all (accepted {random_test})")
            elif code == 550:
                result["status"] = "valid"
                result["is_catch_all"] = False
                logger.debug(f"Domain {domain} is NOT catch-all (rejected {random_test})")
            
        except Exception as e:
            logger.warning(f"Catch-all check failed for domain {domain}: {e}")
            # Keep the valid status if catch-all check fails to connect
        finally:
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass

    return result

def verify_emails(email_list: list[str], config: dict = None) -> list[dict]:
    """
    Batch verification. Groups by domain to minimize connections.
    """
    if config is None:
        config = {}
        
    delay_seconds = config.get('verification', {}).get('delay_seconds', 2)

    # Group by domain
    domain_groups = defaultdict(list)
    for e in email_list:
        if '@' in e:
            domain = e.split('@')[-1].lower()
            domain_groups[domain].append(e)
        else:
            domain_groups['invalid'].append(e)

    results = []
    
    for domain, emails in domain_groups.items():
        if domain == 'invalid':
            for e in emails:
                results.append({
                    "email": e,
                    "status": "invalid",
                    "mx_host": None,
                    "response_code": None,
                    "is_catch_all": False
                })
            continue
            
        for i, email in enumerate(emails):
            if i > 0:
                time.sleep(delay_seconds)
            res = verify_email(email, config)
            results.append(res)
            
    return results

def filter_valid_emails(email_list: list[str], config: dict = None) -> list[str]:
    """
    Convenience: returns only emails with status "valid" or "catch_all".
    """
    results = verify_emails(email_list, config)
    valid_emails = [r["email"] for r in results if r["status"] in ("valid", "catch_all")]
    return valid_emails
