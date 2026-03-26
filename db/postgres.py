"""
PostgreSQL database connection and session management
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Database URL from environment or default to local
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://powracle:powracle@localhost:5432/powracle"
)

# Create engine
# Use NullPool for Streamlit to avoid connection pool issues with multiprocessing
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,  # Set to True for SQL debugging
)

# Session factory
SessionLocal = scoped_session(sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
))


@contextmanager
def get_db():
    """
    Context manager for database sessions.

    Usage:
        with get_db() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session():
    """
    Get a database session (for use in Streamlit callbacks).

    Remember to close the session when done:
        db = get_db_session()
        try:
            # ... use db ...
        finally:
            db.close()
    """
    return SessionLocal()


def init_db():
    """
    Initialize the database by creating all tables.
    Run this once to set up the database schema.
    """
    from models.user import Base

    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete!")


def check_connection():
    """
    Test database connection.
    Returns True if successful, False otherwise.
    """
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test connection and initialize DB
    print(f"Testing connection to: {DATABASE_URL}")
    if check_connection():
        print("✓ Database connection successful!")
        init_db()
    else:
        print("✗ Database connection failed!")
        print("\nMake sure PostgreSQL is running and DATABASE_URL is correct in .env")
        print("Example DATABASE_URL: postgresql://user:password@localhost:5432/dbname")
