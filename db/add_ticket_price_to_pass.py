"""
Add day_ticket_price column to user_passes table
Run this once to update the database schema
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.postgres import get_db
from sqlalchemy import text

def add_ticket_price_column():
    """Add day_ticket_price column to user_passes table"""
    try:
        with get_db() as db:
            # Check if column already exists
            check_sql = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='user_passes' AND column_name='day_ticket_price';
            """
            result = db.execute(text(check_sql)).fetchone()

            if result:
                print("[OK] Column 'day_ticket_price' already exists")
                return True

            # Add the column
            alter_sql = """
                ALTER TABLE user_passes
                ADD COLUMN day_ticket_price NUMERIC(10, 2);
            """
            db.execute(text(alter_sql))
            db.commit()
            print("[OK] Added 'day_ticket_price' column to user_passes table")
            return True

    except Exception as e:
        print(f"[ERROR] Error adding column: {e}")
        return False

if __name__ == "__main__":
    print("Adding day_ticket_price column to user_passes table...")
    success = add_ticket_price_column()
    if success:
        print("\n[SUCCESS] Migration completed successfully!")
    else:
        print("\n[FAILED] Migration failed")
