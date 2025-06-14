"""
Simple synchronous test for single plate processing
This avoids any asyncio issues with Playwright sync API
"""
import sys
import time
from datetime import datetime

def test_single_plate_sync():
    """Test single plate processing without asyncio"""
    print("=" * 60)
    print("TESTING SINGLE PLATE (SYNCHRONOUS)")
    print("=" * 60)
    
    test_plate = "DF15ZXB"
    test_mileage = 50000
    
    try:
        from wbac_modules.windows_valuation import get_valuation_windows, parse_valuation
        
        print(f"Testing plate: {test_plate}")
        print(f"Mileage: {test_mileage}")
        print("Starting valuation process...")
        
        start_time = datetime.now()
        valuation_text = get_valuation_windows(test_plate, test_mileage)
        duration = datetime.now() - start_time
        
        if valuation_text:
            print(f"[SUCCESS] Valuation retrieved: {valuation_text}")
            
            try:
                valuation_number = parse_valuation(valuation_text)
                if valuation_number and valuation_number > 0:
                    print(f"[SUCCESS] Parsing successful: £{valuation_number:.2f}")
                    print(f"[INFO] Test completed in {duration.total_seconds():.1f} seconds")
                    print("\n[RESULT] SINGLE PLATE TEST SUCCESSFUL!")
                    return True
                else:
                    print(f"[ERROR] Parsing failed: {valuation_number}")
                    return False
            except Exception as e:
                print(f"[ERROR] Parsing error: {e}")
                return False
        else:
            print(f"[ERROR] No valuation retrieved for {test_plate}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parse_function():
    """Test parsing function with sample data"""
    print("\n" + "=" * 60)
    print("TESTING PARSING FUNCTION")
    print("=" * 60)
    
    try:
        from wbac_modules.windows_valuation import parse_valuation
        
        test_cases = [
            "£12,345.67",
            "£8,765.43",
            "£1,234.00",
            "£50,000.99"
        ]
        
        for test_val in test_cases:
            try:
                result = parse_valuation(test_val)
                print(f"[TEST] '{test_val}' -> £{result:.2f}")
            except Exception as e:
                print(f"[ERROR] Failed to parse '{test_val}': {e}")
                return False
        
        print("\n[SUCCESS] All parsing tests passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Parsing test failed: {e}")
        return False

if __name__ == "__main__":
    print("Windows WBAC Scraper - Synchronous Test")
    print("=" * 60)
    
    # Test parsing first
    parse_success = test_parse_function()
    
    # Test single plate if parsing works
    if parse_success:
        plate_success = test_single_plate_sync()
        
        if plate_success:
            print("\n" + "=" * 60)
            print("ALL TESTS SUCCESSFUL!")
            print("The Windows scraper is ready for batch processing")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("PLATE TEST FAILED - Check network/website availability")
            print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("PARSING TEST FAILED - Check parse_valuation function")
        print("=" * 60)
