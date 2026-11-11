"""FarmLink web frontend (Flask). Talks to the FastAPI backend through api_client.api()."""
import os
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, session, url_for

from api_client import api

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")


def login_required(role: str | None = None):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and user["role"] != role:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapper

    return decorator


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _home_for(role: str) -> str:
    return url_for({"farmer": "farmer_dashboard", "admin": "admin_dashboard"}.get(role, "index"))


@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}


# ---------- Public: search ----------
@app.route("/")
def index():
    params = {
        "q": request.args.get("q", "").strip(),
        "city": request.args.get("city", "").strip(),
        "district": request.args.get("district", "").strip(),
        "origin": request.args.get("origin", "").strip(),
        "radius_km": request.args.get("radius_km", "").strip(),
        "lat": request.args.get("lat", "").strip(),
        "lon": request.args.get("lon", "").strip(),
    }
    if request.args.get("organic"):
        params["organic"] = "true"
    if request.args.get("deliverable_only"):
        params["deliverable_only"] = "true"

    results, searched = [], any(request.args.values())
    if searched:
        ok, data = api("GET", "/search", params={k: v for k, v in params.items() if v})
        if ok:
            results = data
        else:
            flash(data, "danger")
    return render_template("index.html", results=results, searched=searched, form=request.args)


# ---------- Auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        payload = {k: request.form.get(k, "").strip() for k in ("name", "phone", "password", "role", "language")}
        ok, data = api("POST", "/auth/register", json=payload)
        if ok:
            session["token"], session["user"] = data["access_token"], data["user"]
            flash("Welcome to FarmLink!", "success")
            return redirect(_home_for(data["user"]["role"]))
        flash(data, "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ok, data = api(
            "POST", "/auth/login", data={"username": request.form["phone"].strip(), "password": request.form["password"]}
        )
        if ok:
            session["token"], session["user"] = data["access_token"], data["user"]
            return redirect(_home_for(data["user"]["role"]))
        flash(data, "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- Buyer ----------
@app.route("/order/new/<int:listing_id>", methods=["GET", "POST"])
@login_required("buyer")
def order_new(listing_id):
    lat, lon = request.values.get("lat"), request.values.get("lon")
    ok, listing = api("GET", f"/listings/{listing_id}", params={k: v for k, v in (("lat", lat), ("lon", lon)) if v})
    if not ok:
        flash(listing, "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        payload = {
            "items": [{"listing_id": listing_id, "qty": _float(request.form.get("qty"), 1)}],
            "fulfilment_type": request.form.get("fulfilment_type", "pickup"),
            "payment_method": request.form.get("payment_method", "cod"),
            "delivery_address": request.form.get("delivery_address") or None,
            "delivery_lat": _float(request.form.get("delivery_lat")),
            "delivery_lon": _float(request.form.get("delivery_lon")),
        }
        ok, data = api("POST", "/orders", json=payload)
        if ok:
            flash(f"Order #{data['id']} placed. Your code is {data['confirmation_code']}.", "success")
            return redirect(url_for("orders"))
        flash(data, "danger")
    return render_template("order_new.html", listing=listing, lat=lat, lon=lon)


@app.route("/orders")
@login_required("buyer")
def orders():
    ok, data = api("GET", "/orders/mine")
    if not ok:
        flash(data, "danger")
    return render_template("orders.html", orders=data if ok else [])


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required("buyer")
def order_cancel(order_id):
    ok, data = api("POST", f"/orders/{order_id}/status", json={"status": "cancelled"})
    flash("Order cancelled." if ok else data, "success" if ok else "danger")
    return redirect(url_for("orders"))


# ---------- Farmer ----------
@app.route("/farmer/profile", methods=["GET", "POST"])
@login_required("farmer")
def farm_profile():
    ok, farm = api("GET", "/farms/me")
    farm = farm if ok else None
    if request.method == "POST":
        f = request.form
        payload = {
            "farm_name": f.get("farm_name", "").strip(),
            "description": f.get("description") or None,
            "delivery_enabled": bool(f.get("delivery_enabled")),
            "pickup_enabled": bool(f.get("pickup_enabled")),
            "delivery_radius_km": _float(f.get("delivery_radius_km"), 10),
            "delivery_fee": _float(f.get("delivery_fee"), 0),
            "min_order": _float(f.get("min_order"), 0),
            "pickup_hours": f.get("pickup_hours") or None,
            "address_text": f.get("address_text", "").strip(),
            "city": f.get("city", "").strip(),
            "district": f.get("district", "").strip(),
            "province": f.get("province", "").strip(),
            "latitude": _float(f.get("latitude")),
            "longitude": _float(f.get("longitude")),
        }
        ok, data = api("PUT" if farm else "POST", "/farms/profile", json=payload)
        if ok:
            flash("Farm profile saved. An admin will review it before you can publish stock.", "success")
            return redirect(url_for("farmer_dashboard"))
        flash(data, "danger")
    return render_template("farm_profile.html", farm=farm)


@app.route("/farmer")
@login_required("farmer")
def farmer_dashboard():
    ok, farm = api("GET", "/farms/me")
    if not ok:
        return redirect(url_for("farm_profile"))
    _, listings = api("GET", "/stock/mine")
    _, products = api("GET", "/catalog/products")
    return render_template("farmer_dashboard.html", farm=farm, listings=listings or [], products=products or [])


@app.route("/farmer/stock", methods=["POST"])
@login_required("farmer")
def farmer_add_stock():
    f = request.form
    payload = {
        "product_id": int(f["product_id"]),
        "total_qty": _float(f.get("total_qty")),
        "unit": f.get("unit", "kg"),
        "price_per_unit": _float(f.get("price_per_unit")),
        "is_organic": bool(f.get("is_organic")),
        "harvest_date": f.get("harvest_date") or None,
        "expiry_date": f.get("expiry_date") or None,
        "address_text": f.get("address_text", "").strip(),
        "city": f.get("city", "").strip(),
        "district": f.get("district", "").strip(),
        "province": f.get("province", "").strip(),
        "latitude": _float(f.get("latitude")),
        "longitude": _float(f.get("longitude")),
        "origin_tag": f.get("origin_tag") or None,
    }
    ok, data = api("POST", "/stock", json=payload)
    flash("Stock published." if ok else data, "success" if ok else "danger")
    return redirect(url_for("farmer_dashboard"))


@app.route("/farmer/stock/<int:listing_id>/update", methods=["POST"])
@login_required("farmer")
def farmer_update_stock(listing_id):
    changes = {}
    if request.form.get("total_qty"):
        changes["total_qty"] = _float(request.form["total_qty"])
    if request.form.get("price_per_unit"):
        changes["price_per_unit"] = _float(request.form["price_per_unit"])
    if request.form.get("status"):
        changes["status"] = request.form["status"]
    ok, data = api("PATCH", f"/stock/{listing_id}", json=changes)
    flash("Stock updated." if ok else data, "success" if ok else "danger")
    return redirect(url_for("farmer_dashboard"))


@app.route("/farmer/orders")
@login_required("farmer")
def farmer_orders():
    ok, data = api("GET", "/orders/farm")
    if not ok:
        flash(data, "danger")
    return render_template("farmer_orders.html", orders=data if ok else [])


@app.route("/farmer/orders/<int:order_id>/status", methods=["POST"])
@login_required("farmer")
def farmer_order_status(order_id):
    payload = {"status": request.form["status"], "code": request.form.get("code") or None}
    if request.form.get("reason"):
        payload["reason"] = request.form["reason"]
    ok, data = api("POST", f"/orders/{order_id}/status", json=payload)
    flash("Order updated." if ok else data, "success" if ok else "danger")
    return redirect(url_for("farmer_orders"))


# ---------- Admin ----------
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    ok, pending = api("GET", "/admin/farms/pending")
    if not ok:
        flash(pending, "danger")
    _, farmers = api("GET", "/admin/users", params={"role": "farmer"})
    _, buyers = api("GET", "/admin/users", params={"role": "buyer"})
    return render_template(
        "admin_dashboard.html", pending=pending if ok else [], farmers=farmers or [], buyers=buyers or []
    )


@app.route("/admin/farms/<int:farm_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_farm_action(farm_id, action):
    if action not in ("approve", "reject"):
        return redirect(url_for("admin_dashboard"))
    ok, data = api("POST", f"/admin/farms/{farm_id}/{action}")
    flash(f"Farm {action}d." if ok else data, "success" if ok else "danger")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_user_action(user_id, action):
    if action not in ("suspend", "activate"):
        return redirect(url_for("admin_dashboard"))
    ok, data = api("POST", f"/admin/users/{user_id}/{action}")
    flash("Account suspended." if ok and action == "suspend" else "Account re-activated." if ok else data,
          "success" if ok else "danger")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(port=5000, debug=True)
