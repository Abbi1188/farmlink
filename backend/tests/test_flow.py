"""End-to-end checks of the main rules: approval, location search, stock reservation, order lifecycle."""
from app.models.catalog import Category, Product
from app.models.farm import FarmProfile

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
    r = client.post("/auth/register", json={"name": f"{role} user", "phone": phone, "password": "secret123", "role": role})
    assert r.status_code == 201, r.text
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


def setup_farm_and_product(client, db_session):
    farmer = signup(client, "03001111111", "farmer")
    farm = client.post("/farms/profile", json=FARM, headers=farmer).json()
    category = Category(name="Dairy")
    db_session.add(category)
    db_session.flush()
    product = Product(name="Milk", category_id=category.id, default_unit="litre")
    db_session.add(product)
    db_session.commit()
    return farmer, farm, product


def approve(db_session, farm_id):
    db_session.get(FarmProfile, farm_id).verification_status = "approved"
    db_session.commit()


def test_unapproved_farm_cannot_publish(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    r = client.post("/stock", json=listing_payload(product.id), headers=farmer)
    assert r.status_code == 403


def test_location_search_and_pickup_order(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    approve(db_session, farm["id"])
    assert client.post("/stock", json=listing_payload(product.id), headers=farmer).status_code == 201

    results = client.get("/search", params={"q": "milk", "lat": 34.02, "lon": 71.53}).json()
    assert len(results) == 1
    assert results[0]["fulfilment_label"] == "Delivers to you"
    assert client.get("/search", params={"q": "milk", "origin": "Swat"}).json() == []

    buyer = signup(client, "03002222222", "buyer")
    order = client.post(
        "/orders",
        json={"items": [{"listing_id": results[0]["id"], "qty": 2}], "fulfilment_type": "pickup"},
        headers=buyer,
    )
    assert order.status_code == 201, order.text
    order = order.json()

    # stock is reserved at once
    assert client.get("/search", params={"q": "milk"}).json()[0]["available_qty"] == 8

    oid = order["id"]
    for status in ("accepted", "preparing", "ready_for_pickup"):
        assert client.post(f"/orders/{oid}/status", json={"status": status}, headers=farmer).status_code == 200
    # completing without the buyer's code is refused
    assert client.post(f"/orders/{oid}/status", json={"status": "completed"}, headers=farmer).status_code == 400
    done = client.post(
        f"/orders/{oid}/status", json={"status": "completed", "code": order["confirmation_code"]}, headers=farmer
    )
    assert done.status_code == 200 and done.json()["status"] == "completed"


def test_cannot_order_more_than_available_and_cancel_releases_stock(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    approve(db_session, farm["id"])
    listing = client.post("/stock", json=listing_payload(product.id, qty=5), headers=farmer).json()
    buyer = signup(client, "03002222222", "buyer")

    too_much = client.post(
        "/orders",
        json={"items": [{"listing_id": listing["id"], "qty": 6}], "fulfilment_type": "pickup"},
        headers=buyer,
    )
    assert too_much.status_code == 400

    ok = client.post(
        "/orders",
        json={"items": [{"listing_id": listing["id"], "qty": 5}], "fulfilment_type": "pickup"},
        headers=buyer,
    ).json()
    assert client.get("/search", params={"q": "milk"}).json() == []  # sold out, hidden from search

    cancel = client.post(f"/orders/{ok['id']}/status", json={"status": "cancelled"}, headers=buyer)
    assert cancel.status_code == 200
    assert client.get("/search", params={"q": "milk"}).json()[0]["available_qty"] == 5


def test_delivery_outside_radius_is_refused(client, db_session):
    farmer, farm, product = setup_farm_and_product(client, db_session)
    approve(db_session, farm["id"])
    listing = client.post("/stock", json=listing_payload(product.id), headers=farmer).json()
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


def test_admin_lists_users_and_pending_farms(client, db_session):
    from app.core.constants import Role
    from app.core.security import hash_password
    from app.models.user import User

    farmer = signup(client, "03002222222", "farmer")
    signup(client, "03003333333", "buyer")
    client.post("/farms/profile", json=FARM, headers=farmer)
    db_session.add(User(name="Admin", phone="03000000009", password_hash=hash_password("admin123"), role=Role.ADMIN))
    db_session.commit()
    token = client.post("/auth/login", data={"username": "03000000009", "password": "admin123"}).json()["access_token"]
    admin = {"Authorization": f"Bearer {token}"}

    assert client.get("/admin/users", headers=farmer).status_code == 403
    assert [u["role"] for u in client.get("/admin/users?role=buyer", headers=admin).json()] == ["buyer"]
    farmers = client.get("/admin/users?role=farmer", headers=admin).json()
    assert farmers[0]["farm_status"] == "pending"
    pending = client.get("/admin/farms/pending", headers=admin).json()
    assert len(pending) == 1 and pending[0]["owner_phone"] == "03002222222"
    assert client.post(f"/admin/farms/{pending[0]['id']}/approve", headers=admin).status_code == 200
    assert client.get("/admin/farms/pending", headers=admin).json() == []
