"""
Initialize PostgreSQL database tables for Colorado Powracle user accounts

Creates all tables needed for:
- User authentication
- Season passes
- Trip planning
- ROI tracking
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.postgres import init_db


def main():
    """Initialize database tables"""
    print("Initializing PostgreSQL database...")
    try:
        init_db()
        print("[OK] Database initialized successfully!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
