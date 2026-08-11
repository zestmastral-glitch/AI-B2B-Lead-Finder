import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.logger import get_logger

logger = get_logger(__name__)

def capture_screenshot(url: str, output_dir: str = 'data/screenshots', timeout_ms: int = 10000) -> str | None:
    """
    Navigates to the given URL and captures a full-page screenshot.

    Args:
        url: The URL to capture.
        output_dir: The directory where the screenshot should be saved.
        timeout_ms: The timeout for navigation and capturing in milliseconds.

    Returns:
        The path to the saved PNG screenshot, or None if an error occurred.
    """
    logger.info(f"Attempting to capture screenshot for {url}")
    
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            logger.error(f"Failed to create output directory {output_dir}: {e}")
            return None

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc or parsed_url.path
        if not domain:
            domain = "unknown_domain"
            
        # Clean domain for filename
        domain = domain.replace("www.", "").replace(":", "_").replace("/", "_")
        output_path = os.path.join(output_dir, f"{domain}.png")

        with sync_playwright() as p:
            browser = None
            try:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=timeout_ms)
                page.screenshot(path=output_path, full_page=True, timeout=timeout_ms)
                logger.info(f"Successfully captured screenshot to {output_path}")
                return output_path
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout while capturing screenshot for {url}")
                return None
            except Exception as e:
                logger.warning(f"Failed to capture screenshot for {url}: {e}")
                return None
            finally:
                if browser:
                    browser.close()
    except Exception as e:
        logger.warning(f"Unexpected error in capture_screenshot for {url}: {e}")
        return None
