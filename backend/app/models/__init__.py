"""Importing every model here registers all tables on Base.metadata."""
from app.models.catalog import Category, Product, StockListing  # noqa: F401
from app.models.farm import FarmProfile  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.order import Order, OrderEvent, OrderItem  # noqa: F401
from app.models.otp import OtpCode  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.user import User  # noqa: F401
