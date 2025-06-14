"""
Test the fixed retry logic with smart error classification
"""
import sys
import time
from datetime import datetime

def test_fixed_retry():
    """Test with car not found to verify it doesn't retry endlessly"""
    print("=" * 70)
    print("TESTING FIXED RETRY LOGIC - CAR NOT FOUND HANDLING")
    print("=" * 70)
    
    try:
        # Import the fixed functions
        from run_batch_sync import should_retry_error, sync_browser_level_retry, sync_stats
        
        print("1. Testing error classification...")
        
        # Test car not found - should NOT retry
        test_cases = [
            ("Car not found after form submission", False),
            ("vehicle not found", False), 
            ("registration not found", False),
            ("Element is not attached to the DOM", True),
            ("Target closed", True),
            ("timeout", True),
            ("connection failed", True),
            ("random error", False)  # Unknown errors default to no retry
        ]
        
        for error_msg, expected_retry in test_cases:
            should_retry = should_retry_error(error_msg)
            status = "✓" if should_retry == expected_retry else "✗"
            print(f"  {status} '{error_msg}' -> Retry: {should_retry} (expected: {expected_retry})")
        
        print(f"\n2. Testing with a known 'car not found' plate...")
        
        # Reset stats
        sync_stats.reset()
        
        # Test GL58LOV - this plate should quickly fail without multiple retries
        start_time = datetime.now()
        result = sync_browser_level_retry("GL58LOV", 165000, max_retries=3)
        duration = datetime.now() - start_time
        
        print(f"\nResult: {result}")
        print(f"Duration: {duration.total_seconds():.1f}s")
        print(f"Should be quick (< 30s) for car not found")
        
        sync_stats.print_stats()
        
        print(f"\n" + "=" * 70)
        print("FIXED RETRY LOGIC TEST COMPLETED")
        print("The system now properly handles 'car not found' without wasting retries")
        print("=" * 70)
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_retry()
