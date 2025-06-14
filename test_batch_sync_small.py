"""
Test the synchronous batch runner with just a few entries
This ensures everything works before running the full 2815 entries
"""
import sys
import time
import asyncio
from datetime import datetime

def test_small_batch():
    """Test with just 3 entries to verify the sync batch system works"""
    print("=" * 70)
    print("TESTING SYNCHRONOUS BATCH PROCESSING (SMALL SAMPLE)")
    print("=" * 70)
    
    try:
        # Import required modules
        from wbac_modules.database_utils import connect_to_database, fetch_valuations_to_process
        from run_batch_sync import sync_browser_level_retry, sync_stats, SyncRetryConfig
        from wbac_modules.windows_valuation import parse_valuation
        
        # Get just a few entries from database
        async def get_sample_data():
            conn = await connect_to_database()
            rows = await fetch_valuations_to_process(conn)
            await conn.close()
            return rows[:3]  # Just first 3 entries
        
        print("Fetching 3 sample entries from database...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rows = loop.run_until_complete(get_sample_data())
        loop.close()
        
        if not rows:
            print("[ERROR] No entries found in database!")
            return False
        
        print(f"Retrieved {len(rows)} sample entries:")
        for i, row in enumerate(rows):
            print(f"  {i+1}. {row['number_plate']} - {row['mileage']} miles")
        
        # Reset stats
        sync_stats.reset()
        
        print(f"\nStarting processing at {datetime.now().strftime('%H:%M:%S')}...")
        
        success_count = 0
        
        for i, row in enumerate(rows):
            plate = row['number_plate'].upper().strip()
            mileage = row['mileage']
            
            print(f"\n[{i+1}/{len(rows)}] Testing {plate} (mileage: {mileage})")
            
            start_time = datetime.now()
            valuation_text = sync_browser_level_retry(plate, mileage, max_retries=2)  # Reduce retries for testing
            duration = datetime.now() - start_time
            
            if valuation_text:
                try:
                    valuation_number = parse_valuation(valuation_text)
                    if valuation_number and valuation_number > 0:
                        print(f"[SUCCESS] {plate}: £{valuation_number:.2f} (took {duration.total_seconds():.1f}s)")
                        success_count += 1
                    else:
                        print(f"[PARSE_ERROR] {plate}: Could not parse '{valuation_text}'")
                except Exception as e:
                    print(f"[PARSE_ERROR] {plate}: {e}")
            else:
                print(f"[FAILED] {plate}: No valuation retrieved")
            
            # Small delay between tests
            if i < len(rows) - 1:
                print("Waiting 3 seconds...")
                time.sleep(3)
        
        # Print results
        print(f"\n" + "=" * 50)
        print("SMALL BATCH TEST RESULTS")
        print("=" * 50)
        sync_stats.print_stats()
        print(f"Successful valuations: {success_count}/{len(rows)}")
        
        if success_count > 0:
            print(f"\n[SUCCESS] Synchronous batch processing is working!")
            print(f"Ready to process all {2815} entries with run_batch_sync.py")
            return True
        else:
            print(f"\n[WARNING] No successful valuations. Check network/website status.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_small_batch()
    
    if success:
        print(f"\n" + "=" * 70)
        print("SMALL BATCH TEST SUCCESSFUL!")
        print("The synchronous batch processor is ready for full operation")
        print(f"Run: py run_batch_sync.py")
        print("=" * 70)
    else:
        print(f"\n" + "=" * 70)
        print("TEST FAILED - Review errors above")
        print("=" * 70)
