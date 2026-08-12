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
        logger.debug(f"DDGS returned {len(urls)} raw results")
        return urls
    except Exception as e:
        logger.warning(f"DDGS search failed: {e}")
        return []

def _search_google_library(query: str, max_results: int) -> list[str]:
    """Search using googlesearch-python (deep pagination)."""
    try:
        from googlesearch import search
        urls = list(search(query, num_results=max_results * 3, sleep_interval=1))
        logger.debug(f"Google Search Library returned {len(urls)} raw results")
        return urls
    except ImportError:
        logger.warning("googlesearch-python not installed. Use 'pip install googlesearch-python'")
        return []
    except Exception as e:
        logger.warning(f"Google Search Library failed: {e}")
        return []


def _search_bing_html(query: str, max_results: int) -> list[str]:
    """Fallback: scrape Bing HTML search results with pagination."""
    try:
        import requests
        from bs4 import BeautifulSoup
        import time

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        urls = []
        for first in range(1, max_results + 10, 10):
            url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}&first={first}"
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200:
                break
                
            soup = BeautifulSoup(res.text, "html.parser")
            page_urls = []
            
            for selector in ["li.b_algo h2 a", ".b_algo a", "h2 a[href^='http']"]:
                items = soup.select(selector)
                if items:
                    page_urls = [a["href"] for a in items if a.get("href", "").startswith("http")]
                    break

            if not page_urls:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                        page_urls.append(href)
                        
            if not page_urls:
                break
                
            urls.extend(page_urls)
            time.sleep(random.uniform(0.5, 1.5))
            
            if len(urls) >= max_results * 2:
                break

        logger.debug(f"Bing HTML returned {len(urls)} raw results across pages")
        return urls
    except Exception as e:
        logger.warning(f"Bing HTML search failed: {e}")
        return []

def _search_yahoo_html(query: str, max_results: int) -> list[str]:
    """Fallback: scrape Yahoo HTML search results with pagination."""
    try:
        import requests
        from bs4 import BeautifulSoup
        import time

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        urls = []
        for b in range(1, max_results + 10, 10):
            url = f"https://search.yahoo.com/search?p={urllib.parse.quote_plus(query)}&b={b}"
            res = requests.get(url, headers=headers, timeout=15)
            if res.status_code != 200:
                break
                
            soup = BeautifulSoup(res.text, "html.parser")
            page_urls = []
            
            for a in soup.find_all("a", class_="ac-algo", href=True):
                href = a["href"]
                if href.startswith("http") and "yahoo.com" not in href:
                    page_urls.append(href)
                        
            if not page_urls:
                break
                
            urls.extend(page_urls)
            time.sleep(random.uniform(0.5, 1.5))
            
            if len(urls) >= max_results * 2:
                break

        logger.debug(f"Yahoo HTML returned {len(urls)} raw results across pages")
        return urls
    except Exception as e:
        logger.warning(f"Yahoo HTML search failed: {e}")
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

        logger.debug(f"DDG HTML returned {len(urls)} raw results")
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
                
        logger.debug(f"Yellow Pages returned {len(urls)} raw business websites")
        return urls[:max_results * 2]
    except Exception as e:
        logger.warning(f"Yellow Pages search failed: {e}")
        return []


def search_leads(niche: str, location: str, max_results: int = 25, config: dict = None) -> list[str]:
    """
    Search for business URLs using DuckDuckGo API, with HTML fallbacks.
    Uses multiple query variations to maximize results.
    """
    config = config or {}
    scraping_config = config.get("scraping", {})
    min_delay = scraping_config.get("min_delay_seconds", 1.5)
    max_delay = scraping_config.get("max_delay_seconds", 3.5)

    queries = [
        f"{niche} {location}",
        f"{niche} in {location}",
        f"best {niche} {location}",
        f"{location} {niche} companies",
        f"top {niche} agencies {location}",
        f"local {niche} in {location}",
        f"{niche} services {location}",
        f"professional {niche} {location}",
        f"award winning {niche} {location}",
        f"{location} {niche} experts"
    ]
    
    seen_domains = set()
    results = []

    for query in queries:
        if len(results) >= max_results:
            break
            
        logger.debug(f"Searching leads for query: '{query}'")
        time.sleep(random.uniform(min_delay, max_delay))

        # Strategy 1: ddgs library
        raw_urls = _search_ddgs(query, max_results)

        # Strategy 2: DuckDuckGo HTML fallback
        if len(raw_urls) < max_results:
            logger.debug(f"DDGS only got {len(raw_urls)}, stacking DDG HTML...")
            time.sleep(random.uniform(min_delay, max_delay))
            raw_urls.extend(_search_ddg_html(query))

        # Strategy 3: Bing HTML fallback (Paginated)
        if len(raw_urls) < max_results:
            logger.debug(f"Still need more ({len(raw_urls)}), stacking Bing...")
            time.sleep(random.uniform(min_delay, max_delay))
            raw_urls.extend(_search_bing_html(query, max_results))

        # Strategy 4: Yahoo HTML fallback (Paginated)
        if len(raw_urls) < max_results:
            logger.debug(f"Still need more ({len(raw_urls)}), stacking Yahoo...")
            time.sleep(random.uniform(min_delay, max_delay))
            raw_urls.extend(_search_yahoo_html(query, max_results))

        # Deduplicate and filter
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

    logger.debug(f"Found {len(results)} unique business URLs for '{niche}' in '{location}'")
    return results
