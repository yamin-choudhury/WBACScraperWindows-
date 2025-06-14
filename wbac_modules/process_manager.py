"""
Main process manager for handling batch processing and single plate testing
"""
import asyncio
import platform
from datetime import datetime
import re
import traceback

from .database_utils import (
    connect_to_database, insert_failure, verify_record_exists,
    fetch_valuations_to_process, insert_valuation
)

# Import the appropriate valuation module based on platform
IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    # Use Windows-specific implementation
    from .windows_valuation import get_valuation_windows, parse_valuation, WindowsValuationError as ValuationError
else:
    # Use cross-platform implementation
    from .valuation_service import process_valuation 
    from .browser_utils import parse_valuation, ValuationError

async def process_all_entries():
    """
    Process all entries in the to_valuate table and update respective tables
    with results.
    """
    start_time = datetime.now()
    print(f"Starting WBAC valuation process at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = None
    success_count = 0
    failure_count = 0
    
    try:
        conn = await connect_to_database()
        rows = await fetch_valuations_to_process(conn)
        
        print(f"Found {len(rows)} entries to valuate")
        
        for row in rows:
            unique_id = row['unique_id']
            plate = row['number_plate']
            mileage = row['mileage'] or 0
            salvage_category = row['salvage_category']
            
            print(f"\nProcessing: {plate} (ID: {unique_id})")
            
            try:
                # Use the appropriate valuation function based on platform
                if IS_WINDOWS:
                    valuation_text = get_valuation_windows(plate, mileage)
                else:
                    valuation_text = await process_valuation(plate, mileage)
                
                if not valuation_text:
                    await insert_failure(conn, unique_id, plate, mileage, "Car not found or valuation retrieval failed")
                    failure_count += 1
                    continue
                
                # Parse the valuation from text to number
                valuation_number = None
                try:
                    valuation_number = parse_valuation(valuation_text)
                except Exception:
                    valuation_number = None
                
                if valuation_number is None or valuation_number <= 0:
                    await insert_failure(conn, unique_id, plate, mileage, f"Invalid valuation: '{valuation_text}'")
                    failure_count += 1
                    continue
                
                # Apply salvage category adjustment if needed
                original_valuation = None
                if salvage_category in ['CAT N', 'CAT S']:
                    original_valuation = valuation_number
                    if salvage_category == 'CAT N':
                        # For Cat N, reduce valuation by 15%
                        valuation_number = valuation_number * 0.85
                        print(f"CAT N salvage detected: adjusted valuation from £{original_valuation:.2f} to £{valuation_number:.2f}")
                    elif salvage_category == 'CAT S':
                        # For Cat S, reduce valuation by 30%
                        valuation_number = valuation_number * 0.70
                        print(f"CAT S salvage detected: adjusted valuation from £{original_valuation:.2f} to £{valuation_number:.2f}")
                
                # Insert into valid_valuation table and remove from to_valuate
                success = await insert_valuation(
                    conn, unique_id, plate, mileage, valuation_number, 
                    original_valuation, salvage_category
                )
                
                if success:
                    success_count += 1
                    await verify_record_exists(conn, unique_id)
                else:
                    failure_count += 1
                
            except ValuationError as e:
                print(f"ValuationError for {plate}: {e.message}")
                await insert_failure(conn, unique_id, plate, mileage, f"ValuationError: {e.message}")
                failure_count += 1
            except Exception as e:
                print(f"Unexpected error for {plate}: {e}")
                traceback.print_exc()
                await insert_failure(conn, unique_id, plate, mileage, f"Error: {str(e)}")
                failure_count += 1
    
    finally:
        if conn:
            await conn.close()
        
        duration = datetime.now() - start_time
        print(f"\nWBAC valuation process completed: {success_count} successful, {failure_count} failed")
        print(f"Total runtime: {duration.total_seconds():.1f} seconds")
        
        return success_count, failure_count

async def process_single_plate(plate, mileage):
    """
    Process a single plate for testing without database storage.
    """
    print(f"\nTesting single plate: {plate} with mileage: {mileage}")
    start_time = datetime.now()
    
    try:
        # Use the appropriate valuation function based on platform
        if IS_WINDOWS:
            valuation_text = get_valuation_windows(plate, mileage)
        else:
            valuation_text = await process_valuation(plate, mileage)
        
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
        
    except ValuationError as e:
        print(f"[ERROR] ValuationError: {e.message}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return None
