# WBAC Driver v2

This is a modular Windows-compatible version of the WeBuyAnyCar valuation system originally developed in Jupyter Notebook. The system processes vehicle data from a PostgreSQL database, obtains valuations from webuyanycar.com, and updates the database accordingly.

## Setup Instructions for Windows

### 1. Install Required Packages

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for web automation)
python -m playwright install
```

### 2. Running the Application

```powershell
# Start the application
python run_wbac.py
```

You'll be presented with a menu to either:
1. Process all database entries
2. Test a single plate

### 3. Command Line Options

You can also run the application with command line arguments:

```powershell
# Process all database entries
python run_wbac.py --batch

# Test a single license plate
python run_wbac.py --plate AB12CDE --mileage 50000

# For Windows - use the Windows-specific implementation (recommended)
python run_wbac_windows.py --plate AB12CDE --mileage 50000
```

## Project Structure

- `run_wbac.py` - Main entry point script
- `run_wbac_windows.py` - Windows-specific entry point script (uses synchronous API)
- `wbac_modules/` - Core functionality modules:
  - `config.py` - Configuration settings (DB connection, browser settings)
  - `database_utils.py` - Database connection and queries
  - `browser_utils.py` - Browser setup and utilities
  - `human_behavior.py` - Human-like behavior simulation
  - `valuation_service.py` - Core valuation process (async implementation)
  - `windows_valuation.py` - Windows-specific valuation implementation (sync)
  - `process_manager.py` - Orchestration for batch and single plate processing

## Notes

- This version maintains exactly the same database table names and row structures as the original notebook to ensure AWS compatibility.
- SSL verification is disabled for the database connection as in the original code.
- The system simulates human-like behavior to avoid bot detection.
- Windows-specific implementation (`run_wbac_windows.py`) uses Playwright's synchronous API to avoid Windows asyncio subprocess limitations.
- Platform detection automatically selects the right implementation based on your operating system.
- Screenshots are saved during the valuation process for debugging purposes.
