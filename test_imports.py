"""
Test imports to verify package structure
"""
print("Testing imports...")

try:
    from wbac_modules.config import WBAC_URL
    print(f"[OK] Config imported. WBAC_URL: {WBAC_URL}")
except Exception as e:
    print(f"[ERROR] Config import failed: {e}")

try:
    from wbac_modules.human_behavior import generate_random_email
    print("[OK] Human behavior imported")
except Exception as e:
    print(f"[ERROR] Human behavior import failed: {e}")

try:
    from wbac_modules.windows_valuation import WindowsValuationError, parse_valuation
    print("[OK] Windows valuation imported")
except Exception as e:
    print(f"[ERROR] Windows valuation import failed: {e}")

try:
    from wbac_modules.windows_valuation import get_valuation_windows
    print("[OK] All imports successful!")
except Exception as e:
    print(f"[ERROR] Final import failed: {e}")

print("Import test complete.")
