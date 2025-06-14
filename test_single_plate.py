"""
Simple test script for single plate valuation
"""
import sys
import traceback
from wbac_modules.windows_valuation import get_valuation_windows, parse_valuation, WindowsValuationError

def test_single_plate(plate, mileage):
    """Test a single license plate"""
    print(f"\n=== Testing Single Plate: {plate} ===")
    print(f"Mileage: {mileage}")
    print("-" * 40)
    
    try:
        # Get raw valuation text
        valuation_text = get_valuation_windows(plate, mileage)
        
        if not valuation_text:
            print(f"[ERROR] No valuation found for {plate}")
            return None
        
        print(f"[SUCCESS] Raw valuation text: {valuation_text}")
        
        # Parse valuation to get numeric value
        valuation_amount = parse_valuation(valuation_text)
        
        if valuation_amount and valuation_amount > 0:
            print(f"[SUCCESS] Parsed valuation: £{valuation_amount:.2f}")
            return valuation_amount
        else:
            print(f"[ERROR] Failed to parse valuation from: {valuation_text}")
            return None
            
    except WindowsValuationError as e:
        print(f"[ERROR] Valuation Error: {e.message}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_single_plate.py <PLATE> [MILEAGE]")
        print("Example: python test_single_plate.py DF15ZXB 50000")
        sys.exit(1)
    
    plate = sys.argv[1].upper().strip()
    mileage = int(sys.argv[2]) if len(sys.argv) > 2 else 50000
    
    result = test_single_plate(plate, mileage)
    
    if result:
        print(f"\n[SUCCESS] {plate} valued at £{result:.2f}")
    else:
        print(f"\n[FAILED] Could not get valuation for {plate}")
