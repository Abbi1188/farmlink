"""String constants stored in the database (plain strings keep SQLite and PostgreSQL identical)."""


class Role:
    FARMER = "farmer"
    BUYER = "buyer"
    ADMIN = "admin"


class Verification:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ListingStatus:
    ACTIVE = "active"
    PAUSED = "paused"
    SOLD_OUT = "sold_out"


class OrderStatus:
    PLACED = "placed"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    OUT_FOR_DELIVERY = "out_for_delivery"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED_DELIVERY = "failed_delivery"


class Fulfilment:
    DELIVERY = "delivery"
    PICKUP = "pickup"
