"""
Setup script for user accounts & personalization feature

Run this once to set up the database and install dependencies.
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("=" * 60)
    print("Colorado Powracle - User Accounts Setup")
    print("=" * 60)
    print()

    # Step 1: Install Python dependencies
    print("Step 1: Installing Python dependencies...")
    dependencies = [
        "sqlalchemy",
        "psycopg2-binary",  # PostgreSQL driver
        "bcrypt",  # Password hashing
    ]

    for dep in dependencies:
        print(f"  Installing {dep}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

    print("[OK] Dependencies installed!\n")

    # Step 2: Check for PostgreSQL
    print("Step 2: Database Setup")
    print("-" * 60)
    print("You need PostgreSQL installed and running.")
    print()
    print("Options:")
    print("  A. Local PostgreSQL (Docker recommended)")
    print("  B. Cloud PostgreSQL (Supabase, AWS RDS, etc.)")
    print()
    print("Docker Quick Start:")
    print("  docker run --name powracle-db \\")
    print("    -e POSTGRES_PASSWORD=powracle \\")
    print("    -e POSTGRES_USER=powracle \\")
    print("    -e POSTGRES_DB=powracle \\")
    print("    -p 5432:5432 -d postgres")
    print()

    response = input("Have you set up PostgreSQL? (y/n): ").lower()
    if response != 'y':
        print("\nPlease set up PostgreSQL first, then run this script again.")
        return

    # Step 3: Configure DATABASE_URL
    print("\nStep 3: Database Connection")
    print("-" * 60)
    print("Add this line to your .env file:")
    print()
    print('  DATABASE_URL=postgresql://powracle:powracle@localhost:5432/powracle')
    print()
    print("Format: postgresql://user:password@host:port/database")
    print()

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            if 'DATABASE_URL' in content:
                print("[OK] DATABASE_URL found in .env")
            else:
                print("[WARNING] DATABASE_URL not found in .env")
                db_url = input("\nEnter DATABASE_URL (or press Enter for default): ").strip()
                if not db_url:
                    db_url = "postgresql://powracle:powracle@localhost:5432/powracle"

                with open(env_path, 'a') as f:
                    f.write(f"\n\n# User Accounts Database\nDATABASE_URL={db_url}\n")
                print("[OK] DATABASE_URL added to .env")
    else:
        print("[WARNING] .env file not found!")
        db_url = input("Enter DATABASE_URL: ").strip()
        if db_url:
            with open(env_path, 'w') as f:
                f.write(f"# User Accounts Database\nDATABASE_URL={db_url}\n")
            print("[OK] .env file created with DATABASE_URL")

    # Step 4: Initialize database
    print("\nStep 4: Initializing Database")
    print("-" * 60)

    try:
        from db.postgres import check_connection, init_db

        if check_connection():
            print("[OK] Database connection successful!")
            print("\nCreating tables...")
            init_db()
            print("[OK] Database tables created!")

            # Load ticket prices
            print("\nLoading resort ticket prices...")
            load_ticket_prices()
            print("[OK] Ticket prices loaded!")

        else:
            print("[ERROR] Database connection failed!")
            print("\nTroubleshooting:")
            print("  1. Check PostgreSQL is running")
            print("  2. Verify DATABASE_URL in .env is correct")
            print("  3. Check firewall/network settings")
            return

    except Exception as e:
        print(f"[ERROR] {e}")
        return

    # Step 5: Done!
    print("\n" + "=" * 60)
    print("[SUCCESS] Setup Complete!")
    print("=" * 60)
    print("\nYou can now run the app with user accounts enabled:")
    print("  streamlit run app.py")
    print()
    print("The app will show a login/register screen before the main UI.")
    print()


def load_ticket_prices():
    """Load resort ticket prices into database"""
    from db.postgres import get_db
    from models.user import ResortTicketPrice

    prices = [
        ('Vail', 239.00, 209.00),
        ('Breckenridge', 229.00, 199.00),
        ('Keystone', 199.00, 169.00),
        ('Beaver Creek', 249.00, 219.00),
        ('Crested Butte', 199.00, 169.00),
        ('Winter Park', 209.00, 179.00),
        ('Steamboat', 209.00, 179.00),
        ('Aspen Snowmass', 219.00, 189.00),
        ('Telluride', 189.00, 159.00),
        ('Copper Mountain', 199.00, 169.00),
        ('Arapahoe Basin', 159.00, 139.00),
        ('Loveland', 139.00, 119.00),
        ('Monarch', 109.00, 99.00),
        ('Wolf Creek', 119.00, 99.00),
        ('Eldora', 149.00, 129.00),
        ('Sunlight Mountain', 99.00, 89.00),
        ('Powderhorn', 99.00, 89.00),
        ('Silverton', 159.00, 159.00),
        ('Purgatory', 169.00, 149.00),
    ]

    season = "2024-2025"

    with get_db() as db:
        for resort_name, peak, regular in prices:
            existing = db.query(ResortTicketPrice).filter(
                ResortTicketPrice.resort_name == resort_name
            ).first()

            if not existing:
                price = ResortTicketPrice(
                    resort_name=resort_name,
                    peak_price=peak,
                    regular_price=regular,
                    season=season
                )
                db.add(price)

        db.commit()


if __name__ == "__main__":
    main()
