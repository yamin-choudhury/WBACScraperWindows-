"""
Core valuation service for processing license plates through WBAC
"""
import asyncio
import random
import sys
import os
import platform
import time
import traceback

# Fix for Windows subprocess implementation
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
# Determine if we're running on Windows
IS_WINDOWS = platform.system() == 'Windows'

# Import appropriate Playwright modules
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Import for non-Windows environments
if not IS_WINDOWS:
    from playwright.async_api import async_playwright

from .config import WBAC_URL
from .human_behavior import (
    generate_random_email, generate_random_postcode, generate_random_uk_phone,
    human_type, simulate_human_behavior
)
from .browser_utils import (
    check_for_car_not_found, ValuationError, setup_browser, setup_page
)

async def process_valuation(plate, mileage):
    """
    Use Playwright to interact with the valuation website and extract the valuation text.
    Incorporates human-like behavior to avoid bot detection.
    Uses sync API on Windows and async API on other platforms.
    """
    # Validate and adjust mileage if needed
    if mileage == 0 or mileage is None:
        mileage = 100000
    elif mileage < 1000 and mileage > 0:
        # If mileage is a small number (2 or 3 digits), multiply by 1000
        # For example: 153 becomes 153000, 23 becomes 23000
        mileage = mileage * 1000
        print(f"Small mileage detected, converted to {mileage}")

    if IS_WINDOWS:
        # Windows implementation using synchronous Playwright API
        # Return the result of the synchronous version wrapped in an async function
        return await asyncio.to_thread(process_valuation_sync, plate, mileage)
    else:
        # For non-Windows platforms, use the async API
        return await process_valuation_async(plate, mileage)


def process_valuation_sync(plate, mileage):
    """
    Synchronous implementation of the valuation process for Windows systems.
    """
    browser = None
    try:
        print(f"Starting synchronous valuation process for {plate} with mileage {mileage}")
        with sync_playwright() as p:
            # Launch browser with configuration from the config module
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
                locale="en-GB"
            )
            
            # Create a new page
            page = context.new_page()
            
            # Navigate to the WBAC site
            print(f"Navigating to {WBAC_URL}")
            page.goto(WBAC_URL)
            time.sleep(0.5)  # Short delay after navigation
            
            # Handle cookie consent if present
            try:
                cookie_button = page.wait_for_selector('#onetrust-accept-btn-handler', timeout=5000)
                if cookie_button:
                    print("Accepting cookies...")
                    cookie_button.click()
                    time.sleep(0.2)
            except Exception:
                print("No cookie banner found or error handling cookies")
            
            # Fill in the registration plate
            reg_input = page.query_selector('#vehicleReg')
            if not reg_input:
                print("Could not find registration input field")
                return None
                
            # Type like a human
            for character in plate:
                reg_input.type(character)
                time.sleep(random.uniform(0.05, 0.2))  # Random delay between keystrokes
            
            # Fill in mileage
            mileage_input = page.query_selector('#Mileage')
            if not mileage_input:
                print("Could not find mileage input field")
                return None
                
            # Clear the field and type mileage
            mileage_input.fill(str(int(mileage)))
            
            # Add random delay before clicking the button
            time.sleep(random.uniform(0.5, 1.5))
            
            # Click the valuation button
            go_button = page.query_selector('#btn-go')
            if go_button:
                go_button.click()
                print("Clicked valuation button")
            else:
                print("Could not find valuation button")
                return None
            
            # Wait for page to load
            time.sleep(random.uniform(2, 4))
            
            # Check if car was found
            content = page.content()
            if "sorry, we couldn't find your car" in content.lower():
                print(f"Car not found: {plate}")
                return None
            
            # Fill out form fields if present
            try:
                # Generate random email, postcode, and phone number
                email = generate_random_email()
                postcode = generate_random_postcode()
                phone = generate_random_uk_phone()
                
                # Fill form fields
                email_field = page.query_selector('#EmailAddress')
                if email_field:
                    email_field.fill(email)
                    
                postcode_field = page.query_selector('#Postcode')
                if postcode_field:
                    postcode_field.fill(postcode)
                    
                phone_field = page.query_selector('#TelephoneNumber')
                if phone_field:
                    phone_field.fill(phone)
                
                # Click advance button
                advance_button = page.query_selector('#advance-btn')
                if advance_button:
                    advance_button.click()
                    print("Clicked advance button")
                    time.sleep(2)  # Wait for valuation
            except Exception as e:
                print(f"Error filling form: {e}")
            
            # Extract valuation using multiple selectors
            try:
                page.wait_for_selector('div.amount, div.price, .valuation-amount', timeout=30000)
                valuation_text = None
                
                # Try multiple possible selectors
                for selector in ["div.amount", "div.price", ".valuation-amount", ".car-value"]:
                    element = page.query_selector(selector)
                    if element:
                        valuation_text = element.inner_text()
                        if valuation_text and valuation_text.strip():
                            break
                
                # If nothing found, try JavaScript approach
                if not valuation_text:
                    valuation_text = page.evaluate("""
                        () => {
                            const elems = document.querySelectorAll('div, span, h1, h2, h3, h4');
                            for (const el of elems) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£') && /\d/.test(text)) {
                                    return text;
                                }
                            }
                            return null;
                        }
                    """)
                
                if valuation_text:
                    print(f"Valuation for {plate}: {valuation_text.strip()}")
                    return valuation_text.strip()
                else:
                    print(f"No valuation found for {plate}")
                    # Take screenshot for debugging
                    try:
                        page.screenshot(path=f"no_valuation_{plate}.png")
                    except Exception:
                        pass
                    return None
                    
            except Exception as e:
                print(f"Error extracting valuation: {e}")
                return None
                
    except Exception as e:
        print(f"Error in synchronous process: {e}")
        traceback.print_exc()
        return None
    finally:
        if browser:
            try:
                browser.close()
                print(f"Browser closed for {plate}")
            except Exception as e:
                print(f"Error closing browser: {e}")


async def process_valuation_async(plate, mileage):
    """
    Asynchronous implementation of the valuation process for non-Windows systems.
    """
    browser = None
    total_bytes = 0  # Initialize bandwidth counter
    
    try:
        async with async_playwright() as p:
            # Launch browser and create context
            browser, context = await setup_browser(p)
            page, total_bytes = await setup_page(context)
            
            # Navigate to WBAC website
            await page.goto(WBAC_URL)
            await asyncio.sleep(0.3)
            
            # Handle cookie banner
            try:
                cookie_button = await page.wait_for_selector("#onetrust-accept-btn-handler", timeout=5000)
                if cookie_button:
                    await page.click("#onetrust-accept-btn-handler")
                    await asyncio.sleep(0.2)
            except Exception:
                pass
            
            # Short pause
            await asyncio.sleep(0.5)
            
            # Simulate human behavior
            await simulate_human_behavior(page)
            
            # ----- PAGE VARIATION HANDLING -----
            max_attempts = 3
            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                if await check_for_car_not_found(page):
                    print(f"Car not found (during page variation handling): {plate}")
                    return None
                
                # Try multiple selectors for registration and mileage fields
                reg_field = await page.query_selector("#vehicleReg, input[placeholder*='registration'], input[name*='reg']")
                mileage_field = await page.query_selector("#Mileage, input[placeholder*='mileage'], input[name*='mileage']")
                
                if reg_field and mileage_field:
                    print(f"Standard page with both fields detected for {plate}")
                    break
                elif reg_field and not mileage_field:
                    print(f"Variant page with only reg field detected for {plate} (attempt {attempts})")
                    await human_type(page, "#vehicleReg", plate)
                    button_clicked = False
                    for btn_selector in ['button:has-text("Get my car valuation")', 'button[type="submit"]']:
                        if await page.query_selector(btn_selector):
                            await page.click(btn_selector)
                            button_clicked = True
                            print(f"Clicked {btn_selector} for {plate}")
                            break
                    if not button_clicked:
                        form = await page.query_selector('form')
                        if form:
                            await page.evaluate('document.querySelector("form").submit()')
                            button_clicked = True
                            print(f"Submitted form for {plate}")
                    if not button_clicked:
                        print(f"Warning: Could not find button to click for {plate}")
                    await asyncio.sleep(random.uniform(2, 4))
                    # Simulate a human reading the page after form submission
                    await simulate_human_behavior(page)
                else:
                    print(f"Unexpected page state for {plate} - no reg field found")
                    await page.screenshot(path=f"unexpected_page_{plate}.png")
                    await page.reload()
                    await asyncio.sleep(random.uniform(1.5, 3.0))
            
            if attempts >= max_attempts:
                print(f"Exceeded maximum attempts ({max_attempts}) for {plate}")
                return None
            
            if await check_for_car_not_found(page):
                print(f"Car not found (before standard flow): {plate}")
                return None
            
            # Standard flow: Fill in registration and mileage
            await human_type(page, "#vehicleReg", plate)
            await human_type(page, "#Mileage", str(int(mileage)))
            # Simulate a brief pause before clicking the valuation button
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.click("#btn-go")
            await asyncio.sleep(random.uniform(2, 4))
            if await check_for_car_not_found(page):
                print(f"Car not found after form submission: {plate}")
                return None
            
            # Simulate human behavior before filling contact form
            await simulate_human_behavior(page)
            
            # Fill out the contact form
            await page.fill("#EmailAddress", generate_random_email())
            await page.fill("#Postcode", generate_random_postcode())
            await page.fill("#TelephoneNumber", generate_random_uk_phone())
            
            # Handle survey if present
            try:
                survey_selector = await page.query_selector("#VehicleDetailsSurvey")
                if survey_selector:
                    await page.select_option("#VehicleDetailsSurvey", str(random.randint(1, 5)))
            except Exception:
                pass
            
            # Handle VAT section
            try:
                vat_section = await page.query_selector('label[for="IsVatRegistered"]')
                if vat_section:
                    print(f"VAT section found for {plate}")
                    for selector in ['label[for="IsVatRegisteredtrue"]', '#IsVatRegisteredtrue']:
                        if await page.query_selector(selector):
                            await page.click(selector)
                            print(f"Selected Yes using {selector}")
                            break
                    try:
                        await page.evaluate('''
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
            
            # Click advance button using multiple selectors
            try:
                for selector in ["#advance-btn", 'button:has-text("Show my valuation")', 'button[type="submit"]']:
                    if await page.query_selector(selector):
                        await page.click(selector)
                        print(f"Clicked {selector} for {plate}")
                        break
            except Exception as e:
                print(f"Error clicking advance button: {e}")
                if await check_for_car_not_found(page):
                    print(f"Car not found after advance button error: {plate}")
                    return None
                raise
            
            await asyncio.sleep(2.0)
            
            # Extract valuation using multiple selectors
            try:
                await page.wait_for_selector("div.amount, div.price, .valuation-amount", state="attached", timeout=30000)
                valuation_text = None
                for selector in ["div.amount", "div.price", ".valuation-amount", ".car-value"]:
                    element = await page.query_selector(selector)
                    if element:
                        valuation_text = await element.inner_text()
                        if valuation_text and valuation_text.strip():
                            break
                if not valuation_text:
                    valuation_text = await page.evaluate('''
                        () => {
                            const elems = document.querySelectorAll('div, span, h1, h2, h3, h4');
                            for (const el of elems) {
                                const text = el.innerText || el.textContent;
                                if (text && text.includes('£') && /\d/.test(text)) {
                                    return text;
                                }
                            }
                            return null;
                        }
                    ''')
                if valuation_text:
                    print(f"Valuation for {plate}: {valuation_text.strip()}")
                    print(f"Total bandwidth used for listing {plate}: {total_bytes} bytes")
                    return valuation_text.strip()
                else:
                    await page.screenshot(path=f"no_valuation_{plate}.png")
                    raise ValuationError("No valuation found on page")
            except PlaywrightTimeoutError:
                await page.screenshot(path=f"timeout_{plate}.png")
                if await check_for_car_not_found(page):
                    print(f"Car not found after timeout: {plate}")
                    return None
                raise ValuationError("Timeout waiting for valuation")
        
    except Exception as e:
        if not isinstance(e, ValuationError):
            print(f"Unexpected error for {plate}: {str(e)}")
            raise ValuationError(f"Unexpected error: {str(e)}")
        raise
    finally:
        if browser:
            try:
                await browser.close()
                print(f"Browser closed for {plate}")
            except Exception as e:
                print(f"Error closing browser: {e}")
    
    # This line should never be reached as all code paths return a value
    return None
