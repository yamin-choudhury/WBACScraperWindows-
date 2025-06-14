"""
Standalone Windows module for WBAC valuation using synchronous Playwright
Enhanced with better error handling and resource cleanup for retry scenarios
"""
import time
import random
import traceback
import re
import sys
import gc
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Import human behavior functions
from .human_behavior import generate_random_email, generate_random_postcode, generate_random_uk_phone
from .config import WBAC_URL

class WindowsValuationError(Exception):
    """Exception raised for errors in the Windows valuation process."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def _detect_car_not_found(page):
    """Check if the page indicates that the car was not found"""
    try:
        content = page.content().lower()
        not_found_phrases = [
            "sorry, we couldn't find your car",
            "couldn't find your registration",
            "we cannot value your car", 
            "couldn't find your car",
            "we can't buy this car",
            "unable to provide a valuation",
            "registration not found",
            "invalid registration"
        ]
        for phrase in not_found_phrases:
            if phrase in content:
                return True
        return False
    except Exception as e:
        print(f"Error checking for car not found: {e}")
        return False

def _cleanup_browser_resources(browser=None, context=None, page=None):
    """Safely cleanup browser resources"""
    cleanup_errors = []
    
    try:
        if page:
            page.close()
    except Exception as e:
        cleanup_errors.append(f"Page cleanup error: {e}")
    
    try:
        if context:
            context.close()
    except Exception as e:
        cleanup_errors.append(f"Context cleanup error: {e}")
    
    try:
        if browser:
            browser.close()
    except Exception as e:
        cleanup_errors.append(f"Browser cleanup error: {e}")
    
    # Force garbage collection
    try:
        gc.collect()
    except Exception as e:
        cleanup_errors.append(f"GC error: {e}")
    
    if cleanup_errors:
        print(f"Cleanup warnings: {'; '.join(cleanup_errors)}")

def get_valuation_windows(plate, mileage):
    """
    Windows-specific valuation function using synchronous Playwright.
    Enhanced with better error handling and resource cleanup for retry scenarios.
    Follows the exact working flow from the WBACv2 notebook.
    """
    print(f"Starting Windows valuation process for {plate} with mileage {mileage}")
    
    # Handle edge cases for mileage
    if mileage == 0 or mileage is None:
        mileage = 100000
    elif mileage < 1000 and mileage > 0:
        mileage = mileage * 1000
        print(f"Small mileage detected, converted to {mileage}")
    
    browser = None
    context = None
    page = None
    
    try:
        with sync_playwright() as p:
            # Launch browser in visible mode for debugging
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-extensions",
                    "--no-first-run",
                    "--disable-default-apps"
                ]
            )
            
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                locale="en-GB",
                timezone_id="Europe/London"
            )
            context.set_extra_http_headers({"Accept-Language": "en-GB,en;q=0.9"})
            
            page = context.new_page()
            page.set_default_timeout(15000)  # 15 seconds
            page.set_default_navigation_timeout(20000)  # 20 seconds
            
            # Navigate to homepage (not direct valuation page)
            print("Navigating to https://www.webuyanycar.com/")
            try:
                page.goto("https://www.webuyanycar.com/", wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                raise WindowsValuationError("Navigation timeout - network issue or site unavailable")
            
            time.sleep(0.3)
            
            # Handle cookies with better error handling
            print("Accepting cookies...")
            try:
                cookie_button = page.wait_for_selector("#onetrust-accept-btn-handler", timeout=5000)
                if cookie_button:
                    cookie_button.click()
                    time.sleep(0.2)
                else:
                    print("Cookie button not found - continuing anyway")
            except PlaywrightTimeoutError:
                print("Cookie acceptance timeout - continuing anyway")
            except Exception as e:
                print(f"Cookie handling error: {e} - continuing anyway")
            
            # Brief pause before proceeding
            time.sleep(0.5)
            
            # Early detection of car not found
            if _detect_car_not_found(page):
                print(f"Car not found (initial check): {plate}")
                return None
            
            # Enhanced page variation handling with better error recovery
            max_attempts = 3
            attempts = 0
            valuation_found = False
            
            while attempts < max_attempts and not valuation_found:
                attempts += 1
                print(f"Attempt {attempts}/{max_attempts} for {plate}")
                
                try:
                    if _detect_car_not_found(page):
                        print(f"Car not found (during page variation handling): {plate}")
                        return None
                    
                    # Try multiple selectors for registration and mileage fields
                    reg_field = page.query_selector("#vehicleReg, input[placeholder*='registration'], input[name*='reg']")
                    mileage_field = page.query_selector("#Mileage, input[placeholder*='mileage'], input[name*='mileage']")
                    
                    if reg_field and mileage_field:
                        print(f"Standard page with both fields detected for {plate}")
                        break
                    elif reg_field and not mileage_field:
                        print(f"Variant page with only reg field detected for {plate} (attempt {attempts})")
                        # Fill registration and try to proceed
                        reg_field.fill(plate)
                        time.sleep(random.uniform(0.5, 1.0))
                        
                        # Try different button selectors
                        button_clicked = False
                        for btn_selector in ['button:has-text("Get my car valuation")', 'button[type="submit"]']:
                            try:
                                button = page.query_selector(btn_selector)
                                if button:
                                    button.click()
                                    button_clicked = True
                                    print(f"Clicked {btn_selector} for {plate}")
                                    break
                            except Exception:
                                continue
                        
                        if not button_clicked:
                            # Try form submission
                            try:
                                page.evaluate('document.querySelector("form").submit()')
                                button_clicked = True
                                print(f"Submitted form for {plate}")
                            except Exception:
                                pass
                        
                        if not button_clicked:
                            print(f"Warning: Could not find button to click for {plate}")
                        
                        time.sleep(random.uniform(2, 4))
                    else:
                        print(f"Unexpected page state for {plate} - no reg field found")
                        page.screenshot(path=f"unexpected_page_{plate}.png")
                        page.reload()
                        time.sleep(random.uniform(1.5, 3.0))
                
                except Exception as e:
                    print(f"Attempt {attempts} failed: {e}")
                    if attempts < max_attempts:
                        print(f"Retrying in 2 seconds...")
                        time.sleep(2)
                        try:
                            # Try to refresh the page for retry
                            page.reload(wait_until="domcontentloaded")
                            time.sleep(1)
                        except Exception as reload_error:
                            print(f"Page reload failed: {reload_error}")
                    else:
                        raise WindowsValuationError(f"All {max_attempts} attempts failed: {str(e)}")
            
            if attempts >= max_attempts:
                print(f"Exceeded maximum attempts ({max_attempts}) for {plate}")
                return None
            
            if _detect_car_not_found(page):
                print(f"Car not found (before standard flow): {plate}")
                return None
            
            # Standard flow: Fill in registration and mileage
            print(f"Filling registration field with {plate}")
            reg_field.fill(plate)
            time.sleep(random.uniform(0.1, 0.3))
            
            print(f"Filling mileage field with {mileage}")
            mileage_field.fill(str(int(mileage)))
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click the "btn-go" button (from notebook)
            print("Clicking btn-go button")
            try:
                btn_go = page.query_selector("#btn-go")
                if btn_go:
                    btn_go.click()
                    print("Clicked #btn-go successfully")
                else:
                    print("Warning: #btn-go not found, trying alternatives")
                    # Try alternative selectors
                    for selector in ['button[type="submit"]', 'input[type="submit"]']:
                        alt_btn = page.query_selector(selector)
                        if alt_btn:
                            alt_btn.click()
                            print(f"Clicked alternative button: {selector}")
                            break
            except Exception as e:
                print(f"Error clicking btn-go: {e}")
                return None
            
            time.sleep(random.uniform(2, 4))
            
            if _detect_car_not_found(page):
                print(f"Car not found after form submission: {plate}")
                return None
            
            # Fill out the contact form
            print("Filling contact form")
            try:
                page.fill("#EmailAddress", generate_random_email())
                page.fill("#Postcode", generate_random_postcode())
                page.fill("#TelephoneNumber", generate_random_uk_phone())
                
                # Handle survey dropdown if present
                try:
                    survey_selector = page.query_selector("#VehicleDetailsSurvey")
                    if survey_selector:
                        page.select_option("#VehicleDetailsSurvey", str(random.randint(1, 5)))
                except Exception:
                    pass
                
            except Exception as e:
                print(f"Error filling contact form: {e}")
            
            # Handle VAT section (important step from notebook)
            print("Handling VAT section")
            try:
                vat_section = page.query_selector('label[for="IsVatRegistered"]')
                if vat_section:
                    print(f"VAT section found for {plate}")
                    # Try different selectors for VAT Yes
                    for selector in ['label[for="IsVatRegisteredtrue"]', '#IsVatRegisteredtrue']:
                        vat_yes = page.query_selector(selector)
                        if vat_yes:
                            vat_yes.click()
                            print(f"Selected Yes using {selector}")
                            break
                    
                    # Ensure VAT is selected using JavaScript
                    try:
                        page.evaluate('''
                            let radio = document.querySelector('#IsVatRegisteredtrue');
                            if (radio) {
                                radio.checked = true;
                                radio.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        ''')
                    except Exception:
                        pass
                else:
                    print(f"No VAT section for {plate}, continuing")
            except Exception as e:
                print(f"Error handling VAT section: {e}")
            
            # Click advance button using multiple selectors (from notebook)
            print("Clicking advance button")
            try:
                advance_clicked = False
                for selector in ["#advance-btn", 'button:has-text("Show my valuation")', 'button[type="submit"]']:
                    advance_btn = page.query_selector(selector)
                    if advance_btn:
                        advance_btn.click()
                        print(f"Clicked {selector} for {plate}")
                        advance_clicked = True
                        break
                
                if not advance_clicked:
                    print("Warning: Could not find advance button")
                    
            except Exception as e:
                print(f"Error clicking advance button: {e}")
                if _detect_car_not_found(page):
                    print(f"Car not found after advance button error: {plate}")
                    return None
                raise WindowsValuationError(f"Error clicking advance button: {e}")
            
            time.sleep(2.0)
            
            # Extract valuation using multiple selectors (from notebook)
            print("Waiting for valuation to appear...")
            try:
                # Wait for any valuation element to appear
                page.wait_for_selector("div.amount, div.price, .valuation-amount", state="attached", timeout=30000)
                
                valuation_text = None
                # Try specific selectors first
                for selector in ["div.amount", "div.price", ".valuation-amount", ".car-value"]:
                    element = page.query_selector(selector)
                    if element:
                        valuation_text = element.inner_text()
                        if valuation_text and valuation_text.strip():
                            print(f"Found valuation using {selector}: {valuation_text.strip()}")
                            break
                
                # If no specific selector worked, use JavaScript to find any £ amount
                if not valuation_text:
                    print("Trying JavaScript approach to find valuation...")
                    valuation_text = page.evaluate('''
                        () => {
                            const elems = document.querySelectorAll('div, span, h1, h2, h3, h4');
                            for (const el of elems) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£') && /\\d/.test(text)) {
                                    return text;
                                }
                            }
                            return null;
                        }
                    ''')
                
                if valuation_text:
                    print(f"Valuation for {plate}: {valuation_text.strip()}")
                    return valuation_text.strip()
                else:
                    print(f"No valuation found for {plate}")
                    page.screenshot(path=f"no_valuation_{plate}.png")
                    return None
                    
            except Exception as e:
                print(f"Timeout or error waiting for valuation: {e}")
                page.screenshot(path=f"timeout_{plate}.png")
                if _detect_car_not_found(page):
                    print(f"Car not found after timeout: {plate}")
                    return None
                return None
                
    except WindowsValuationError:
        # Re-raise WindowsValuationError as-is
        raise
    except PlaywrightTimeoutError as e:
        raise WindowsValuationError(f"Playwright timeout: {str(e)}")
    except Exception as e:
        print(f"Unexpected error for {plate}: {e}")
        traceback.print_exc()
        raise WindowsValuationError(f"Unexpected error: {str(e)}")
    finally:
        # Enhanced cleanup
        _cleanup_browser_resources(browser, context, page)
        print(f"Resources cleaned up for {plate}")

def parse_valuation(valuation_text):
    """Extract the numeric value from the valuation text"""
    if not valuation_text:
        return None
    
    # Clean up the text
    valuation_text = valuation_text.strip()
    
    # Extract numeric value using regex
    match = re.search(r'£([\d,]+(\.\d+)?)', valuation_text)
    if match:
        # Remove commas and convert to float
        value_str = match.group(1).replace(',', '')
        try:
            return float(value_str)
        except (ValueError, TypeError):
            return None
    
    return None
