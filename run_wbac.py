"""
Main entry point for WeBuyAnyCar (WBAC) valuation system.
This script provides a command-line interface for running either batch processing
or single plate testing.

To run on Windows:
1. Make sure all dependencies are installed: pip install -r requirements.txt
2. Install Playwright browsers: python -m playwright install
3. Run this script: python run_wbac.py
"""
import os
import sys
import asyncio
import traceback
import argparse

# Import nest_asyncio to allow nested event loops 
# (useful when running in certain environments or when using asyncio with other async frameworks)
try:
    import nest_asyncio
    nest_asyncio.apply()
    print("Nest-asyncio applied successfully.")
except ImportError:
    print("Warning: nest_asyncio not found. This may cause issues in Jupyter environments.")

def check_requirements():
    """Check if required packages are installed"""
    try:
        import playwright
        import asyncpg
    except ImportError as e:
        print(f"ERROR: Missing required package - {e}")
        print("\nPlease install required packages using:")
        print("pip install -r requirements.txt")
        print("python -m playwright install")
        return False
    return True

async def main():
    """Main entry point with command line argument handling"""
    if not check_requirements():
        return
        
    # Import here to avoid errors if requirements aren't met
    try:
        # Import our modules
        from wbac_modules.process_manager import process_all_entries, process_single_plate
    except ImportError as e:
        print(f"ERROR: Could not import WBAC modules - {e}")
        print("Make sure you're running from the correct directory")
        return
    
    parser = argparse.ArgumentParser(description="WeBuyAnyCar (WBAC) Valuation System")
    parser.add_argument("--plate", help="Process a single license plate")
    parser.add_argument("--mileage", type=int, help="Vehicle mileage for single plate testing")
    parser.add_argument("--batch", action="store_true", help="Run batch processing from database")
    
    args = parser.parse_args()
    
    # Display menu if no arguments provided
    if not (args.plate or args.batch):
        print("\n" + "="*60)
        print("WeBuyAnyCar (WBAC) Valuation System")
        print("="*60)
        print("1. Process all entries from database")
        print("2. Test a single plate")
        print("0. Exit")
        print("="*60)
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            try:
                await process_all_entries()
            except Exception as e:
                print(f"\nERROR processing entries: {e}")
                traceback.print_exc()
        elif choice == "2":
            plate = input("Enter license plate: ").strip().upper()
            mileage_input = input("Enter mileage (default 100000): ").strip()
            try:
                mileage = int(mileage_input) if mileage_input else 100000
                await process_single_plate(plate, mileage)
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
        await process_single_plate(args.plate.strip().upper(), mileage)
    elif args.batch:
        await process_all_entries()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        traceback.print_exc()
