"""Upgrade an EXISTING FarmBridge database to this version. Safe to run more than once.

Run from the project root:   python database/migrate_v2.py

What it does
  * creates the new tables (otp_codes, order_events)
  * adds users.cnic (farmers give their CNIC at sign-up) with a unique index
  * adds approval_status and approval_note to stock_listings; stock that already exists stays visible (approved)
  * marks every existing farm as approved (farms no longer wait for admin approval)
  * creates the built-in admin account if there is none
A new, empty database does not need this: use init_db.py instead.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import inspect, text  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.bootstrap import ensure_default_admin  # noqa: E402


def add_column(table: str, column: str, ddl: str) -> None:
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    if column in existing:
        print(f"  {table}.{column}: already there")
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    print(f"  {table}.{column}: added")


def main() -> None:
    print(f"Database: {engine.url}")
    if not inspect(engine).has_table("stock_listings"):
        print("No tables yet. Run  python database/init_db.py  instead.")
        return

    Base.metadata.create_all(bind=engine)  # new tables only; existing tables are left alone
    print("Tables checked.")

    add_column("stock_listings", "approval_status", "VARCHAR(20) NOT NULL DEFAULT 'approved'")
    add_column("stock_listings", "approval_note", "VARCHAR(255)")
    add_column("users", "cnic", "VARCHAR(15)")
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cnic ON users (cnic)"))
    print("  users.cnic: unique index ready")

    with engine.begin() as conn:
        n = conn.execute(text("UPDATE farm_profiles SET verification_status = 'approved' WHERE verification_status <> 'approved'")).rowcount
    print(f"Farms set to approved: {n}")

    db = SessionLocal()
    try:
        if ensure_default_admin(db):
            print("Default admin created: 03000000000 / admin123 (change ADMIN_PASSWORD in backend/.env)")
        else:
            print("Admin account already exists.")
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()
