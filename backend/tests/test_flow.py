"""End-to-end checks of the main rules: OTP sign-up, per-stock admin approval, location search,
stock reservation, order lifecycle, admin lists and order tracking."""
from app.config import settings
from app.models.catalog import Category, Product
from app.services.bootstrap import ensure_default_admin

FARM = {
    "farm_name": "Green Acres",
    "delivery_enabled": True,
    "pickup_enabled": True,
    "delivery_radius_km": 10,
    "delivery_fee": 100,
    "min_order": 0,
    "pickup_hours": "9am-6pm",
    "address_text": "Ring Road, Peshawar",
    "city": "Peshawar",
    "district": "Peshawar",
    "province": "Khyber Pakhtunkhwa",
    "latitude": 34.0151,
    "longitude": 71.5249,
}


def signup(client, phone, role):
    otp = client.post("/auth/otp/request", json={"phone": phone})
    assert otp.status_code == 200, otp.text
    r = client.post(
        "/auth/register",
        json={
            "name": f"{role} user", "phone": phone, "password": "secret123", "role": role,
            "otp": otp.json()["dev_otp"],
            "cnic": f"35202{phone[-7:]}1",  # farmers need a CNIC; buyers ignore it
        },
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def admin_headers(client, db_session):
    ensure_default_admin(db_session)
    r = client.post("/auth/login", data={"username": settings.admin_phone, "password": settings.admin_password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def listing_payload(product_id, qty=10):
    return {
        "product_id": product_id,
        "total_qty": qty,
        "unit": "litre",
        "price_per_unit": 150,
        "is_organic": True,
        "address_text": "Ring Road, Peshawar",
        "city": "Peshawar",
        "district": "Peshawar",
        "province": "Khyber Pakhtunkhwa",
        "latitude": 34.0151,
        "longitude": 71.5249,
        "origin_tag": "Peshawar",
    }


def setup_farm_and_product(client, db_session, phone="03001111111"):
    farmer = signup(client, phone, "farmer")
    farm = client.post("/farms/profile", json=FARM, headers=farmer).json()
    category = db_session.query(Category).filter_by(name="Dairy").first()
    if not category:
        category = Category(name="Dairy")
        db_session.add(category)
        db_session.flush()
    product = db_session.query(Product).filter_by(name="Milk").first()
    if not product:
        product = Product(name="Milk", category_id=category.id, default_unit="litre")
        db_session.add(product)
    db_session.commit()
    return farmer, farm, product


def publish_approved(client, db_session, farmer, product_id, qty=10):
    """Farmer adds stock; the admin approves it."""
    listing = client.post("/stock", json=listing_payload(product_id, qty), headers=farmer)
    assert listing.status_code == 201, listing.text
    admin = admin_headers(client, db_session)
    assert client.post(f"/admin/stock/{listing.json()['id']}/approve", headers=admin).status_code == 200
    return listing.json()


# ---------- registration ----------
def test_register_needs_the_right_otp(client):
    phone = "03005555555"
    code = client.post("/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    payload = {"name": "Ali Khan", "phone": phone, "password": "secret123", "role": "farmer", "cnic": "35202-1234567-1"}

    wrong = "000000" if code != "000000" else "111111"
    assert client.post("/auth/register", json={**payload, "otp": wrong}).status_code == 400
    assert client.post("/auth/register", json={**payload, "otp": code}).status_code == 201
    # the code works once only, and the phone is now taken
    assert client.post("/auth/register", json={**payload, "otp": code}).status_code == 409


def test_farmer_needs_a_valid_unique_cnic(client):
    def register(phone, **extra):
        code = client.post("/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
        body = {"name": "Farmer", "phone": phone, "password": "secret123", "role": "farmer", "otp": code, **extra}
        return client.post("/auth/register", json=body)

    assert register("03007770001").status_code == 422  # no CNIC
    assert register("03007770001", cnic="1234").status_code == 422  # too short
    assert register("03007770001", cnic="3520212345671").status_code == 201  # digits only is accepted
    assert register("03007770002", cnic="35202-1234567-1").status_code == 409  # same CNIC, formatted differently


def test_buyer_does_not_need_a_cnic(client):
    code = client.post("/auth/otp/request", json={"phone": "03007770003"}).json()["dev_otp"]
    body = {"name": "Buyer", "phone": "03007770003", "password": "secret123", "role": "buyer", "otp": code}
    assert client.post("/auth/register", json=body).status_code == 201


def test_admin_cannot_register(client):
    code = client.post("/auth/otp/request", json={"phone": "03006666666"}).json()["dev_otp"]
    r = client.post(
        "/auth/register",
        json={"name": "Sneaky", "phone": "03006666666", "password": "secret123", "role": "admin", "otp": code},
    )
    assert r.status_code == 422


# ---------- stock approval ----------
def test_farmer_needs_no_approval_but_each_new_stock_does(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    assert farm["verification_status"] == "approved"  # the farm itself is not reviewed

    created = client.post("/stock", json=listing_payload(product.id), headers=farmer)
    assert created.status_code == 201
    assert created.json()["approval_status"] == "pending"
    assert client.get("/search", params={"q": "milk"}).json() == []  # hidden until approved

    admin = admin_headers(client, db_session)
    pending = client.get("/admin/stock/pending", headers=admin).json()
    assert [p["id"] for p in pending] == [created.json()["id"]]
    assert pending[0]["farmer_phone"] == "03001111111"

    assert client.post(f"/admin/stock/{created.json()['id']}/approve", headers=admin).status_code == 200
    assert len(client.get("/search", params={"q": "milk"}).json()) == 1


def test_rejected_stock_stays_hidden_until_resubmitted_and_approved(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    admin = admin_headers(client, db_session)
    lid = client.post("/stock", json=listing_payload(product.id), headers=farmer).json()["id"]

    rejected = client.post(f"/admin/stock/{lid}/reject", json={"reason": "Photo missing"}, headers=admin)
    assert rejected.status_code == 200 and rejected.json()["approval_status"] == "rejected"
    assert client.get("/search", params={"q": "milk"}).json() == []
    mine = client.get("/stock/mine", headers=farmer).json()
    assert mine[0]["approval_status"] == "rejected" and mine[0]["approval_note"] == "Photo missing"

    # editing a rejected listing sends it back for review
    edited = client.patch(f"/stock/{lid}", json={"price_per_unit": 140}, headers=farmer)
    assert edited.json()["approval_status"] == "pending"


def test_farmer_can_add_multiple_stocks(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    wheat = Product(name="Wheat", category_id=product.category_id, default_unit="kg")
    db_session.add(wheat)
    db_session.commit()
    for pid in (product.id, wheat.id, product.id):  # the same product twice is also allowed
        assert client.post("/stock", json=listing_payload(pid), headers=farmer).status_code == 201
    assert len(client.get("/stock/mine", headers=farmer).json()) == 3


def test_buyer_cannot_order_stock_that_is_not_approved(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    lid = client.post("/stock", json=listing_payload(product.id), headers=farmer).json()["id"]
    buyer = signup(client, "03002222222", "buyer")
    r = client.post(
        "/orders", json={"items": [{"listing_id": lid, "qty": 1}], "fulfilment_type": "pickup"}, headers=buyer
    )
    assert r.status_code == 400


# ---------- search and orders ----------
def test_location_search_and_pickup_order(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    publish_approved(client, db_session, farmer, product.id)

    results = client.get("/search", params={"q": "milk", "lat": 34.02, "lon": 71.53}).json()
    assert len(results) == 1
    assert results[0]["fulfilment_label"] == "Delivers to you"
    # the stock location is returned so the app can open it in Google Maps
    assert results[0]["latitude"] == 34.0151 and results[0]["address_text"] == "Ring Road, Peshawar"
    assert client.get("/search", params={"q": "milk", "origin": "Swat"}).json() == []

    buyer = signup(client, "03002222222", "buyer")
    order = client.post(
        "/orders",
        json={"items": [{"listing_id": results[0]["id"], "qty": 2}], "fulfilment_type": "pickup"},
        headers=buyer,
    )
    assert order.status_code == 201, order.text
    order = order.json()

    assert client.get("/search", params={"q": "milk"}).json()[0]["available_qty"] == 8  # reserved at once

    oid = order["id"]
    for status in ("accepted", "preparing", "ready_for_pickup"):
        assert client.post(f"/orders/{oid}/status", json={"status": status}, headers=farmer).status_code == 200
    assert client.post(f"/orders/{oid}/status", json={"status": "completed"}, headers=farmer).status_code == 400
    done = client.post(
        f"/orders/{oid}/status", json={"status": "completed", "code": order["confirmation_code"]}, headers=farmer
    )
    assert done.status_code == 200 and done.json()["status"] == "completed"


def test_cannot_order_more_than_available_and_cancel_releases_stock(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    listing = publish_approved(client, db_session, farmer, product.id, qty=5)
    buyer = signup(client, "03002222222", "buyer")

    too_much = client.post(
        "/orders", json={"items": [{"listing_id": listing["id"], "qty": 6}], "fulfilment_type": "pickup"}, headers=buyer
    )
    assert too_much.status_code == 400

    ok = client.post(
        "/orders", json={"items": [{"listing_id": listing["id"], "qty": 5}], "fulfilment_type": "pickup"}, headers=buyer
    ).json()
    assert client.get("/search", params={"q": "milk"}).json() == []  # sold out, hidden from search

    cancel = client.post(f"/orders/{ok['id']}/status", json={"status": "cancelled"}, headers=buyer)
    assert cancel.status_code == 200
    assert client.get("/search", params={"q": "milk"}).json()[0]["available_qty"] == 5


def test_delivery_outside_radius_is_refused(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    listing = publish_approved(client, db_session, farmer, product.id)
    buyer = signup(client, "03002222222", "buyer")
    r = client.post(
        "/orders",
        json={
            "items": [{"listing_id": listing["id"], "qty": 1}],
            "fulfilment_type": "delivery",
            "delivery_address": "Mardan city",
            "delivery_lat": 34.1986,
            "delivery_lon": 72.0404,
        },
        headers=buyer,
    )
    assert r.status_code == 400
    assert "delivers within" in r.json()["detail"]


def test_popular_and_recent_for_the_home_page(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    wheat = Product(name="Wheat", category_id=product.category_id, default_unit="kg")
    db_session.add(wheat)
    db_session.commit()
    milk = publish_approved(client, db_session, farmer, product.id)
    wheat_listing = publish_approved(client, db_session, farmer, wheat.id)

    buyer = signup(client, "03002222222", "buyer")
    client.post("/orders", json={"items": [{"listing_id": milk["id"], "qty": 1}], "fulfilment_type": "pickup"}, headers=buyer)

    recent = client.get("/listings/recent").json()
    assert [r["id"] for r in recent] == [wheat_listing["id"], milk["id"]]  # newest first
    popular = client.get("/listings/popular").json()
    assert popular[0]["id"] == milk["id"]  # the ordered one comes first


# ---------- admin ----------
def test_admin_lists_buyers_and_farmers_with_their_stock(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    client.post("/stock", json=listing_payload(product.id), headers=farmer)
    publish_approved(client, db_session, farmer, product.id)
    signup(client, "03003333333", "buyer")
    admin = admin_headers(client, db_session)

    assert client.get("/admin/users", headers=farmer).status_code == 403
    assert [u["role"] for u in client.get("/admin/users?role=buyer", headers=admin).json()] == ["buyer"]

    farmers = client.get("/admin/farmers", headers=admin).json()
    assert len(farmers) == 1
    assert farmers[0]["stock_total"] == 2 and farmers[0]["stock_pending"] == 1
    assert {s["approval_status"] for s in farmers[0]["stocks"]} == {"pending", "approved"}

    stats = client.get("/admin/stats", headers=admin).json()
    assert stats["farmers"] == 1 and stats["buyers"] == 1 and stats["pending_stock"] == 1


def test_admin_tracks_an_order_from_source_to_destination(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    listing = publish_approved(client, db_session, farmer, product.id)
    buyer = signup(client, "03002222222", "buyer")
    admin = admin_headers(client, db_session)

    placed = client.post(
        "/orders",
        json={
            "items": [{"listing_id": listing["id"], "qty": 2}],
            "fulfilment_type": "delivery",
            "delivery_address": "House 5, University Town, Peshawar",
            "delivery_lat": 34.02,
            "delivery_lon": 71.53,
        },
        headers=buyer,
    )
    assert placed.status_code == 201, placed.text
    oid = placed.json()["id"]
    assert client.post(f"/orders/{oid}/status", json={"status": "accepted"}, headers=farmer).status_code == 200

    assert client.get("/admin/orders", headers=buyer).status_code == 403
    order = client.get(f"/admin/orders/{oid}", headers=admin).json()
    assert order["source"]["name"] == "Green Acres"
    assert order["source"]["contact_phone"] == "03001111111"
    assert order["source"]["address"] == "Ring Road, Peshawar"
    assert order["destination"]["contact_phone"] == "03002222222"
    assert order["destination"]["kind"] == "Delivery address"
    assert order["destination"]["address"] == "House 5, University Town, Peshawar"
    assert 0 < order["distance_km"] < 2
    assert [e["status"] for e in order["events"]] == ["placed", "accepted"]

    assert len(client.get("/admin/orders", headers=admin).json()) == 1
    assert client.get("/admin/orders?status=completed", headers=admin).json() == []


def test_pickup_order_destination_is_the_stock_location(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    listing = publish_approved(client, db_session, farmer, product.id)
    buyer = signup(client, "03002222222", "buyer")
    admin = admin_headers(client, db_session)
    oid = client.post(
        "/orders", json={"items": [{"listing_id": listing["id"], "qty": 1}], "fulfilment_type": "pickup"}, headers=buyer
    ).json()["id"]
    order = client.get(f"/admin/orders/{oid}", headers=admin).json()
    assert order["destination"]["kind"] == "Pickup at the stock location"
    assert order["destination"]["address"] == order["source"]["address"]
    assert order["distance_km"] is None
