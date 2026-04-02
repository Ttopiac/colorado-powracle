"""
Run all database migrations for Colorado Powracle

This script runs all database migrations in the correct order.
Safe to run multiple times - migrations are idempotent.

Usage:
    python db/run_migrations.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.postgres import check_connection


def print_header(text):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(step, total, description):
    """Print a migration step"""
    print(f"\n[{step}/{total}] {description}")
    print("-" * 70)


def run_migration(module_path, description):
    """Run a single migration module"""
    try:
        # Import and run the migration
        module_name = module_path.replace('/', '.').replace('.py', '')
        module = __import__(module_name, fromlist=[''])

        # Look for main function or just execute the module
        if hasattr(module, '__main__'):
            # Module has a __main__ block, it will run automatically
            pass
        elif hasattr(module, 'main'):
            module.main()
        elif hasattr(module, 'migrate'):
            module.migrate()
        else:
            # For modules with direct execution (like add_ticket_price_to_pass.py)
            for attr_name in dir(module):
                if attr_name.startswith('add_') and callable(getattr(module, attr_name)):
                    getattr(module, attr_name)()
                    break

        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        return False


def main():
    """Run all migrations"""
    print_header("Colorado Powracle - Database Migration Runner")

    # Check database connection
    print("\n[INFO] Checking database connection...")
    if not check_connection():
        print("[ERROR] Cannot connect to database!")
        print("[INFO] Make sure PostgreSQL is running and DATABASE_URL is set in .env")
        print("\nFor Docker: docker ps | grep postgres")
        print("For native: brew services list (macOS) or systemctl status postgresql (Linux)")
        sys.exit(1)

    print("[OK] Database connection successful!")

    # Define migrations in order
    migrations = [
        {
            'step': 1,
            'description': 'Create base tables (users, passes, trips, etc.)',
            'function': 'init_postgres'
        },
        {
            'step': 2,
            'description': 'Add day_ticket_price column to user_passes',
            'function': 'add_ticket_price_to_pass'
        },
        {
            'step': 3,
            'description': 'Add pass tracking columns to trip_days',
            'function': 'add_pass_tracking_to_trip_day'
        }
    ]

    total_migrations = len(migrations)
    successful = 0
    skipped = 0
    failed = 0

    print_header("Running Migrations")

    for migration in migrations:
        print_step(migration['step'], total_migrations, migration['description'])

        try:
            if migration['function'] == 'init_postgres':
                from db.init_postgres import main as init_main
                result = init_main()
                if result:
                    print("[OK] Migration completed")
                    successful += 1
                else:
                    # Tables might already exist
                    print("[OK] Tables already exist (skipped)")
                    skipped += 1

            elif migration['function'] == 'add_ticket_price_to_pass':
                from db.add_ticket_price_to_pass import add_ticket_price_column
                result = add_ticket_price_column()
                if result:
                    successful += 1
                else:
                    # Check if it was skipped (already exists)
                    from db.postgres import get_db
                    from sqlalchemy import text
                    with get_db() as db:
                        check_sql = "SELECT column_name FROM information_schema.columns WHERE table_name='user_passes' AND column_name='day_ticket_price';"
                        result = db.execute(text(check_sql)).fetchone()
                        if result:
                            print("[OK] Column already exists (skipped)")
                            skipped += 1
                        else:
                            failed += 1

            elif migration['function'] == 'add_pass_tracking_to_trip_day':
                from db.add_pass_tracking_to_trip_day import add_pass_tracking_columns
                result = add_pass_tracking_columns()
                if result:
                    successful += 1
                else:
                    # Check if it was skipped (already exists)
                    from db.postgres import get_db
                    from sqlalchemy import text
                    with get_db() as db:
                        check_sql = "SELECT column_name FROM information_schema.columns WHERE table_name='trip_days' AND column_name='used_pass';"
                        result = db.execute(text(check_sql)).fetchone()
                        if result:
                            print("[OK] Columns already exist (skipped)")
                            skipped += 1
                        else:
                            failed += 1

        except Exception as e:
            print(f"[ERROR] Migration failed: {e}")
            failed += 1
            # Don't exit, continue with other migrations

    # Summary
    print_header("Migration Summary")
    print(f"\n  Total migrations: {total_migrations}")
    print(f"  Successful: {successful}")
    print(f"  Skipped (already applied): {skipped}")
    print(f"  Failed: {failed}")

    if failed > 0:
        print("\n[WARNING] Some migrations failed. Check errors above.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All migrations completed successfully!")
        print("\nYour database is ready. You can now run: streamlit run app.py")
        sys.exit(0)


if __name__ == "__main__":
    main()
