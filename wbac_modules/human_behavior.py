"""
Functions for simulating human-like behavior
"""
import asyncio
import random
import string

def generate_random_email():
    """Generate a random email address for more natural interactions."""
    domains = ["gmail.com", "outlook.com", "yahoo.com", "hotmail.com"]
    username_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(6, 10)))
    domain = random.choice(domains)
    return f"{username_part}@{domain}"

def generate_random_uk_phone():
    """Generate a random UK mobile phone number in the format 07XXXXXXXXX."""
    return "07" + ''.join(random.choices("0123456789", k=9))

def generate_random_postcode():
    """Generate a random UK postcode."""
    postcodes = ["BD3 7HR", "LS1 4AX", "M1 1AE", "B1 1HQ", "EC1A 1BB", "SW1A 1AA"]
    return random.choice(postcodes)

async def human_type(page, selector, text, random_delay=False):
    """Type text into an input field with minimal human-like delays."""
    await page.click(selector)
    await asyncio.sleep(0.1)  # Consistent small delay
    await page.type(selector, text, delay=50)  # 50ms delay between keystrokes
    if random_delay:
        await asyncio.sleep(random.uniform(0.1, 0.3))

async def human_click(page, selector, wait_after=False):
    """Click an element with a consistent delay afterward."""
    try:
        await page.click(selector)
        if wait_after:
            await asyncio.sleep(0.2)
    except Exception as e:
        print(f"Click error on {selector}: {e}")
        try:
            await page.evaluate(f'document.querySelector("{selector}").click()')
        except Exception:
            raise

async def human_scroll(page, direction, distance):
    """Scroll the page by a given distance."""
    if direction == "down":
        await page.evaluate(f'window.scrollBy(0, {distance})')
    else:
        await page.evaluate(f'window.scrollBy(0, -{distance})')
    await asyncio.sleep(0.2)

async def human_mouse_move(page, selector):
    """Move the mouse to an element (simplified)."""
    try:
        await page.hover(selector)
    except Exception:
        pass

async def simulate_human_behavior(page):
    """
    Simulate additional human behavior by scrolling, random mouse hovering,
    and taking a brief 'thinking pause.'
    """
    # Random scroll up or down between 100 and 300 pixels
    scroll_distance = random.randint(100, 300)
    direction = random.choice(["up", "down"])
    await human_scroll(page, "down" if direction == "down" else "up", scroll_distance)
    
    # Randomly hover over one of a set of common selectors (if they exist)
    potential_selectors = ["header", "nav", "footer", "img", "article"]
    selector = random.choice(potential_selectors)
    try:
        await human_mouse_move(page, selector)
    except Exception:
        pass
    
    # Pause as if reading the page (between 1 and 3 seconds)
    await asyncio.sleep(random.uniform(1.0, 3.0))
