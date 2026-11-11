from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.catalog import Category, Product
from app.schemas.stock import CategoryOut, ProductOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()


@router.get("/products", response_model=list[ProductOut])
def products(category_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Product)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    return query.order_by(Product.name).all()
