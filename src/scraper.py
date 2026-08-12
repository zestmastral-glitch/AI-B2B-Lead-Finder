import random
import re
import time
import urllib.parse
import urllib.robotparser
import requests
from bs4 import BeautifulSoup
from src.logger import get_logger
from src.searcher import USER_AGENTS

logger = get_logger(__name__)

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'(?:(?:\+?1\s*(?:[.-]\s*)?)?(?:\(\s*([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9])\s*\)|([2-9]1[02-9]|[2-9][02-8]1|[2-9][02-8][02-9]))\s*(?:[.-]\s*)?)?([2-9]1[02-9]|[2-9][02-9]1|[2-9][02-9]{2})\s*(?:[.-]\s*)?([0-9]{4})(?:\s*(?:#|x\.?|ext\.?|extension)\s*(\d+))?|\+212\s*[567]\d\s*\d{2}\s*\d{2}\s*\d{2}|0[567]\d{8}')
JUNK_EMAILS = [
    'example.com', 'sentry.io', 'wixpress', 'wordpress', 'squarespace', 
    '@2x', '.png', '.jpg', '.js', '.css'
]

def clean_business_name(name: str) -> str:
    """Clean common suffixes from business names."""
    suffixes = [" | Home", " - Welcome", " | Official Site", " - Home"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def extract_emails_from_text(text: str) -> set[str]:
    """Extract and filter emails from text."""
    found = set()
    if not text:
        return found
    matches = EMAIL_REGEX.findall(text)
    for email in matches:
        email = email.lower()
        if not any(junk in email for junk in JUNK_EMAILS):
            found.add(email)
    return found

def check_robots_txt(url: str, user_agent: str) -> bool:
    """Check if scraping is allowed by robots.txt."""
    try:
        parsed = urllib.parse.urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        # Use requests with a strict timeout so the scraper never gets stuck
        res = requests.get(robots_url, headers={"User-Agent": user_agent}, timeout=5)
        
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        
        if res.status_code == 200:
            lines = res.text.splitlines()
            rp.parse(lines)
            return rp.can_fetch(user_agent, url)
        else:
            return True # Allowed if no robots.txt exists
            
    except Exception as e:
        logger.debug(f"Error checking robots.txt for {url}: {e}")
        return True # Default to allowed on error

def scrape_lead(url: str, config: dict = None) -> dict | None:
    """
    Scrape a business website for contact info.
    Returns dict or None if no email is found or if scraping fails.
    """
    config = config or {}
    scraping_config = config.get("scraping", {})
    min_delay = scraping_config.get("min_delay_seconds", 1.5)
    max_delay = scraping_config.get("max_delay_seconds", 3.5)
    timeout = scraping_config.get("timeout_seconds", 10)
    
    logger.info(f"Scraping lead: {url}")
    
    user_agent = random.choice(USER_AGENTS)
    headers = {"User-Agent": user_agent}
    
    # Check robots.txt
    if not check_robots_txt(url, user_agent):
        logger.warning(f"Scraping disallowed by robots.txt for {url}")
        return None

    time.sleep(random.uniform(min_delay, max_delay))
    
    try:
        res = requests.get(url, headers=headers, timeout=timeout)
        res.raise_for_status()
        html = res.text
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None
        
    emails = extract_emails_from_text(html)
    
    # Find contact pages
    contact_keywords = ['contact', 'about', 'about-us', 'kontakt', 'contacto']
    contact_links = []
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").lower()
        if any(kw in href for kw in contact_keywords):
            # Resolve relative URLs
            contact_links.append(urllib.parse.urljoin(url, link["href"]))
            
    # Deduplicate and limit to 2 pages to avoid long scraping
    contact_links = list(set(contact_links))[:2]
    
    for contact_link in contact_links:
        time.sleep(random.uniform(min_delay, max_delay))
        try:
            c_res = requests.get(contact_link, headers=headers, timeout=timeout)
            if c_res.status_code == 200:
                emails.update(extract_emails_from_text(c_res.text))
        except Exception as e:
            logger.debug(f"Failed to fetch contact page {contact_link}: {e}")

    if not emails:
        logger.info(f"No valid emails found on {url}")
        return None
        
    # Extract Business Name
    business_name = None
    og_site_name = soup.find("meta", property="og:site_name")
    if og_site_name and og_site_name.get("content"):
        business_name = og_site_name["content"]
    elif soup.title and soup.title.string:
        business_name = soup.title.string
    else:
        parsed = urllib.parse.urlparse(url)
        business_name = parsed.netloc.replace("www.", "")
        
    business_name = clean_business_name(business_name)

    # Extract Phone
    phone = None
    text_content = soup.get_text(separator=' ')
    phone_match = PHONE_REGEX.search(text_content)
    if phone_match:
        phone = phone_match.group(0).strip()
        
    # Extract About Snippet
    about_snippet = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        about_snippet = meta_desc["content"]
    else:
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if 50 < len(text) < 500:
                about_snippet = text
                break
                
    result = {
        "business_name": business_name,
        "emails": list(emails),
        "phone": phone,
        "about_snippet": about_snippet
    }
    logger.info(f"Successfully scraped data for {url}: {len(result['emails'])} emails found")
    return result
