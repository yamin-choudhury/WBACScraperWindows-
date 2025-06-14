"""
Enhanced WBAC Scraper with Robust Retry Mechanism
Designed to reliably process ~4000 car valuations in a single run
Implements multi-layered retry architecture with browser recycling and anti-detection measures
"""
import os
import sys
import asyncio
import traceback
import argparse
import platform
import signal
from datetime import datetime

# Ensure we're using the correct event loop policy for Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import required modules
try:
    from wbac_modules.retry_manager import process_all_entries_with_retry, retry_stats, RetryConfig
    from wbac_modules.process_manager import process_single_plate
    from playwright.sync_api import sync_playwright
    import psutil
except ImportError as e:
    print(f"ERROR: Missing required package - {e}")
    print("\nPlease install required packages using:")
    print("pip install -r requirements.txt")
    print("python -m playwright install")
    print("pip install psutil")
    sys.exit(1)

class EnhancedWBACProcessor:
    """Enhanced WBAC processor with comprehensive monitoring and control"""
    
    def __init__(self):
        self.start_time = None
        self.interrupted = False
        self.total_entries = 0
        
    def setup_signal_handlers(self):
        """Setup graceful interrupt handling"""
        def signal_handler(signum, frame):
            print(f"\n{'='*50}")
            print("INTERRUPT SIGNAL RECEIVED")
            print(f"{'='*50}")
            self.interrupted = True
            self.print_current_status()
            print("\nGracefully shutting down...")
            print("Current batch will complete before stopping.")
            
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def print_current_status(self):
        """Print current processing status"""
        if self.start_time:
            duration = datetime.now() - self.start_time
            print(f"\n{'='*50}")
            print("CURRENT STATUS")
            print(f"{'='*50}")
            print(f"Runtime: {duration.total_seconds():.1f} seconds")
            print(f"Entries processed: {retry_stats.valuations_processed}")
            print(f"Success rate: {(retry_stats.total_successes / max(1, retry_stats.total_attempts)) * 100:.1f}%")
            print(f"Browser retries: {retry_stats.browser_retries}")
            print(f"Batch retries: {retry_stats.batch_retries}")
            print(f"Consecutive failures: {retry_stats.consecutive_failures}")
            
            # Memory usage
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                print(f"Memory usage: {memory_mb:.1f}MB")
            except:
                pass
            print(f"{'='*50}")

    def print_system_info(self):
        """Print system information and configuration"""
        print(f"\n{'='*60}")
        print("ENHANCED WBAC SCRAPER WITH RETRY MECHANISM")
        print(f"{'='*60}")
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {platform.python_version()}")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\nRETRY CONFIGURATION:")
        print(f"  Browser retries: {RetryConfig.BROWSER_MAX_RETRIES}")
        print(f"  Batch retries: {RetryConfig.BATCH_MAX_RETRIES}")
        print(f"  Browser recycling: Every {RetryConfig.BROWSER_RECYCLING_THRESHOLD} valuations")
        print(f"  Memory check: Every {RetryConfig.MEMORY_CHECK_INTERVAL} valuations")
        print(f"  Max memory usage: {RetryConfig.MAX_MEMORY_USAGE_MB}MB")
        print(f"  Anti-detection delay: {RetryConfig.MIN_DELAY_BETWEEN_VALUATIONS}-{RetryConfig.MAX_DELAY_BETWEEN_VALUATIONS}s")
        
        # System resources
        try:
            print(f"\nSYSTEM RESOURCES:")
            print(f"  CPU cores: {psutil.cpu_count()}")
            print(f"  Total RAM: {psutil.virtual_memory().total / 1024**3:.1f}GB")
            print(f"  Available RAM: {psutil.virtual_memory().available / 1024**3:.1f}GB")
        except:
            pass
        
        print(f"{'='*60}")

    async def run_batch_processing(self):
        """Run the enhanced batch processing with comprehensive monitoring"""
        self.start_time = datetime.now()
        self.setup_signal_handlers()
        self.print_system_info()
        
        try:
            # Estimate total entries
            from wbac_modules.database_utils import connect_to_database, fetch_valuations_to_process
            conn = await connect_to_database()
            rows = await fetch_valuations_to_process(conn)
            await conn.close()
            
            self.total_entries = len(rows)
            print(f"\nFound {self.total_entries} entries to process")
            
            if self.total_entries == 0:
                print("No entries to process. Exiting.")
                return 0, 0
            
            # Estimate completion time (rough estimate: 30 seconds per valuation)
            estimated_hours = (self.total_entries * 30) / 3600
            print(f"Estimated completion time: {estimated_hours:.1f} hours")
            
            print(f"\n{'='*50}")
            print("STARTING BATCH PROCESSING")
            print(f"{'='*50}")
            
            # Run the enhanced processing
            success_count, failure_count = await process_all_entries_with_retry()
            
            # Final report
            duration = datetime.now() - self.start_time
            total_processed = success_count + failure_count
            success_rate = (success_count / max(1, total_processed)) * 100
            avg_time_per_valuation = duration.total_seconds() / max(1, total_processed)
            
            print(f"\n{'='*60}")
            print("FINAL PROCESSING REPORT")
            print(f"{'='*60}")
            print(f"Total entries found: {self.total_entries}")
            print(f"Entries processed: {total_processed}")
            print(f"Successful: {success_count}")
            print(f"Failed: {failure_count}")
            print(f"Success rate: {success_rate:.1f}%")
            print(f"Total runtime: {duration.total_seconds():.1f} seconds ({duration.total_seconds()/3600:.1f} hours)")
            print(f"Average time per valuation: {avg_time_per_valuation:.1f} seconds")
            print(f"Processing rate: {3600/avg_time_per_valuation:.1f} valuations/hour")
            
            print(f"\nRETRY STATISTICS:")
            print(f"  Browser retries: {retry_stats.browser_retries}")
            print(f"  Batch retries: {retry_stats.batch_retries}")
            print(f"  Browsers recycled: {retry_stats.browsers_recycled}")
            print(f"  Consecutive failures: {retry_stats.consecutive_failures}")
            
            if total_processed < self.total_entries:
                remaining = self.total_entries - total_processed
                print(f"\nWARNING: {remaining} entries were not processed")
                print("You may need to run the scraper again to complete all entries")
            
            print(f"{'='*60}")
            
            return success_count, failure_count
            
        except KeyboardInterrupt:
            print("\n\nBatch processing interrupted by user")
            self.print_current_status()
            return retry_stats.total_successes, retry_stats.total_failures
        except Exception as e:
            print(f"\nCritical error in batch processing: {str(e)}")
            traceback.print_exc()
            self.print_current_status()
            return retry_stats.total_successes, retry_stats.total_failures

    async def test_single_plate(self, plate: str, mileage: int):
        """Test a single plate with the enhanced retry mechanism"""
        print(f"\n{'='*50}")
        print(f"TESTING SINGLE PLATE: {plate}")
        print(f"{'='*50}")
        
        self.start_time = datetime.now()
        
        try:
            result = await process_single_plate(plate, mileage)
            
            duration = datetime.now() - self.start_time
            print(f"\nTest completed in {duration.total_seconds():.1f} seconds")
            
            if result:
                print(f"✓ SUCCESS: Valuation retrieved for {plate}")
            else:
                print(f"✗ FAILED: Could not retrieve valuation for {plate}")
            
            return result
            
        except Exception as e:
            print(f"✗ ERROR testing {plate}: {str(e)}")
            traceback.print_exc()
            return None

def check_requirements():
    """Check if all required packages are installed"""
    try:
        import playwright
        import asyncpg
        import psutil
        return True
    except ImportError as e:
        print(f"ERROR: Missing required package - {e}")
        print("\nPlease install required packages using:")
        print("pip install -r requirements.txt")
        print("python -m playwright install")
        print("pip install psutil")
        return False

async def main():
    """Main entry point with enhanced command line interface"""
    if not check_requirements():
        return
    
    processor = EnhancedWBACProcessor()
    
    parser = argparse.ArgumentParser(
        description="Enhanced WeBuyAnyCar (WBAC) Valuation System with Robust Retry Mechanism",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_wbac_enhanced.py --batch                    # Process all entries
  python run_wbac_enhanced.py --plate DF15ZXB           # Test single plate
  python run_wbac_enhanced.py --plate DF15ZXB --mileage 50000  # Test with specific mileage
        """
    )
    parser.add_argument("--plate", help="Process a single license plate for testing")
    parser.add_argument("--mileage", type=int, help="Vehicle mileage for single plate testing")
    parser.add_argument("--batch", action="store_true", help="Run enhanced batch processing from database")
    parser.add_argument("--status", action="store_true", help="Show current system status")
    
    args = parser.parse_args()
    
    # Handle status check
    if args.status:
        processor.print_system_info()
        return
    
    # Display interactive menu if no arguments provided
    if not (args.plate or args.batch):
        print(f"\n{'='*60}")
        print("ENHANCED WBAC VALUATION SYSTEM")
        print(f"{'='*60}")
        print("1. Process all entries from database (BATCH MODE)")
        print("2. Test a single plate")
        print("3. Show system status")
        print("0. Exit")
        print(f"{'='*60}")
        
        choice = input("Enter your choice: ")
        
        if choice == "1":
            await processor.run_batch_processing()
        elif choice == "2":
            plate = input("Enter license plate: ").strip().upper()
            mileage_input = input("Enter mileage (default 100000): ").strip()
            try:
                mileage = int(mileage_input) if mileage_input else 100000
                await processor.test_single_plate(plate, mileage)
            except ValueError:
                print("Invalid mileage value. Please enter a number.")
        elif choice == "3":
            processor.print_system_info()
        elif choice == "0":
            print("Exiting...")
            return
        else:
            print("Invalid choice.")
            return
    
    # Process command line arguments
    elif args.plate:
        mileage = args.mileage if args.mileage is not None else 100000
        await processor.test_single_plate(args.plate.strip().upper(), mileage)
    elif args.batch:
        await processor.run_batch_processing()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        traceback.print_exc()
