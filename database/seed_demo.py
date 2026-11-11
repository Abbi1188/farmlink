"""Add demo users and stock so you can try the app straight away.

Run after init_db.py:  python database/seed_demo.py
DEVELOPMENT ONLY: these accounts use well-known passwords. Never run this on a live server.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import models  # noqa: E402,F401
from app.core.constants import Role, Verification  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.catalog import Product, StockListing  # noqa: E402
from app.models.farm import FarmProfile  # noqa: E402
from app.models.user import User  # noqa: E402


def get_or_create_user(db, name, phone, password, role):
    user = db.query(User).filter_by(phone=phone).first()
    if not user:
        user = User(name=name, phone=phone, password_hash=hash_password(password), role=role)
        db.add(user)
        db.flush()
    return user


def main() -> None:
    db = SessionLocal()
    try:
        get_or_create_user(db, "Admin", "03000000000", "admin123", Role.ADMIN)
        get_or_create_user(db, "Demo Buyer", "03001234567", "buyer123", Role.BUYER)
        farmer = get_or_create_user(db, "Demo Farmer", "03007654321", "farmer123", Role.FARMER)

        farm = db.query(FarmProfile).filter_by(owner_id=farmer.id).first()
        if not farm:
            farm = FarmProfile(
                owner_id=farmer.id,
                farm_name="Green Valley Farm",
                description="Family farm supplying fresh dairy and grains.",
                verification_status=Verification.APPROVED,
                delivery_enabled=True,
                pickup_enabled=True,
                delivery_radius_km=15,
                delivery_fee=150,
                min_order=500,
                pickup_hours="9am - 6pm",
                address_text="Charsadda Road, Peshawar",
                city="Peshawar",
                district="Peshawar",
                province="Khyber Pakhtunkhwa",
                latitude=34.0151,
                longitude=71.5249,
            )
            db.add(farm)
            db.flush()

        if not db.query(StockListing).filter_by(farm_id=farm.id).first():
            today = date.today()
            demo = [
                ("Milk", 40, "litre", 180, 2, None),
                ("Desi ghee", 15, "kg", 2400, 60, None),
                ("Wheat", 200, "kg", 110, 30, None),
            ]
            for name, qty, unit, price, shelf_days, origin in demo:
                product = db.query(Product).filter_by(name=name).first()
                if not product:
                    continue  # run init_db.py first
                db.add(
                    StockListing(
                        farm_id=farm.id,
                        product_id=product.id,
                        total_qty=qty,
                        unit=unit,
                        price_per_unit=price,
                        is_organic=True,
                        harvest_date=today,
                        expiry_date=today + timedelta(days=shelf_days),
                        address_text=farm.address_text,
                        city=farm.city,
                        district=farm.district,
                        province=farm.province,
                        latitude=farm.latitude,
                        longitude=farm.longitude,
                        origin_tag=origin or "Peshawar",
                    )
                )
        db.commit()
        print("Demo data added.")
        print("  Admin : 03000000000 / admin123")
        print("  Farmer: 03007654321 / farmer123")
        print("  Buyer : 03001234567 / buyer123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
