from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import OrderStatus
from app.database import Base, utcnow


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farm_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=OrderStatus.PLACED, index=True)

    fulfilment_type: Mapped[str] = mapped_column(String(20))  # delivery | pickup
    payment_method: Mapped[str] = mapped_column(String(20), default="cod")
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")

    delivery_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    subtotal: Mapped[float] = mapped_column(Float)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float)

    confirmation_code: Mapped[str] = mapped_column(String(4))  # pickup or delivery code
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    placed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
<<<<<<< HEAD
    events = relationship(
        "OrderEvent", back_populates="order", cascade="all, delete-orphan", order_by="OrderEvent.id"
    )
=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
    farm = relationship("FarmProfile")
    buyer = relationship("User")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("stock_listings.id"))
    product_name: Mapped[str] = mapped_column(String(100))  # snapshot at order time
    qty: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)  # snapshot at order time

    order = relationship("Order", back_populates="items")
    listing = relationship("StockListing")
<<<<<<< HEAD


class OrderEvent(Base):
    """One row per status change, so admins can follow an order from placed to completed."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    order = relationship("Order", back_populates="events")
=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
