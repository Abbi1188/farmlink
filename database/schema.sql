-- FarmLink reference schema (PostgreSQL).
-- The app creates the same tables from backend/app/models, so you do not need to run
-- this file for development. Use it as documentation, or to build PostgreSQL by hand.
-- Statuses are stored as plain text; allowed values are listed in comments.

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    phone         VARCHAR(20)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'buyer',   -- farmer | buyer | admin
    language      VARCHAR(10)  NOT NULL DEFAULT 'en',      -- en | ur | ps
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE farm_profiles (
    id                  SERIAL PRIMARY KEY,
    owner_id            INTEGER NOT NULL UNIQUE REFERENCES users(id),
    farm_name           VARCHAR(150) NOT NULL,
    description         TEXT,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    delivery_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    pickup_enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    delivery_radius_km  DOUBLE PRECISION NOT NULL DEFAULT 10,
    delivery_fee        DOUBLE PRECISION NOT NULL DEFAULT 0,
    min_order           DOUBLE PRECISION NOT NULL DEFAULT 0,
    pickup_hours        VARCHAR(100),
    address_text        VARCHAR(255) NOT NULL,
    city                VARCHAR(80)  NOT NULL,
    district            VARCHAR(80)  NOT NULL,
    province            VARCHAR(80)  NOT NULL,
    latitude            DOUBLE PRECISION NOT NULL,
    longitude           DOUBLE PRECISION NOT NULL
);

CREATE TABLE categories (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(80) NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES categories(id)
);

CREATE TABLE products (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL UNIQUE,
    category_id  INTEGER NOT NULL REFERENCES categories(id),
    default_unit VARCHAR(20) NOT NULL DEFAULT 'kg'
);

CREATE TABLE stock_listings (
    id             SERIAL PRIMARY KEY,
    farm_id        INTEGER NOT NULL REFERENCES farm_profiles(id),
    product_id     INTEGER NOT NULL REFERENCES products(id),
    total_qty      DOUBLE PRECISION NOT NULL CHECK (total_qty > 0),
    reserved_qty   DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (reserved_qty >= 0),
    sold_qty       DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (sold_qty >= 0),
    unit           VARCHAR(20) NOT NULL,
    price_per_unit DOUBLE PRECISION NOT NULL CHECK (price_per_unit > 0),
    is_organic     BOOLEAN NOT NULL DEFAULT FALSE,           -- self-declared
    harvest_date   DATE,
    expiry_date    DATE,
    address_text   VARCHAR(255) NOT NULL,
    city           VARCHAR(80)  NOT NULL,
    district       VARCHAR(80)  NOT NULL,
    province       VARCHAR(80)  NOT NULL,
    latitude       DOUBLE PRECISION NOT NULL,
    longitude      DOUBLE PRECISION NOT NULL,
    origin_tag     VARCHAR(80),                              -- regional origin, e.g. Swat
    status         VARCHAR(20) NOT NULL DEFAULT 'active',    -- active | paused | sold_out
    created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    CHECK (reserved_qty + sold_qty <= total_qty)
);
CREATE INDEX ix_listings_farm     ON stock_listings (farm_id);
CREATE INDEX ix_listings_product  ON stock_listings (product_id);
CREATE INDEX ix_listings_city     ON stock_listings (city);
CREATE INDEX ix_listings_district ON stock_listings (district);
CREATE INDEX ix_listings_origin   ON stock_listings (origin_tag);
CREATE INDEX ix_listings_status   ON stock_listings (status);
CREATE INDEX ix_listings_geo      ON stock_listings (latitude, longitude);
-- For large data, add PostGIS and a GiST index on a geography column instead of the (latitude, longitude) index.

CREATE TABLE orders (
    id                SERIAL PRIMARY KEY,
    buyer_id          INTEGER NOT NULL REFERENCES users(id),
    farm_id           INTEGER NOT NULL REFERENCES farm_profiles(id),
    status            VARCHAR(30) NOT NULL DEFAULT 'placed',
    -- placed | accepted | preparing | ready_for_pickup | out_for_delivery
    -- | completed | rejected | cancelled | failed_delivery
    fulfilment_type   VARCHAR(20) NOT NULL,                  -- delivery | pickup
    payment_method    VARCHAR(20) NOT NULL DEFAULT 'cod',    -- cod | jazzcash | easypaisa | card
    payment_status    VARCHAR(20) NOT NULL DEFAULT 'pending',
    delivery_address  VARCHAR(255),
    delivery_lat      DOUBLE PRECISION,
    delivery_lon      DOUBLE PRECISION,
    subtotal          DOUBLE PRECISION NOT NULL,
    delivery_fee      DOUBLE PRECISION NOT NULL DEFAULT 0,
    total             DOUBLE PRECISION NOT NULL,
    confirmation_code VARCHAR(4) NOT NULL,
    rejection_reason  VARCHAR(255),
    placed_at         TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_orders_buyer  ON orders (buyer_id);
CREATE INDEX ix_orders_farm   ON orders (farm_id);
CREATE INDEX ix_orders_status ON orders (status);

CREATE TABLE order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    listing_id   INTEGER NOT NULL REFERENCES stock_listings(id),
    product_name VARCHAR(100) NOT NULL,                      -- copied at order time
    qty          DOUBLE PRECISION NOT NULL CHECK (qty > 0),
    unit_price   DOUBLE PRECISION NOT NULL                   -- copied at order time
);

CREATE TABLE reviews (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL UNIQUE REFERENCES orders(id),
    buyer_id     INTEGER NOT NULL REFERENCES users(id),
    farm_id      INTEGER NOT NULL REFERENCES farm_profiles(id),
    stars        INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    comment      TEXT,
    farmer_reply VARCHAR(500),
    created_at   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    type       VARCHAR(40)  NOT NULL,                        -- order | stock | account
    message    VARCHAR(255) NOT NULL,
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_notifications_user ON notifications (user_id);
