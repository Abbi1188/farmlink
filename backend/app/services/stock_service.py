"""Stock rules: reserve on order, release on reject or cancel, move to sold on completion."""
from app.core.constants import ListingStatus
from app.models.catalog import StockListing


class StockError(Exception):
    pass


def refresh_status(listing: StockListing) -> None:
    if listing.available_qty <= 0 and listing.status == ListingStatus.ACTIVE:
        listing.status = ListingStatus.SOLD_OUT
    elif listing.available_qty > 0 and listing.status == ListingStatus.SOLD_OUT:
        listing.status = ListingStatus.ACTIVE


def reserve(listing: StockListing, qty: float) -> None:
    if listing.status != ListingStatus.ACTIVE:
        raise StockError(f"{listing.product.name} is not available right now")
    if qty > listing.available_qty:
        raise StockError(f"Only {listing.available_qty:g} {listing.unit} of {listing.product.name} left")
    listing.reserved_qty += qty
    refresh_status(listing)


def release(listing: StockListing, qty: float) -> None:
    listing.reserved_qty = max(listing.reserved_qty - qty, 0.0)
    refresh_status(listing)


def commit_sale(listing: StockListing, qty: float) -> None:
    listing.reserved_qty = max(listing.reserved_qty - qty, 0.0)
    listing.sold_qty += qty
    refresh_status(listing)
