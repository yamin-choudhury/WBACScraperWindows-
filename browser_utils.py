"""
Browser utilities for interacting with web pages
"""
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import asyncio

class ValuationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

async def check_for_car_not_found(page):
    """
    Check for car not found error using multiple approaches to ensure detection
    even if the element is hidden.
    """
    # Method 1: Check for specific h1 element by class
    error_heading = await page.query_selector('h1.text-focus.ng-star-inserted')
    if error_heading:
        error_text = await page.evaluate('(element) => element.textContent', error_heading)
        if error_text and "sorry" in error_text.lower() and "find your car" in error_text.lower():
            return True
    
    # Method 2: Check entire page content for error message
    page_content = await page.content()
    if "sorry, we couldn't find your car" in page_content.lower():
        return True
    
    # Method 3: Use JavaScript to find hidden elements
    has_error = await page.evaluate('''
        () => {
            const errorHeadings = document.querySelectorAll('h1.text-focus');
            for (const heading of errorHeadings) {
                if (heading.textContent.toLowerCase().includes("sorry") && 
                    heading.textContent.toLowerCase().includes("find your car")) {
                    return true;
                }
            }
            const allElements = document.querySelectorAll('*');
            for (const element of allElements) {
                if (element.textContent.toLowerCase().includes("sorry, we couldn't find your car")) {
                    return true;
                }
            }
            return false;
        }
    ''')
    return has_error

async def setup_browser(playwright, use_proxy=False, config=None):
    """
    Set up and configure the browser with appropriate settings
    """
    from .config import BROWSER_SETTINGS, OX_PROXY, OX_USERNAME, OX_PASSWORD
    
    if not config:
        config = BROWSER_SETTINGS
    
    launch_options = {
        "headless": config.get("headless", False),
    }
    
    if use_proxy:
        launch_options["proxy"] = {
            "server": f"http://{OX_PROXY}",
            "username": OX_USERNAME,
            "password": OX_PASSWORD
        }
    
    browser = await playwright.chromium.launch(**launch_options)
    
    context = await browser.new_context(
        viewport=config.get("viewport", {'width': 1366, 'height': 768}),
        user_agent=config.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36")
    )
    
    await context.set_extra_http_headers({"Accept-Language": config.get("language", "en-GB,en;q=0.9")})
    
    return browser, context

async def setup_page(context, timeouts=None):
    """
    Create and set up a new page with monitoring and appropriate timeouts
    """
    from .config import DEFAULT_TIMEOUT, NAVIGATION_TIMEOUT
    
    if not timeouts:
        timeouts = {
            "default": DEFAULT_TIMEOUT,
            "navigation": NAVIGATION_TIMEOUT
        }
    
    page = await context.new_page()
    
    # Set timeouts
    page.set_default_timeout(timeouts.get("default", 15000))
    page.set_default_navigation_timeout(timeouts.get("navigation", 20000))
    
    # Initialize bandwidth tracking
    total_bytes = 0
    
    # Response monitoring for bandwidth tracking
    async def log_response(response):
        nonlocal total_bytes
        try:
            size = int(response.headers.get("content-length", 0))
            if size == 0 and response.status not in [301, 302, 303, 307, 308]:
                try:
                    body = await response.body()
                    size = len(body)
                except Exception:
                    pass
            total_bytes += size
        except Exception:
            pass
    
    page.on("response", log_response)
    
    return page, total_bytes

def parse_valuation(valuation_text):
    """
    Extracts a numeric value from the valuation text.
    """
    import re
    cleaned_text = re.sub(r'[^\d.,]', '', valuation_text)
    cleaned_text = cleaned_text.replace(',', '')
    try:
        return float(cleaned_text)
    except ValueError:
        return None
