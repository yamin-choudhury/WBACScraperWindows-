"""
Database utilities for handling AWS PostgreSQL interactions
"""
import asyncpg
from .config import DB_DSN, get_ssl_context

async def connect_to_database():
    """Create a database connection with appropriate SSL context"""
    ssl_context = get_ssl_context()
    return await asyncpg.connect(dsn=DB_DSN, ssl=ssl_context)

async def insert_failure(conn, unique_id, number_plate, mileage, failure_reason):
    """Insert a record into the failed_valuations table"""
    try:
        await conn.execute(
            """
            INSERT INTO car_pipeline.failed_valuations (
                unique_id, number_plate, mileage, failure_reason, failed_at
            )
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (unique_id) DO UPDATE 
            SET number_plate = EXCLUDED.number_plate,
                mileage = EXCLUDED.mileage,
                failure_reason = EXCLUDED.failure_reason,
                failed_at = CURRENT_TIMESTAMP
            """,
            unique_id, number_plate, mileage, failure_reason
        )
        print(f"Added to failed_valuations: {unique_id}")
        return True
    except Exception as e:
        print(f"ERROR inserting failure record: {e}")
        return False

async def verify_record_exists(conn, unique_id):
    """Verify that a record exists in the valid_valuation table"""
    try:
        row = await conn.fetchrow(
            "SELECT unique_id FROM car_pipeline.valid_valuation WHERE unique_id = $1",
            unique_id
        )
        if row:
            print(f"✓ VERIFIED: Record {unique_id} exists in valid_valuation table")
            return True
        else:
            print(f"✗ ERROR: Record {unique_id} is NOT in valid_valuation table")
            return False
    except Exception as e:
        print(f"Error verifying record: {e}")
        return False

async def fetch_valuations_to_process(conn):
    """Fetch entries from the database that need to be valuated"""
    query = """
        SELECT tv.unique_id, tv.number_plate, tv.mileage, tv.ebay_url, 
               e.salvage_category
        FROM car_pipeline.to_valuate tv
        LEFT JOIN car_pipeline.enriched_ebay_listings_auction e
        ON tv.unique_id = e.unique_id;
    """
    return await conn.fetch(query)

async def insert_valuation(conn, unique_id, plate, original_mileage, valuation_number, original_valuation=None, salvage_category=None):
    """Insert a record into the valid_valuation table and delete from to_valuate"""
    try:
        async with conn.transaction():
            print(f"Inserting valuation for {plate}: £{valuation_number:.2f}")
            await conn.execute(
                """
                INSERT INTO car_pipeline.valid_valuation (
                    unique_id, number_plate, mileage, valuation, validation_date
                )
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (unique_id) DO UPDATE 
                SET number_plate = EXCLUDED.number_plate,
                    mileage = EXCLUDED.mileage,
                    valuation = EXCLUDED.valuation,
                    validation_date = EXCLUDED.validation_date
                """,
                unique_id, plate, original_mileage, valuation_number
            )
            await conn.execute("DELETE FROM car_pipeline.to_valuate WHERE unique_id = $1", unique_id)
            
            adjustment_msg = ""
            if salvage_category and salvage_category in ['CAT N', 'CAT S'] and original_valuation:
                adjustment_msg = f" (adjusted from £{original_valuation} due to {salvage_category})"
                
            print(f"DB INSERT SUCCESS: {plate} valuation: £{valuation_number:.2f}{adjustment_msg}")
            return True
    except Exception as e:
        print(f"ERROR inserting valuation: {e}")
        return False
