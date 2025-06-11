"""
Standalone Windows module for WBAC valuation using synchronous Playwright
"""
import time
import random
import traceback
import re
import sys
from playwright.sync_api import sync_playwright

# Import human behavior functions
from .human_behavior import generate_random_email, generate_random_postcode, generate_random_uk_phone
from .config import WBAC_URL

class WindowsValuationError(Exception):
    """Exception raised for errors in the Windows valuation process."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

def check_for_car_not_found(page):
    """Check if the page indicates that the car was not found"""
    content = page.content().lower()
    not_found_phrases = [
        "sorry, we couldn't find your car",
        "couldn't find your registration",
        "we cannot value your car", 
        "couldn't find your car",
        "we can't buy this car",
        "unable to provide a valuation"        
    ]
    for phrase in not_found_phrases:
        if phrase in content:
            return True
    return False

def get_valuation_windows(plate, mileage):
    """
    A purely synchronous implementation to get a valuation for Windows.
    This avoids the NotImplementedError on Windows when mixing sync/async.
    """
    # Validate and adjust mileage if needed
    if mileage == 0 or mileage is None:
        mileage = 100000
    elif mileage < 1000 and mileage > 0:
        # If mileage is a small number (2 or 3 digits), multiply by 1000
        # For example: 153 becomes 153000, 23 becomes 23000
        mileage = mileage * 1000
        print(f"Small mileage detected, converted to {mileage}")

    browser = None
    try:
        print(f"Starting Windows valuation process for {plate} with mileage {mileage}")
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=False)
            
            # Create a new context with viewport and user agent
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                locale="en-GB",
            )
            
            # Create a new page
            page = context.new_page()
            
            # Navigate to WBAC website
            print(f"Navigating to {WBAC_URL}")
            page.goto(WBAC_URL)
            time.sleep(0.3)  # Reduced wait time
            
            # Handle cookie banner if it appears
            try:
                cookie_button = page.wait_for_selector('#onetrust-accept-btn-handler', timeout=5000)
                if cookie_button:
                    print("Accepting cookies...")
                    cookie_button.click()
                    time.sleep(0.2)  # Reduced wait time
            except Exception:
                print("No cookie banner found or error handling cookies")
            
            # Short pause instead of full simulation
            time.sleep(0.5)
            
            # ----- PAGE VARIATION HANDLING -----
            max_attempts = 3
            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                if check_for_car_not_found(page):
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
                    # Type the plate with human-like delays - use fill('') to clear the field first
                    reg_field.fill('')  # Clear the field
                    for char in plate:
                        reg_field.type(char)
                        time.sleep(random.uniform(0.05, 0.2))
                        
                    # Try to click a button
                    button_clicked = False
                    for btn_selector in ['button:has-text("Get my car valuation")', 'button[type="submit"]', '#btn-go']:
                        try:
                            btn = page.query_selector(btn_selector)
                            if btn:
                                btn.click()
                                button_clicked = True
                                print(f"Clicked {btn_selector} for {plate}")
                                break
                        except Exception as e:
                            print(f"Error clicking {btn_selector}: {e}")
                            
                    if not button_clicked:
                        try:
                            page.evaluate('document.querySelector("form").submit()')
                            button_clicked = True
                            print(f"Submitted form for {plate}")
                        except Exception as e:
                            print(f"Error submitting form: {e}")
                            
                    if not button_clicked:
                        print(f"Warning: Could not find button to click for {plate}")
                    
                    # Wait for page to load after submission
                    time.sleep(random.uniform(2, 4))
                else:
                    print(f"Unexpected page state for {plate} - no reg field found")
                    try:
                        page.screenshot(path=f"unexpected_page_{plate}.png")
                        print(f"Screenshot saved as unexpected_page_{plate}.png")
                    except Exception as e:
                        print(f"Error taking screenshot: {e}")
                    
                    page.reload()
                    time.sleep(random.uniform(1.5, 3.0))
            
            if attempts >= max_attempts:
                print(f"Exceeded maximum attempts ({max_attempts}) for {plate}")
                return None
            
            if check_for_car_not_found(page):
                print(f"Car not found (before standard flow): {plate}")
                return None
            
            # Standard flow: Fill in registration and mileage
            reg_field = page.query_selector("#vehicleReg, input[placeholder*='registration'], input[name*='reg']")
            mileage_field = page.query_selector("#Mileage, input[placeholder*='mileage'], input[name*='mileage']")
            
            if reg_field:
                reg_field.fill('')  # Clear the field
                for char in plate:
                    reg_field.type(char)
                    time.sleep(random.uniform(0.05, 0.1))
            
            if mileage_field:
                mileage_field.fill(str(int(mileage)))
            
            # Brief pause before clicking the valuation button
            time.sleep(random.uniform(0.5, 1.0))
            
            # Click the valuation button with multiple selector options
            button_clicked = False
            for btn_selector in ['#btn-go', 'button[type="submit"]', 'button:has-text("Get valuation")']:
                try:
                    btn = page.query_selector(btn_selector)
                    if btn:
                        btn.click()
                        button_clicked = True
                        print(f"Clicked valuation button {btn_selector}")
                        break
                except Exception as e:
                    print(f"Error clicking {btn_selector}: {e}")
            
            if not button_clicked:
                print("Could not find any valuation button")
                return None
            
            # Wait for result page to load
            time.sleep(random.uniform(2, 3))
            
            # Check if car not found again after navigation
            if check_for_car_not_found(page):
                print(f"Car not found after form submission: {plate}")
                return None
            
            # Fill out contact form if present with enhanced handling
            contact_form_fields = {
                "#EmailAddress": generate_random_email,
                "#Postcode": generate_random_postcode,
                "#TelephoneNumber": generate_random_uk_phone
            }
            
            form_filled = False
            for selector, generator in contact_form_fields.items():
                field = page.query_selector(selector)
                if field:
                    value = generator()
                    field.fill(value)
                    print(f"Filled {selector}: {value}")
                    form_filled = True
                    time.sleep(random.uniform(0.1, 0.3))
            
            if form_filled:
                print("Contact form detected and filled")
                
                # Handle survey if present 
                try:
                    survey_selector = page.query_selector('#VehicleDetailsSurvey')
                    if survey_selector:
                        # Select a random option between 1-5
                        page.select_option('#VehicleDetailsSurvey', str(random.randint(1, 5)))
                        print("Selected random survey option")
                except Exception:
                    pass
                
                # Handle VAT question with multiple approaches
                try:
                    # Check if VAT section exists
                    vat_section = page.query_selector('label[for="IsVatRegistered"]')
                    if vat_section:
                        print(f"VAT section found for {plate}")
                        
                        # Try multiple methods to select VAT option
                        for selector in ['label[for="IsVatRegisteredtrue"]', '#IsVatRegisteredtrue']:
                            try:
                                vat_element = page.query_selector(selector)
                                if vat_element:
                                    vat_element.click()
                                    print(f"Selected VAT option using {selector}")
                                    break
                            except Exception:
                                continue
                                
                        # Try JavaScript approach as a fallback
                        try:
                            page.evaluate("""
                                let radio = document.querySelector('#IsVatRegisteredtrue');
                                if (radio) {
                                    radio.checked = true;
                                    radio.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            """)
                            print("Selected VAT option using JavaScript")
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error handling VAT section: {e}")
                
                # Click the advance button with multiple approach
                advance_clicked = False
                for selector in ["#advance-btn", 'button:has-text("Show my valuation")', 
                                 'button[type="submit"]', 'input[type="submit"]']:
                    try:
                        button = page.query_selector(selector)
                        if button:
                            time.sleep(random.uniform(0.3, 0.7))
                            button.click()
                            advance_clicked = True
                            print(f"Clicked form submission button: {selector}")
                            break
                    except Exception as e:
                        print(f"Error clicking {selector}: {e}")
                        
                if not advance_clicked:
                    # Try form submission via JavaScript
                    try:
                        page.evaluate('document.querySelector("form").submit()')
                        advance_clicked = True
                        print("Submitted form using JavaScript")
                    except Exception as e:
                        print(f"Error submitting form: {e}")
                
                # Wait after form submission
                time.sleep(random.uniform(2, 3))
                
                # Check for car not found after form submission
                if check_for_car_not_found(page):
                    print(f"Car not found after contact form submission: {plate}")
                    return None
            
            # Take screenshot before attempting valuation extraction
            try:
                page.screenshot(path=f"pre_valuation_{plate}.png")
                print(f"Screenshot saved as pre_valuation_{plate}.png")
            except Exception as e:
                print(f"Error taking screenshot: {e}")
            
            # Get current URL for debugging
            current_url = page.url
            print(f"Current page URL: {current_url}")
            
            # Try different approaches to wait for valuation elements
            # Use a more reasonable timeout and different selector strategies
            valuation_selectors = [
                'div.amount', 'div.price', '.valuation-amount', '.car-value',
                '.your-valuation-amount', 'span.valuation', '.wbac-valuation',
                'h1:has-text("£")', 'h2:has-text("£")', 'div:has-text("£")',
                'span:has-text("£")', 'p:has-text("£")', 'strong:has-text("£")',
                '.value-section', '.valuation-result', '.valuation-wrapper'
            ]
            
            # First attempt to wait for any element containing the pound sign
            found_valuation_element = False
            try:
                print("Waiting for valuation to appear...")
                page.wait_for_selector('div:has-text("£"), span:has-text("£")', timeout=10000)
                found_valuation_element = True
            except Exception:
                print("Could not find element with £ symbol within timeout period")
            
            # Even if wait times out, we'll still try extraction approaches
            # Take another screenshot after waiting period
            try:
                page.screenshot(path=f"valuation_page_{plate}.png")
                print(f"Screenshot saved as valuation_page_{plate}.png")
            except Exception as e:
                print(f"Error taking screenshot: {e}")
            
            valuation_text = None
            
            # Approach 1: Try all specific selectors one by one
            print("Trying specific CSS selectors to find valuation...")
            for selector in valuation_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        text = element.inner_text()
                        if text and text.strip() and '£' in text:
                            valuation_text = text
                            print(f"Found valuation using selector: {selector}")
                            print(f"Raw valuation text: {text.strip()}")
                            break
                except Exception as e:
                    continue
            
            # Approach 2: Advanced JavaScript extraction
            if not valuation_text:
                print("Trying JavaScript approach to find valuation...")
                try:
                    valuation_text = page.evaluate("""
                        () => {
                            // Log for debugging
                            console.log('Running JavaScript valuation extraction');
                            
                            // First approach: Look for specific class patterns
                            const valueClasses = ['amount', 'price', 'valuation', 'car-value', 'value'];
                            for (const cls of valueClasses) {
                                const elements = document.querySelectorAll('*[class*="' + cls + '"]');
                                for (const el of elements) {
                                    const text = el.innerText || el.textContent;
                                    if (text && text.includes('£') && /\\d/.test(text)) {
                                        console.log('Found by class pattern:', text, el.className);
                                        return text;
                                    }
                                }
                            }
                            
                            // Second approach: Check headings and prominent elements
                            const prominentElements = document.querySelectorAll('h1, h2, h3, h4, p.lead, strong, b');
                            for (const el of prominentElements) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£') && /\\d/.test(text)) {
                                    console.log('Found in prominent element:', text);
                                    return text;
                                }
                            }
                            
                            // Third approach: Look for any element with a pound sign and number
                            const allElements = document.querySelectorAll('*');
                            for (const el of allElements) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£') && /\\d/.test(text)) {
                                    console.log('Found in general element:', text);
                                    return text;
                                }
                            }
                            
                            // Last resort: Collect all occurrences of pound symbols for debugging
                            const allValuationText = [];
                            for (const el of document.querySelectorAll('*')) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£')) {
                                    allValuationText.push(text.trim());
                                }
                            }
                            
                            if (allValuationText.length > 0) {
                                return 'Potential valuations: ' + allValuationText.join(' | ');
                            }
                            
                            return null;
                        }
                    """)
                    if valuation_text:
                        print(f"JavaScript extraction found: {valuation_text}")
                except Exception as e:
                    print(f"JavaScript extraction error: {e}")
                    
            # Approach 3: Try taking a screenshot with browser console open
            # This is just for debugging purposes
            try:
                page.evaluate("""
                    () => {
                        console.log('Page HTML for debugging:', document.body.innerHTML);
                    }
                """)
            except Exception:
                pass
            
            # Handle the valuation result
            if valuation_text:
                print(f"Found valuation for {plate}: {valuation_text.strip()}")
                return valuation_text.strip()
            else:
                print(f"No valuation found for {plate}")
                
                # Check for specific error messages
                try:
                    error_text = page.evaluate("""
                        () => {
                            const errorElements = document.querySelectorAll('.error-message, .alert, .notification');
                            for (const el of errorElements) {
                                if (el.innerText && el.innerText.trim()) {
                                    return el.innerText;
                                }
                            }
                            return null;
                        }
                    """)
                    
                    if error_text:
                        print(f"Website error message: {error_text}")
                except Exception:
                    pass
                    
                # Take final screenshot
                try:
                    page.screenshot(path=f"no_valuation_{plate}.png")
                    print(f"Final screenshot saved as no_valuation_{plate}.png")
                except Exception as e:
                    print(f"Error taking final screenshot: {e}")
                    
                return None
                
    except Exception as e:
        print(f"Error in Windows valuation process: {e}")
        traceback.print_exc()
        return None
    finally:
        if browser:
            try:
                browser.close()
                print(f"Browser closed for {plate}")
            except Exception as e:
                print(f"Error closing browser: {e}")

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
