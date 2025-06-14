"""
Robust retry mechanism for WBAC scraper with multi-layered retry architecture.
Implements browser-level, component-level, batch-level, and process-level resilience.
"""
import asyncio
import time
import random
import traceback
import platform
from datetime import datetime, timedelta
from typing import Optional, Callable, Any, Dict, List
import psutil
import gc

# Platform detection
IS_WINDOWS = platform.system() == 'Windows'

if IS_WINDOWS:
    from .windows_valuation import get_valuation_windows, parse_valuation, WindowsValuationError as ValuationError
else:
    from .valuation_service import process_valuation 
    from .browser_utils import parse_valuation, ValuationError

from .database_utils import (
    connect_to_database, insert_failure, verify_record_exists,
    fetch_valuations_to_process, insert_valuation
)

class RetryConfig:
    """Configuration for retry mechanisms"""
    # Browser-level retry settings
    BROWSER_MAX_RETRIES = 3
    BROWSER_RETRY_DELAY_BASE = 2.0  # Base delay in seconds
    BROWSER_RETRY_DELAY_MAX = 30.0  # Maximum delay in seconds
    
    # Batch-level retry settings  
    BATCH_MAX_RETRIES = 10
    BATCH_RETRY_DELAY_BASE = 5.0
    BATCH_RETRY_DELAY_MAX = 120.0
    
    # Resource management
    BROWSER_RECYCLING_THRESHOLD = 75  # Recycle after this many valuations
    MEMORY_CHECK_INTERVAL = 50  # Check memory every N valuations
    MAX_MEMORY_USAGE_MB = 2048  # Force cleanup if memory exceeds this
    
    # Processing delays for anti-detection
    MIN_DELAY_BETWEEN_VALUATIONS = 2.0
    MAX_DELAY_BETWEEN_VALUATIONS = 5.0
    
    # Network resilience
    CONNECTION_TIMEOUT = 30.0
    NAVIGATION_TIMEOUT = 45.0
    
    # Error thresholds
    MAX_CONSECUTIVE_FAILURES = 5
    FORCE_RESTART_THRESHOLD = 10

class RetryStatistics:
    """Track retry statistics and performance metrics"""
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0
        self.browser_retries = 0
        self.batch_retries = 0
        self.consecutive_failures = 0
        self.start_time = datetime.now()
        self.last_success_time = None
        self.valuations_processed = 0
        self.browsers_recycled = 0
        
    def record_attempt(self):
        self.total_attempts += 1
        
    def record_success(self):
        self.total_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        self.valuations_processed += 1
        
    def record_failure(self):
        self.total_failures += 1
        self.consecutive_failures += 1
        
    def record_browser_retry(self):
        self.browser_retries += 1
        
    def record_batch_retry(self):
        self.batch_retries += 1
        
    def record_browser_recycle(self):
        self.browsers_recycled += 1
        
    def should_force_restart(self) -> bool:
        return (self.consecutive_failures >= RetryConfig.MAX_CONSECUTIVE_FAILURES or
                self.total_failures >= RetryConfig.FORCE_RESTART_THRESHOLD)
    
    def get_summary(self) -> str:
        duration = datetime.now() - self.start_time
        success_rate = (self.total_successes / max(1, self.total_attempts)) * 100
        
        return (
            f"=== RETRY STATISTICS ===\n"
            f"Total attempts: {self.total_attempts}\n"
            f"Successes: {self.total_successes}\n"
            f"Failures: {self.total_failures}\n"
            f"Success rate: {success_rate:.1f}%\n"
            f"Browser retries: {self.browser_retries}\n"
            f"Batch retries: {self.batch_retries}\n"
            f"Browsers recycled: {self.browsers_recycled}\n"
            f"Consecutive failures: {self.consecutive_failures}\n"
            f"Runtime: {duration.total_seconds():.1f} seconds\n"
            f"Avg time per valuation: {duration.total_seconds() / max(1, self.valuations_processed):.1f}s\n"
        )

# Global statistics instance
retry_stats = RetryStatistics()

def exponential_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    """Calculate exponential backoff with jitter"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    # Add random jitter (±25%)
    jitter = delay * 0.25 * (random.random() * 2 - 1)
    return max(0.1, delay + jitter)

def check_memory_usage() -> Dict[str, float]:
    """Check current memory usage"""
    process = psutil.Process()
    memory_info = process.memory_info()
    return {
        'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
        'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
        'percent': process.memory_percent()
    }

def force_memory_cleanup():
    """Force garbage collection and memory cleanup"""
    gc.collect()
    if IS_WINDOWS:
        # Additional Windows-specific cleanup if needed
        try:
            import ctypes
            ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
        except:
            pass

async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    error_types: tuple = (Exception,),
    error_handler: Optional[Callable] = None,
    **kwargs
) -> Any:
    """
    Generic retry mechanism with exponential backoff
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            retry_stats.record_attempt()
            
            if IS_WINDOWS:
                # For sync functions on Windows
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            else:
                # For async functions on other platforms
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            
            retry_stats.record_success()
            return result
            
        except error_types as e:
            last_exception = e
            retry_stats.record_failure()
            
            if error_handler:
                should_retry = error_handler(e, attempt)
                if not should_retry:
                    break
            
            if attempt < max_retries:
                delay = exponential_backoff(attempt, base_delay, max_delay)
                print(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s delay. Error: {str(e)}")
                
                if IS_WINDOWS:
                    time.sleep(delay)
                else:
                    await asyncio.sleep(delay)
            else:
                print(f"Max retries ({max_retries}) exceeded")
                break
    
    # If we get here, all retries failed
    raise last_exception

async def browser_level_retry(plate: str, mileage: int) -> Optional[str]:
    """
    Browser-level retry with fresh browser instances
    """
    def error_handler(error, attempt):
        retry_stats.record_browser_retry()
        print(f"Browser-level retry {attempt + 1} for {plate}: {str(error)}")
        
        # Force memory cleanup on retry
        if attempt > 0:
            force_memory_cleanup()
        
        return True  # Always retry at browser level
    
    try:
        return await retry_with_backoff(
            get_valuation_windows if IS_WINDOWS else process_valuation,
            plate, mileage,
            max_retries=RetryConfig.BROWSER_MAX_RETRIES,
            base_delay=RetryConfig.BROWSER_RETRY_DELAY_BASE,
            max_delay=RetryConfig.BROWSER_RETRY_DELAY_MAX,
            error_types=(ValuationError, Exception),
            error_handler=error_handler
        )
    except Exception as e:
        print(f"Browser-level retry failed for {plate}: {str(e)}")
        return None

async def process_single_valuation_with_retry(row: Dict) -> tuple[bool, str]:
    """
    Process a single valuation with comprehensive retry logic
    """
    unique_id = row['unique_id']
    plate = row['number_plate']
    mileage = row['mileage'] or 0
    salvage_category = row['salvage_category']
    
    print(f"\nProcessing: {plate} (ID: {unique_id}, Mileage: {mileage})")
    
    # Check memory usage periodically
    if retry_stats.valuations_processed % RetryConfig.MEMORY_CHECK_INTERVAL == 0:
        memory_info = check_memory_usage()
        print(f"Memory usage: {memory_info['rss_mb']:.1f}MB ({memory_info['percent']:.1f}%)")
        
        if memory_info['rss_mb'] > RetryConfig.MAX_MEMORY_USAGE_MB:
            print("High memory usage detected - forcing cleanup")
            force_memory_cleanup()
    
    # Browser recycling logic
    if (retry_stats.valuations_processed > 0 and 
        retry_stats.valuations_processed % RetryConfig.BROWSER_RECYCLING_THRESHOLD == 0):
        print(f"Browser recycling threshold reached ({RetryConfig.BROWSER_RECYCLING_THRESHOLD})")
        retry_stats.record_browser_recycle()
        force_memory_cleanup()
    
    # Add random delay between valuations for anti-detection
    delay = random.uniform(
        RetryConfig.MIN_DELAY_BETWEEN_VALUATIONS,
        RetryConfig.MAX_DELAY_BETWEEN_VALUATIONS
    )
    if IS_WINDOWS:
        time.sleep(delay)
    else:
        await asyncio.sleep(delay)
    
    # Attempt to get valuation with browser-level retry
    valuation_text = await browser_level_retry(plate, mileage)
    
    if not valuation_text:
        error_msg = "Car not found or valuation retrieval failed after all retries"
        print(f"[FAILURE] {plate}: {error_msg}")
        return False, error_msg
    
    # Parse the valuation from text to number
    try:
        valuation_number = parse_valuation(valuation_text)
    except Exception as e:
        error_msg = f"Valuation parsing error: {str(e)}"
        print(f"[FAILURE] {plate}: {error_msg}")
        return False, error_msg
    
    if valuation_number is None or valuation_number <= 0:
        error_msg = f"Invalid valuation: '{valuation_text}'"
        print(f"[FAILURE] {plate}: {error_msg}")
        return False, error_msg
    
    # Apply salvage category adjustment if needed
    original_valuation = None
    if salvage_category in ['CAT N', 'CAT S']:
        original_valuation = valuation_number
        if salvage_category == 'CAT N':
            valuation_number = valuation_number * 0.85
            print(f"CAT N salvage: adjusted from £{original_valuation:.2f} to £{valuation_number:.2f}")
        elif salvage_category == 'CAT S':
            valuation_number = valuation_number * 0.70
            print(f"CAT S salvage: adjusted from £{original_valuation:.2f} to £{valuation_number:.2f}")
    
    print(f"[SUCCESS] {plate}: £{valuation_number:.2f}")
    return True, f"Success: £{valuation_number:.2f}"

async def batch_level_retry(rows: List[Dict]) -> tuple[int, int]:
    """
    Batch-level retry that processes all entries with resilience
    """
    success_count = 0
    failure_count = 0
    conn = None
    
    try:
        conn = await connect_to_database()
        
        for i, row in enumerate(rows):
            unique_id = row['unique_id']
            plate = row['number_plate']
            mileage = row['mileage'] or 0
            salvage_category = row['salvage_category']
            
            print(f"\n[{i+1}/{len(rows)}] Processing {plate}")
            
            # Check if we should force restart
            if retry_stats.should_force_restart():
                print(f"Force restart threshold reached - stopping batch")
                break
            
            try:
                success, result_msg = await process_single_valuation_with_retry(row)
                
                if success:
                    # Extract valuation from success message
                    valuation_match = result_msg.replace('Success: £', '').replace(',', '')
                    valuation_number = float(valuation_match)
                    
                    # Determine original valuation for salvage categories
                    original_valuation = None
                    if salvage_category in ['CAT N', 'CAT S']:
                        if salvage_category == 'CAT N':
                            original_valuation = valuation_number / 0.85
                        elif salvage_category == 'CAT S':
                            original_valuation = valuation_number / 0.70
                    
                    # Insert into valid_valuation table
                    insert_success = await insert_valuation(
                        conn, unique_id, plate, mileage, valuation_number,
                        original_valuation, salvage_category
                    )
                    
                    if insert_success:
                        success_count += 1
                        await verify_record_exists(conn, unique_id)
                    else:
                        await insert_failure(conn, unique_id, plate, mileage, "Database insertion failed")
                        failure_count += 1
                else:
                    # Insert failure record
                    await insert_failure(conn, unique_id, plate, mileage, result_msg)
                    failure_count += 1
                    
            except Exception as e:
                print(f"Unexpected error processing {plate}: {str(e)}")
                traceback.print_exc()
                await insert_failure(conn, unique_id, plate, mileage, f"Unexpected error: {str(e)}")
                failure_count += 1
    
    finally:
        if conn:
            await conn.close()
    
    return success_count, failure_count

async def process_all_entries_with_retry():
    """
    Main entry point for batch processing with comprehensive retry logic
    """
    print(f"=== WBAC SCRAPER WITH RETRY MECHANISM ===")
    print(f"Platform: {platform.system()}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Reset statistics
    retry_stats.reset()
    
    conn = None
    total_success = 0
    total_failure = 0
    
    try:
        # Fetch all entries to process
        conn = await connect_to_database()
        rows = await fetch_valuations_to_process(conn)
        await conn.close()
        conn = None
        
        print(f"Found {len(rows)} entries to valuate")
        
        if not rows:
            print("No entries to process")
            return 0, 0
        
        # Process in batches with retry
        batch_attempt = 0
        remaining_rows = rows
        
        while remaining_rows and batch_attempt < RetryConfig.BATCH_MAX_RETRIES:
            batch_attempt += 1
            print(f"\n=== BATCH ATTEMPT {batch_attempt}/{RetryConfig.BATCH_MAX_RETRIES} ===")
            print(f"Processing {len(remaining_rows)} entries")
            
            try:
                success_count, failure_count = await batch_level_retry(remaining_rows)
                total_success += success_count
                total_failure += failure_count
                
                print(f"Batch {batch_attempt} results: {success_count} success, {failure_count} failed")
                
                # If we processed everything successfully, we're done
                if success_count + failure_count >= len(remaining_rows):
                    break
                
                # Calculate remaining entries (those that weren't processed due to errors)
                processed_count = success_count + failure_count
                remaining_rows = remaining_rows[processed_count:]
                
                if remaining_rows:
                    retry_stats.record_batch_retry()
                    delay = exponential_backoff(
                        batch_attempt - 1,
                        RetryConfig.BATCH_RETRY_DELAY_BASE,
                        RetryConfig.BATCH_RETRY_DELAY_MAX
                    )
                    print(f"Retrying batch in {delay:.1f} seconds...")
                    if IS_WINDOWS:
                        time.sleep(delay)
                    else:
                        await asyncio.sleep(delay)
                
            except Exception as e:
                print(f"Batch attempt {batch_attempt} failed: {str(e)}")
                traceback.print_exc()
                
                if batch_attempt < RetryConfig.BATCH_MAX_RETRIES:
                    delay = exponential_backoff(
                        batch_attempt - 1,
                        RetryConfig.BATCH_RETRY_DELAY_BASE,
                        RetryConfig.BATCH_RETRY_DELAY_MAX
                    )
                    print(f"Retrying entire batch in {delay:.1f} seconds...")
                    if IS_WINDOWS:
                        time.sleep(delay)
                    else:
                        await asyncio.sleep(delay)
        
        # Final statistics
        duration = datetime.now() - retry_stats.start_time
        print(f"\n=== FINAL RESULTS ===")
        print(f"Total processed: {total_success + total_failure}")
        print(f"Successful: {total_success}")
        print(f"Failed: {total_failure}")
        print(f"Total runtime: {duration.total_seconds():.1f} seconds")
        print(f"Average time per valuation: {duration.total_seconds() / max(1, total_success + total_failure):.1f}s")
        print(retry_stats.get_summary())
        
        return total_success, total_failure
        
    except Exception as e:
        print(f"Critical error in process_all_entries_with_retry: {str(e)}")
        traceback.print_exc()
        return total_success, total_failure
    finally:
        if conn:
            await conn.close()
