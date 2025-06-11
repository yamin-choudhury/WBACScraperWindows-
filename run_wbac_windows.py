"""
Windows-specific entry point for the WBAC valuation system.
This is a fully synchronous implementation that avoids asyncio conflicts on Windows.
"""
import os
import sys
import traceback
import argparse
import platform
from datetime import datetime

# Ensure we're only running this on Windows
if platform.system() != 'Windows':
    print("This script is intended for Windows only. Please use run_wbac.py instead.")
    sys.exit(1)

# Import required modules
try:
    from wbac_modules.windows_valuation import get_valuation_windows, parse_valuation, WindowsValuationError
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print(f"ERROR: Missing required package - {e}")
    print("\nPlease install required packages using:")
    print("pip install -r requirements.txt")
    print("python -m playwright install")
    sys.exit(1)

def check_requirements():
    """Check if required packages are installed"""
    try:
        import playwright
    except ImportError as e:
        print(f"ERROR: Missing required package - {e}")
        print("\nPlease install required packages using:")
        print("pip install -r requirements.txt")
        print("python -m playwright install")
        return False
    return True

def process_single_plate(plate, mileage):
    """
    Process a single plate for testing without database storage.
    Synchronous implementation for Windows.
    """
    print(f"\nTesting single plate: {plate} with mileage: {mileage}")
    start_time = datetime.now()
    
    try:
        valuation_text = get_valuation_windows(plate, mileage)
        
        if not valuation_text:
            print(f"[ERROR] No valuation found for {plate}")
            return None
        
        print(f"[SUCCESS] Raw valuation for {plate}: {valuation_text}")
        
        # Parse the valuation from text to number
        valuation_number = parse_valuation(valuation_text)
        
        if valuation_number is None or valuation_number <= 0:
            print(f"[ERROR] Invalid valuation: '{valuation_text}'")
            return None
        
        print(f"[SUCCESS] Parsed valuation for {plate}: £{valuation_number:.2f}")
        
        duration = datetime.now() - start_time
        print(f"\nProcess completed in {duration.total_seconds():.1f} seconds")
        
        return valuation_number
        
    except WindowsValuationError as e:
        print(f"[ERROR] ValuationError: {e.message}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return None

def batch_process():
    """
    Placeholder for batch processing from database.
    For full batch processing, we recommend using the default run_wbac.py
    with proper asyncio configuration.
    """
    print("Batch processing on Windows is not implemented in this simplified script.")
    print("For batch processing, please use the main run_wbac.py script")
    print("with proper Windows event loop policy configuration.")
    return

def main():
    """Main entry point with command line argument handling"""
    if not check_requirements():
        return
    
    parser = argparse.ArgumentParser(description="WeBuyAnyCar (WBAC) Valuation System - Windows Version")
    parser.add_argument("--plate", help="Process a single license plate")
    parser.add_argument("--mileage", type=int, help="Vehicle mileage for single plate testing")
    parser.add_argument("--batch", action="store_true", help="Run batch processing from database")
    
    args = parser.parse_args()
    
    # Display menu if no arguments provided
    if not (args.plate or args.batch):
        print("\n" + "="*60)
        print("WeBuyAnyCar (WBAC) Valuation System - Windows Version")
        print("="*60)
        print("1. Test a single plate")
        print("0. Exit")
        print("="*60)
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            plate = input("Enter license plate: ").strip().upper()
            mileage_input = input("Enter mileage (default 100000): ").strip()
            try:
                mileage = int(mileage_input) if mileage_input else 100000
                process_single_plate(plate, mileage)
            except ValueError:
                print("Invalid mileage value. Please enter a number.")
            except Exception as e:
                print(f"\nERROR processing plate {plate}: {e}")
                traceback.print_exc()
        elif choice == "0":
            print("Exiting...")
            return
        else:
            print("Invalid choice.")
            return
    
    # Process command line arguments
    elif args.plate:
        mileage = args.mileage if args.mileage is not None else 100000
        process_single_plate(args.plate.strip().upper(), mileage)
    elif args.batch:
        print("Batch processing is not supported in the Windows-specific script.")
        print("Please use the main run_wbac.py script for batch processing.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        traceback.print_exc()
