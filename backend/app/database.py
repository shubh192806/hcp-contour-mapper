"""
Database engine + session configuration.

Uses SQLite by default (zero setup, ships with Python) so the project runs
immediately after `pip install -r requirements.txt`. Swap SQLALCHEMY_DATABASE_URL
for a Postgres DSN later without touching anything else in the app.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hcp_mapper.db")
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_light_migrations():
    """
    Additive-only SQLite migration: adds any column that's in the model but
    missing from an existing database file, so upgrading the code doesn't
    require deleting a database that already has real project data in it.
    Safe by construction — only ever ADDs nullable columns, never drops or
    alters existing ones. Not a replacement for a real migration tool if
    this project ever needs one (e.g. after switching to Postgres); it's
    intentionally just enough for a single-developer SQLite project.
    """
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return  # Postgres etc. — assume a real migration workflow is in place

    expected = {
        "survey_sessions": [("photo_filename", "VARCHAR")],
        "readings": [("description", "VARCHAR")],
    }
    with engine.connect() as conn:
        for table, columns in expected.items():
            info_rows = list(conn.execute(text(f"PRAGMA table_info({table})")))
            if not info_rows:
                continue  # table doesn't exist yet — create_all() will make it with every column already present
            existing = {row[1] for row in info_rows}
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
