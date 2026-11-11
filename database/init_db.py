"""Create all tables and the starting product catalogue.

Run from the project root:  python database/init_db.py
Safe to run more than once.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.catalog import Category, Product  # noqa: E402

CATALOGUE = {
    "Grains": [("Wheat", "kg"), ("Rice", "kg"), ("Maize", "kg"), ("Lentils", "kg")],
    "Dairy": [("Milk", "litre"), ("Yogurt", "kg"), ("Butter", "kg"), ("Desi ghee", "kg"), ("Cheese", "kg")],
    "Vegetables": [("Tomato", "kg"), ("Onion", "kg"), ("Potato", "kg")],
    "Fruits": [("Apple", "kg"), ("Orange", "kg")],
    "Eggs": [("Desi eggs", "dozen")],
    "Honey": [("Honey", "kg")],
}


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for category_name, products in CATALOGUE.items():
            category = db.query(Category).filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name)
                db.add(category)
                db.flush()
            for name, unit in products:
                if not db.query(Product).filter_by(name=name).first():
                    db.add(Product(name=name, category_id=category.id, default_unit=unit))
        db.commit()
        print(f"Database ready: {engine.url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
