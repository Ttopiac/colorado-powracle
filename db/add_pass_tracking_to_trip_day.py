"""
Add pass tracking columns to trip_days table
Run this once to update the database schema
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.postgres import get_db
from sqlalchemy import text

def add_pass_tracking_columns():
    """Add used_pass, pass_used_id, and day_ticket_cost columns to trip_days table"""
    try:
        with get_db() as db:
            # Check if columns already exist
            check_sql = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='trip_days' AND column_name IN ('used_pass', 'pass_used_id', 'day_ticket_cost');
            """
            result = db.execute(text(check_sql)).fetchall()
            existing_cols = [row[0] for row in result]

            if 'used_pass' in existing_cols and 'pass_used_id' in existing_cols and 'day_ticket_cost' in existing_cols:
                print("[OK] All columns already exist")
                return True

            # Add the columns
            if 'used_pass' not in existing_cols:
                db.execute(text("ALTER TABLE trip_days ADD COLUMN used_pass BOOLEAN DEFAULT TRUE;"))
                print("[OK] Added 'used_pass' column")

            if 'pass_used_id' not in existing_cols:
                db.execute(text("""
                    ALTER TABLE trip_days
                    ADD COLUMN pass_used_id INTEGER,
                    ADD CONSTRAINT fk_pass_used FOREIGN KEY (pass_used_id)
                        REFERENCES user_passes(user_pass_id) ON DELETE SET NULL;
                """))
                print("[OK] Added 'pass_used_id' column with foreign key")

            if 'day_ticket_cost' not in existing_cols:
                db.execute(text("ALTER TABLE trip_days ADD COLUMN day_ticket_cost NUMERIC(10, 2);"))
                print("[OK] Added 'day_ticket_cost' column")

            db.commit()
            return True

    except Exception as e:
        print(f"[ERROR] Error adding columns: {e}")
        return False

if __name__ == "__main__":
    print("Adding pass tracking columns to trip_days table...")
    success = add_pass_tracking_columns()
    if success:
        print("\n[SUCCESS] Migration completed successfully!")
    else:
        print("\n[FAILED] Migration failed")
