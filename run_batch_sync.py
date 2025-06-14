"""
Synchronous batch runner for WBAC scraper with retry mechanism
Designed specifically for Windows to avoid asyncio/sync Playwright conflicts
Processes all entries with robust retry and monitoring capabilities
"""
import sys
import time
import random
import signal
import gc
import psutil
from datetime import datetime
from threading import Thread
import traceback
import asyncio
import asyncpg

# Import WBAC modules
from wbac_modules.database_utils import connect_to_database, fetch_valuations_to_process
from wbac_modules.windows_valuation import parse_valuation, get_valuation_windows

# Ensure we're on Windows
if sys.platform != 'win32':
    print("This script is designed for Windows only!")
    sys.exit(1)

class SyncRetryConfig:
    """Configuration for synchronous retry mechanism"""
    BROWSER_MAX_RETRIES = 3
    BATCH_MAX_RETRIES = 10
    BROWSER_RECYCLING_THRESHOLD = 75
    MEMORY_CHECK_INTERVAL = 50
    MAX_MEMORY_USAGE_MB = 2048
    MIN_DELAY_BETWEEN_VALUATIONS = 2.0
    MAX_DELAY_BETWEEN_VALUATIONS = 5.0
    
    BROWSER_RETRY_DELAY_BASE = 2.0
    BROWSER_RETRY_DELAY_MAX = 30.0
    BATCH_RETRY_DELAY_BASE = 5.0
    BATCH_RETRY_DELAY_MAX = 120.0

class SyncRetryStats:
    """Statistics tracking for retry mechanism"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.total_attempts = 0
        self.successes = 0
        self.failures = 0
        self.browser_retries = 0
        self.batch_retries = 0
        self.start_time = datetime.now()
    
    def success_rate(self):
        if self.total_attempts == 0:
            return 0.0
        return (self.successes / self.total_attempts) * 100
    
    def print_stats(self):
        duration = datetime.now() - self.start_time
        print(f"\n=== RETRY STATISTICS ===")
        print(f"Total attempts: {self.total_attempts}")
        print(f"Successes: {self.successes}")
        print(f"Failures: {self.failures}")
        print(f"Success rate: {self.success_rate():.1f}%")
        print(f"Browser retries: {self.browser_retries}")
        print(f"Batch retries: {self.batch_retries}")
        print(f"Runtime: {duration.total_seconds():.1f}s")

# Global stats instance
sync_stats = SyncRetryStats()
graceful_shutdown = False

def signal_handler(signum, frame):
    """Handle interrupt signals (Ctrl+C)"""
    global graceful_shutdown
    print(f"\n[INTERRUPT] Received signal {signum}. Initiating graceful shutdown...")
    graceful_shutdown = True
    
    # Force exit after 3 seconds if graceful shutdown doesn't work
    def force_exit():
        import time
        time.sleep(3)
        print("\n[FORCE_EXIT] Forcing immediate exit...")
        import os
        os._exit(0)
    
    import threading
    force_thread = threading.Thread(target=force_exit, daemon=True)
    force_thread.start()

def exponential_backoff(attempt, base_delay=2.0, max_delay=30.0):
    """Calculate exponential backoff delay with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0.8, 1.2)
    return delay * jitter

def check_memory_usage():
    """Check current memory usage"""
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    memory_percent = process.memory_percent()
    
    return {
        'rss_mb': memory_mb,
        'percent': memory_percent
    }

def force_memory_cleanup():
    """Force garbage collection and memory cleanup"""
    gc.collect()
    time.sleep(0.1)

def should_retry_error(error_msg):
    """
    Determine if an error should trigger a retry or be treated as permanent failure.
    Car not found should NOT trigger retries - it's a valid result to record as failure.
    """
    # Convert to lowercase for easier matching
    error_lower = str(error_msg).lower()
    
    # DON'T retry these - they are valid "failure" results
    non_retry_errors = [
        'car not found',
        'vehicle not found',
        'registration not found',
        'no valuation found'
    ]
    
    for non_retry in non_retry_errors:
        if non_retry in error_lower:
            return False
    
    # DO retry these - they are technical issues
    retry_errors = [
        'timeout',
        'connection',
        'network',
        'element not attached',
        'target closed',
        'context was destroyed',
        'browser has been closed',
        'unexpected error'
    ]
    
    for retry_error in retry_errors:
        if retry_error in error_lower:
            return True
    
    # Default: don't retry unknown errors (treat as permanent failures)
    return False

def sync_browser_level_retry(plate, mileage, max_retries=3):
    """Browser-level retry with smart error classification"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[{attempt}/{max_retries}] Processing {plate}")
            
            sync_stats.total_attempts += 1
            valuation_text = get_valuation_windows(plate, mileage)
            
            if valuation_text:
                sync_stats.successes += 1
                return valuation_text
            else:
                # Check if this was a "car not found" (don't retry) or technical issue (retry)
                print(f"No valuation returned for {plate}")
                
                # If it's the last attempt, treat as failure
                if attempt == max_retries:
                    sync_stats.failures += 1
                    return None
                else:
                    # For now, let's not retry empty results unless we can determine the cause
                    sync_stats.failures += 1
                    return None
                    
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Attempt {attempt} error for {plate}: {error_msg}")
            
            # Check if we should retry this error
            if not should_retry_error(error_msg):
                print(f"[NO_RETRY] {plate}: Error not retryable - {error_msg}")
                sync_stats.failures += 1
                return None
            
            sync_stats.browser_retries += 1
            
            if attempt == max_retries:
                print(f"[FAILED] All retries exhausted for {plate}")
                sync_stats.failures += 1
                return None
            
            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 2)
            print(f"[DELAY] Waiting {delay:.1f}s before retry...")
            time.sleep(delay)
    
    return None

def process_single_valuation(row, attempt_num, total_entries):
    """Process a single valuation with proper database operations"""
    unique_id = row['unique_id']
    plate = row['number_plate'].upper().strip()
    mileage = row['mileage']
    
    print(f"\n[{attempt_num}/{total_entries}] Processing: {plate} (ID: {unique_id})")
    
    start_time = datetime.now()
    
    # Attempt to get valuation
    valuation_text = sync_browser_level_retry(plate, mileage, max_retries=3)
    
    duration = datetime.now() - start_time
    
    if valuation_text:
        try:
            # Parse the valuation
            valuation_number = parse_valuation(valuation_text)
            
            if valuation_number and valuation_number > 0:
                print(f"Valuation for {plate}: £{valuation_number:.2f}")
                
                # Insert successful valuation into database
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    result = loop.run_until_complete(
                        insert_successful_valuation(unique_id, plate, valuation_number, mileage)
                    )
                    if result:
                        print(f"DB INSERT SUCCESS: {plate} valuation: £{valuation_number:.2f}")
                        print(f"✓ VERIFIED: Record {unique_id} exists in valid_valuation table")
                        return True
                    else:
                        print(f"[DB_ERROR] Failed to insert {plate} valuation")
                        return False
                finally:
                    loop.close()
            else:
                print(f"Could not parse valuation from: '{valuation_text}'")
                # Treat parsing failure as a failed valuation
                return await_insert_failed_valuation(unique_id, plate, "Could not parse valuation")
        
        except Exception as e:
            print(f"[PARSE_ERROR] {plate}: {e}")
            return await_insert_failed_valuation(unique_id, plate, f"Parse error: {str(e)}")
    else:
        # No valuation returned - could be car not found or technical failure
        print(f"No valuation text returned for {plate} - likely car not found")
        return await_insert_failed_valuation(unique_id, plate, "No valuation returned")

def await_insert_failed_valuation(unique_id, plate, reason):
    """Helper to insert failed valuation using async event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            insert_failed_valuation(unique_id, plate, reason)
        )
        if result:
            print(f"Added to failed_valuations: {unique_id}")
            return True
        else:
            print(f"[DB_ERROR] Failed to insert failure record for {plate}")
            return False
    finally:
        loop.close()

async def insert_successful_valuation(unique_id, plate, valuation, mileage):
    """Insert successful valuation into database"""
    try:
        conn = await connect_to_database()
        
        query = """
            INSERT INTO car_pipeline.valid_valuation 
            (unique_id, number_plate, valuation, mileage, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (unique_id) DO UPDATE SET
            valuation = EXCLUDED.valuation,
            created_at = EXCLUDED.created_at
        """
        
        await conn.execute(query, unique_id, plate, valuation, mileage)
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[DB_ERROR] Failed to insert successful valuation: {e}")
        if 'conn' in locals():
            await conn.close()
        return False

async def insert_failed_valuation(unique_id, plate, reason):
    """Insert failed valuation into database"""
    try:
        conn = await connect_to_database()
        
        query = """
            INSERT INTO car_pipeline.failed_valuations 
            (unique_id, number_plate, failure_reason, created_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (unique_id) DO UPDATE SET
            failure_reason = EXCLUDED.failure_reason,
            created_at = EXCLUDED.created_at
        """
        
        await conn.execute(query, unique_id, plate, reason)
        await conn.close()
        return True
        
    except Exception as e:
        print(f"[DB_ERROR] Failed to insert failed valuation: {e}")
        if 'conn' in locals():
            await conn.close()
        return False

def process_entries_sync():
    """
    Process all database entries synchronously with retry mechanism
    """
    global sync_stats, graceful_shutdown
    
    print("="*70)
    print("STARTING SYNCHRONOUS BATCH PROCESSING")
    print("="*70)
    
    # Get all entries from database
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        print("Connecting to database...")
        conn_result = loop.run_until_complete(connect_to_database())
        
        print("Fetching entries to process...")
        rows = loop.run_until_complete(fetch_valuations_to_process(conn_result))
        
        loop.run_until_complete(conn_result.close())
        loop.close()
        
        if not rows:
            print("No entries found to process!")
            return
        
        total_entries = len(rows)
        print(f"Found {total_entries} entries to valuate")
        
        # Initialize tracking variables
        processed_count = 0
        success_count = 0
        failure_count = 0
        consecutive_failures = 0
        browser_count = 0
        
        print(f"\nStarting processing at {datetime.now().strftime('%H:%M:%S')}...")
        
        for i, row in enumerate(rows):
            if graceful_shutdown:
                print(f"\n[INTERRUPT] Graceful shutdown requested. Processed {processed_count}/{total_entries}")
                break
                
            processed_count += 1
            unique_id = row['unique_id']
            plate = row['number_plate'].upper().strip()
            mileage = row['mileage']
            salvage_category = row.get('salvage_category')
            
            print(f"\n[{processed_count}/{total_entries}] Processing: {plate} (ID: {unique_id})")
            
            try:
                # Process single valuation
                result = process_single_valuation(row, processed_count, total_entries)
                
                if result:
                    success_count += 1
                    consecutive_failures = 0
                else:
                    failure_count += 1
                    consecutive_failures += 1
                
                # Check for too many consecutive failures (restart browser)
                if consecutive_failures >= 5:
                    print(f"[WARNING] {consecutive_failures} consecutive failures. Browser may need recycling.")
                    force_memory_cleanup()
                    consecutive_failures = 0  # Reset after cleanup
                
                # Browser recycling
                browser_count += 1
                if browser_count >= 75:  # Browser recycling threshold
                    print(f"[RECYCLE] Browser recycled after {browser_count} operations")
                    browser_count = 0
                    force_memory_cleanup()
                
                # Random delay between operations (anti-detection)
                if processed_count < total_entries:
                    delay = random.uniform(2, 5)
                    print(f"[WAIT] {delay:.1f}s delay...")
                    time.sleep(delay)
                
            except Exception as e:
                print(f"[UNEXPECTED_ERROR] {plate}: {e}")
                failure_count += 1
                consecutive_failures += 1
                
                # Insert failure record
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    insert_failed_valuation(unique_id, plate, f"Unexpected error: {str(e)}")
                )
                loop.close()
        
        # Final statistics
        print(f"\n" + "="*70)
        print("BATCH PROCESSING COMPLETED")
        print("="*70)
        sync_stats.print_stats()
        print(f"Total processed: {processed_count}/{total_entries}")
        print(f"Successful: {success_count}")
        print(f"Failed: {failure_count}")
        print(f"Success rate: {(success_count/processed_count*100):.1f}%" if processed_count > 0 else "N/A")
        
    except Exception as e:
        print(f"[FATAL_ERROR] Batch processing failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        force_memory_cleanup()

def print_system_info():
    """Print system information"""
    memory = psutil.virtual_memory()
    cpu_count = psutil.cpu_count()
    
    print("=" * 70)
    print("SYSTEM INFORMATION")
    print("=" * 70)
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"CPU cores: {cpu_count}")
    print(f"Total RAM: {memory.total / 1024**3:.1f}GB")
    print(f"Available RAM: {memory.available / 1024**3:.1f}GB")
    print(f"Memory usage: {memory.percent:.1f}%")
    
    # Print configuration
    print("\n" + "=" * 70)
    print("RETRY CONFIGURATION")
    print("=" * 70)
    print(f"Browser retries: {SyncRetryConfig.BROWSER_MAX_RETRIES}")
    print(f"Batch retries: {SyncRetryConfig.BATCH_MAX_RETRIES}")
    print(f"Browser recycling: Every {SyncRetryConfig.BROWSER_RECYCLING_THRESHOLD} operations")
    print(f"Memory monitoring: Every {SyncRetryConfig.MEMORY_CHECK_INTERVAL} operations")
    print(f"Max memory: {SyncRetryConfig.MAX_MEMORY_USAGE_MB}MB")
    print(f"Processing delay: {SyncRetryConfig.MIN_DELAY_BETWEEN_VALUATIONS}-{SyncRetryConfig.MAX_DELAY_BETWEEN_VALUATIONS}s")

def main():
    """Main entry point"""
    global graceful_shutdown
    
    # Enhanced signal handling for reliable Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("WBAC Scraper - Synchronous Batch Processor")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print_system_info()
        process_entries_sync()
        
    except KeyboardInterrupt:
        print("\n[KEYBOARD_INTERRUPT] Ctrl+C detected. Exiting...")
        graceful_shutdown = True
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL_ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n[CLEANUP] Final cleanup...")
        force_memory_cleanup()
        print("Batch processor shutdown complete.")

if __name__ == "__main__":
    main()
