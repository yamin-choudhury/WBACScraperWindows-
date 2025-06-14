# Enhanced WBAC Scraper with Robust Retry Mechanism

## Overview

This enhanced WBAC scraper implements a comprehensive multi-layered retry mechanism designed to reliably process ~4000 car valuations in a single run without manual intervention. The system handles internet drops, browser timeouts, and various error conditions with intelligent recovery strategies.

## Key Features

### 🔄 Multi-Layered Retry Architecture

1. **Browser-Level Retry** (3 attempts per valuation)
   - Fresh browser instance for each retry
   - Handles network timeouts and browser crashes
   - Exponential backoff with jitter

2. **Component-Level Fallbacks**
   - Multiple selector strategies for form elements
   - JavaScript injection as backup method
   - Alternative navigation paths

3. **Batch-Level Retry** (10 attempts for entire batch)
   - Continues processing from last successful item
   - Handles database connection issues
   - Process-level error recovery

4. **Resource Management**
   - Browser recycling every 75-100 valuations
   - Memory monitoring and forced cleanup
   - Proper resource cleanup in finally blocks

### 🛡️ Anti-Detection Measures

- Random delays between valuations (2-5 seconds)
- Human-like typing speeds and mouse movements
- Browser fingerprint randomization
- Connection throttling during high-failure periods

### 📊 Comprehensive Monitoring

- Real-time progress tracking
- Success/failure rate statistics
- Memory usage monitoring
- Performance metrics and timing
- Detailed error reporting

## Quick Start

### 1. Installation

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
python -m playwright install
pip install psutil
```

### 2. Test the System

Before running the full batch, test the retry mechanism:

```bash
python test_retry_mechanism.py
```

This will verify:
- All imports work correctly
- Database connectivity
- Single plate processing
- Memory monitoring
- Retry configuration

### 3. Process All Entries (Batch Mode)

Run the enhanced batch processor:

```bash
python run_wbac_enhanced.py --batch
```

Or use the interactive menu:

```bash
python run_wbac_enhanced.py
```

### 4. Test Single Plates

Test individual plates with retry:

```bash
python run_wbac_enhanced.py --plate DF15ZXB --mileage 50000
```

## Configuration

### Retry Settings

The retry mechanism can be configured by modifying `RetryConfig` in `wbac_modules/retry_manager.py`:

```python
class RetryConfig:
    # Browser-level retry settings
    BROWSER_MAX_RETRIES = 3
    BROWSER_RETRY_DELAY_BASE = 2.0
    BROWSER_RETRY_DELAY_MAX = 30.0
    
    # Batch-level retry settings  
    BATCH_MAX_RETRIES = 10
    BATCH_RETRY_DELAY_BASE = 5.0
    BATCH_RETRY_DELAY_MAX = 120.0
    
    # Resource management
    BROWSER_RECYCLING_THRESHOLD = 75
    MEMORY_CHECK_INTERVAL = 50
    MAX_MEMORY_USAGE_MB = 2048
    
    # Processing delays
    MIN_DELAY_BETWEEN_VALUATIONS = 2.0
    MAX_DELAY_BETWEEN_VALUATIONS = 5.0
```

### Performance Optimization

For optimal performance with ~4000 entries:

1. **System Requirements**
   - 8GB+ RAM recommended
   - Stable internet connection
   - Windows 10/11 with good CPU

2. **Batch Size Management**
   - Browser recycling prevents memory leaks
   - Automatic cleanup every 50 valuations
   - Forced restart on consecutive failures

3. **Network Resilience**
   - Connection verification before operations
   - Exponential backoff for reconnection
   - Random delays to avoid detection

## Monitoring and Diagnostics

### Real-Time Status

During batch processing, you'll see:

```
=== BATCH ATTEMPT 1/10 ===
Processing 4000 entries

[1/4000] Processing AB12CDE
✓ SUCCESS: AB12CDE: £12,345.67
Memory usage: 245.3MB (3.2%)

[75/4000] Processing XY98ZAB
Browser recycling threshold reached (75)
✓ SUCCESS: XY98ZAB: £8,765.43

=== RETRY STATISTICS ===
Total attempts: 150
Successes: 148
Failures: 2
Success rate: 98.7%
Browser retries: 5
Batch retries: 0
```

### Progress Tracking

The system provides:
- Current entry being processed (X/Total)
- Success/failure counts
- Real-time success rate
- Memory usage monitoring
- Estimated completion time

### Error Handling

Common scenarios and how they're handled:

1. **Network Timeout**
   - Browser-level retry with fresh instance
   - Exponential backoff delays
   - Up to 3 attempts per valuation

2. **Car Not Found**
   - Immediate detection and logging
   - No unnecessary retries
   - Proper failure recording

3. **Memory Issues**
   - Automatic browser recycling
   - Forced garbage collection
   - Memory usage alerts

4. **Consecutive Failures**
   - Batch-level restart after 5 failures
   - Fresh browser instances
   - Extended delays between attempts

## Database Integration

The retry mechanism integrates seamlessly with your existing database:

- Reads from `car_pipeline.to_valuate`
- Successful valuations → `car_pipeline.valid_valuation`
- Failures → `car_pipeline.failed_valuations`
- Atomic transactions prevent data loss
- Automatic cleanup of processed entries

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   python test_retry_mechanism.py
   ```
   This will identify missing dependencies.

2. **Database Connection Issues**
   - Check your database credentials
   - Verify SSL configuration
   - Test connection manually

3. **Browser Issues**
   ```bash
   python -m playwright install
   ```
   Reinstall browser binaries if needed.

4. **Memory Problems**
   - Reduce `BROWSER_RECYCLING_THRESHOLD`
   - Lower `MAX_MEMORY_USAGE_MB`
   - Close other applications

### Performance Tuning

For slower systems:
- Increase delays between valuations
- Reduce browser recycling frequency
- Lower memory thresholds

For faster systems:
- Decrease retry delays
- Increase batch sizes
- Optimize memory settings

## Expected Performance

### Typical Batch Run (4000 entries)

- **Processing Rate**: ~100-150 valuations/hour
- **Success Rate**: 95%+ under normal conditions
- **Memory Usage**: 200-500MB peak
- **Total Runtime**: 24-40 hours for 4000 entries
- **Browser Restarts**: 50-75 during full run

### Failure Scenarios

The system handles:
- Temporary network outages (auto-retry)
- Browser crashes (fresh instance)
- Website changes (multiple selectors)
- Memory leaks (forced cleanup)
- Database issues (connection retry)

## Files Overview

- `wbac_modules/retry_manager.py` - Core retry mechanism
- `run_wbac_enhanced.py` - Enhanced batch runner
- `test_retry_mechanism.py` - Comprehensive test suite
- `wbac_modules/process_manager.py` - Updated with retry integration
- `wbac_modules/windows_valuation.py` - Enhanced error handling

## Support

If you encounter issues:

1. Run the test suite first
2. Check system resources
3. Review error logs
4. Adjust retry configuration if needed

The system is designed to be self-recovering and should handle most issues automatically through its multi-layered retry architecture.
