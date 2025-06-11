"""
Configuration settings for the WBAC Driver
"""
import ssl

# Oxylabs proxy credentials
OX_USERNAME = "cyber001_pzbfZ"       # Your Oxylabs username
OX_PASSWORD = "qweASDzxc123+"        # Your Oxylabs password
OX_PROXY = "ddc.oxylabs.io:8000"     # Oxylabs proxy server (port 8000)

# Database connection settings
DB_DSN = (
    "postgres://postgres.jdwimnqtenkoedkfzosl:G0KUJJ8OBxJu4hsL@"
    "aws-0-eu-west-2.pooler.supabase.com:5432/postgres"
    "?pool_mode=session&sslmode=require"
)

# SSL Context for database connections
def get_ssl_context():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

# Browser settings
BROWSER_SETTINGS = {
    "headless": False,  # Set to False to show the browser window
    "viewport": {'width': 1366, 'height': 768},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "language": "en-GB,en;q=0.9"
}

# URLs
WBAC_URL = "https://www.webuyanycar.com/"

# Timeouts
DEFAULT_TIMEOUT = 15000  # 15 seconds
NAVIGATION_TIMEOUT = 20000  # 20 seconds
