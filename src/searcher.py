import random
import time
import urllib.parse
from src.logger import get_logger

logger = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

EXCLUDED_DOMAINS = {
    "facebook.com", "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "youtube.com", "yelp.com", "yellowpages.com", "tripadvisor.com",
    "bbb.org", "mapquest.com", "foursquare.com", "pinterest.com", "reddit.com",
    "wikipedia.org", "amazon.com", "ebay.com", "craigslist.org", "nextdoor.com",
    "angi.com", "thumbtack.com", "groupon.com", "google.com", "bing.com",
    # Directory / aggregator sites (we want the business's OWN website)
    "goodfirms.co", "designrush.com", "topdevelopers.co", "expertise.com",
    "clutch.co", "sortlist.com", "bark.com", "upwork.com", "fiverr.com",
    "glassdoor.com", "indeed.com", "trustpilot.com", "g2.com", "capterra.com",
    "insidea.com", "agencyspotter.com", "upcity.com", "digitalagencynetwork.com",
    "themanifest.com", "agency-list.com", "ontoplist.com", "influencermarketinghub.com",
    "thesocialshepherd.com", "upandup.agency", "webfx.com", "ignitevisibility.com",
    "disruptiveadvertising.com", "thriveagency.com", "smartinsights.com",
    "hubspot.com", "neilpatel.com", "marketingblink.com", "yellowbook.com",
}


def _extract_root_domain(url: str) -> str | None:
    """Extract and normalize root domain from a URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return None


def _is_excluded(domain: str) -> bool:
    """Check if domain or any parent domain is in the exclusion list."""
    return any(domain == ed or domain.endswith("." + ed) for ed in EXCLUDED_DOMAINS)


def _search_ddgs(query: str, max_results: int) -> list[str]:
    """Search using the ddgs library (DuckDuckGo API wrapper)."""
    try:
        from ddgs import DDGS
        # Over-fetch by 5x to allow aggressive filtering of directories
        results = DDGS().text(query, max_results=max_results * 5)
        urls = [r["href"] for r in results if "href" in r]
        logger.info(f"DDGS returned {len(urls)} raw results")
        return urls
    except Exception as e:
        logger.warning(f"DDGS search failed: {e}")
        return []


def _search_bing_html(query: str) -> list[str]:
    """Fallback: scrape Bing HTML search results."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
        }
        url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        urls = []
        # Try multiple selectors for Bing
        for selector in ["li.b_algo h2 a", ".b_algo a", "h2 a[href^='http']"]:
            items = soup.select(selector)
            if items:
                urls = [a["href"] for a in items if a.get("href", "").startswith("http")]
                break

        # Fallback: find all external links
        if not urls:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                    urls.append(href)

        logger.info(f"Bing HTML returned {len(urls)} raw results")
        return urls
    except Exception as e:
        logger.warning(f"Bing HTML search failed: {e}")
        return []


def _search_ddg_html(query: str) -> list[str]:
    """Fallback: scrape DuckDuckGo HTML search results."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        res = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers=headers,
            timeout=15,
        )
        soup = BeautifulSoup(res.text, "html.parser")

        urls = []
        # Try known selectors
        for link in soup.find_all("a", class_="result__a"):
            href = link.get("href", "")
            if href.startswith("http"):
                urls.append(href)

        # Try result snippets
        if not urls:
            for link in soup.find_all("a", class_="result__url"):
                href = link.get("href", "")
                if href.startswith("http"):
                    urls.append(href)

        logger.info(f"DDG HTML returned {len(urls)} raw results")
        return urls
    except Exception as e:
        logger.warning(f"DDG HTML search failed: {e}")
        return []

def _search_yellowpages(niche: str, location: str, max_results: int) -> list[str]:
    """Scrape business websites directly from Yellow Pages."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        url = f"https://www.yellowpages.com/search?search_terms={urllib.parse.quote_plus(niche)}&geo_location_terms={urllib.parse.quote_plus(location)}"
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        urls = []
        # Find all 'Website' buttons on the Yellow Pages cards
        for link in soup.find_all("a", class_="track-visit-website"):
            href = link.get("href", "")
            if href.startswith("http"):
                urls.append(href)
                
        logger.info(f"Yellow Pages returned {len(urls)} raw business websites")
        return urls[:max_results * 2]
    except Exception as e:
        logger.warning(f"Yellow Pages search failed: {e}")
        return []


def search_leads(niche: str, location: str, max_results: int = 25, config: dict = None) -> list[str]:
    """
    Search for business URLs using DuckDuckGo API, with HTML fallbacks.

    Args:
        niche: Business type to search for
        location: City/location to search in
        max_results: Maximum number of deduplicated URLs to return
        config: Configuration dict with scraping delay settings

    Returns:
        List of deduplicated root domain URLs (business websites only)
    """
    config = config or {}
    scraping_config = config.get("scraping", {})
    min_delay = scraping_config.get("min_delay_seconds", 1.5)
    max_delay = scraping_config.get("max_delay_seconds", 3.5)

    query = f"{niche} {location}"
    logger.info(f"Searching leads for query: '{query}'")

    # Small delay before searching
    time.sleep(random.uniform(min_delay, max_delay))

    # Strategy 1: Yellow Pages (Directly scrapes business websites)
    raw_urls = _search_yellowpages(niche, location, max_results)
    
    # Strategy 2: ddgs library (most reliable web search fallback)
    if not raw_urls:
        logger.info("Yellow Pages returned 0 results, trying DDGS fallback")
        time.sleep(random.uniform(min_delay, max_delay))
        raw_urls = _search_ddgs(query, max_results)

    # Strategy 3: DuckDuckGo HTML fallback
    if not raw_urls:
        logger.info("DDGS returned 0 results, trying DDG HTML fallback")
        time.sleep(random.uniform(min_delay, max_delay))
        raw_urls = _search_ddg_html(query)

    # Strategy 4: Bing HTML fallback
    if not raw_urls:
        logger.info("DDG HTML returned 0 results, trying Bing fallback")
        time.sleep(random.uniform(min_delay, max_delay))
        raw_urls = _search_bing_html(query)

    # Deduplicate and filter
    seen_domains = set()
    results = []

    for url in raw_urls:
        if not url.startswith("http"):
            if url.startswith("//"):
                url = "https:" + url
            else:
                continue

        domain = _extract_root_domain(url)
        if not domain:
            continue

        # Skip excluded domains
        if _is_excluded(domain):
            continue

        # Deduplicate by root domain
        if domain not in seen_domains:
            seen_domains.add(domain)
            parsed = urllib.parse.urlparse(url)
            results.append(f"{parsed.scheme}://{parsed.netloc}")
            if len(results) >= max_results:
                break

    logger.info(f"Found {len(results)} unique business URLs for '{query}'")
    return results
