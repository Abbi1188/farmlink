"""FarmLink web frontend (Flask). Talks to the FastAPI backend through api_client.api()."""
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from api_client import api

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")

# The server stores times in UTC. Show them in local time (Pakistan = UTC+5, no daylight saving).
DISPLAY_UTC_OFFSET_HOURS = float(os.environ.get("DISPLAY_UTC_OFFSET_HOURS", "5"))

ROLE_LABELS = {"farmer": "Farmer", "buyer": "User", "admin": "Admin"}


# ---------- helpers ----------
def _safe_next(target):
    """Only allow redirects to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


def _home_for(role: str) -> str:
    return url_for({"farmer": "farmer_dashboard", "admin": "admin_dashboard"}.get(role, "index"))


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def login_required(role: str | None = None):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please log in first.", "warning")
                here = request.full_path if request.query_string else request.path
                return redirect(url_for("login", role=role or "buyer", next=here))
            if role and user["role"] != role:
                flash("You do not have access to that page.", "danger")
                return redirect(_home_for(user["role"]))
            return view(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_globals():
    return {"current_user": session.get("user"), "ROLE_LABELS": ROLE_LABELS}


@app.template_filter("dt")
def format_datetime(value):
    """'2026-11-16T07:58:29' (UTC) -> '16 Nov 2026, 12:58'."""
    if not value:
        return "—"
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", ""))
    except ValueError:
        return str(value)
    moment = moment.replace(tzinfo=timezone.utc) + timedelta(hours=DISPLAY_UTC_OFFSET_HOURS)
    return moment.strftime("%d %b %Y, %H:%M")


@app.template_filter("maps_url")
def maps_url(lat, lon):
    """Google Maps link that opens a pin at the given coordinates (no API key needed)."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


@app.template_filter("route_url")
def route_url(src_lat, src_lon, dst_lat, dst_lon):
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={src_lat},{src_lon}&destination={dst_lat},{dst_lon}&travelmode=driving"
    )


# ---------- Welcome page ----------
@app.route("/welcome")
def welcome():
    if session.get("user"):
        return redirect(_home_for(session["user"]["role"]))
    return render_template("welcome.html")


# ---------- Buyer home and search ----------
RECENT_LIMIT = 6


def _remember_search(term: str) -> None:
    recent = [t for t in session.get("recent_searches", []) if t.lower() != term.lower()]
    session["recent_searches"] = ([term] + recent)[:RECENT_LIMIT]


@app.route("/")
def index():
    user = session.get("user")
    if user and user["role"] in ("farmer", "admin"):
        return redirect(_home_for(user["role"]))

    args = request.args
    params = {
        "q": args.get("q", "").strip(),
        "city": args.get("city", "").strip(),
        "district": args.get("district", "").strip(),
        "origin": args.get("origin", "").strip(),
        "radius_km": args.get("radius_km", "").strip(),
        "lat": args.get("lat", "").strip(),
        "lon": args.get("lon", "").strip(),
    }
    if args.get("organic"):
        params["organic"] = "true"
    if args.get("deliverable_only"):
        params["deliverable_only"] = "true"

    # lat/lon alone (set by the location button) is not a search
    searched = any(v for k, v in params.items() if k not in ("lat", "lon"))
    filters_active = any(params[k] for k in ("city", "district", "origin", "radius_km")) or bool(
        args.get("organic") or args.get("deliverable_only")
    )

    results, popular, recent = [], [], []
    if searched:
        if params["q"]:
            _remember_search(params["q"])
        ok, data = api("GET", "/search", params={k: v for k, v in params.items() if v})
        if ok:
            results = data
        else:
            flash(data, "danger")
    else:
        ok_p, data_p = api("GET", "/listings/popular", params={"limit": 6})
        ok_r, data_r = api("GET", "/listings/recent", params={"limit": 6})
        popular = data_p if ok_p else []
        recent = data_r if ok_r else []
        if not ok_p and not ok_r:
            flash(data_p, "danger")

    # The welcome pop-up appears once each time the app is opened by someone who is not logged in.
    show_welcome = not user and not session.get("welcome_seen")
    if show_welcome:
        session["welcome_seen"] = True

    return render_template(
        "index.html",
        results=results,
        searched=searched,
        form=args,
        filters_active=filters_active,
        popular=popular,
        recent=recent,
        recent_searches=session.get("recent_searches", []),
        show_welcome=show_welcome,
    )


# ---------- Auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    role = request.values.get("role", "buyer")
    if role == "admin":
        flash("There is only one admin account. Please log in.", "warning")
        return redirect(url_for("login", role="admin"))
    if role not in ("farmer", "buyer"):
        role = "buyer"

    if request.method == "POST":
        payload = {k: request.form.get(k, "").strip() for k in ("name", "phone", "password", "otp", "language")}
        payload["role"] = role
        ok, data = api("POST", "/auth/register", json=payload)
        if ok:
            session["token"], session["user"] = data["access_token"], data["user"]
            flash("Welcome to FarmLink!", "success")
            if role == "farmer":
                flash("Set up your farm to start adding stock.", "success")
            return redirect(_home_for(role))
        flash(data, "danger")
    return render_template("register.html", role=role, form=request.form)


@app.post("/register/otp")
def register_otp():
    """Called by the sign-up page (JavaScript) to send the 6-digit code."""
    phone = ((request.get_json(silent=True) or {}).get("phone") or "").strip()
    ok, data = api("POST", "/auth/otp/request", json={"phone": phone})
    if ok:
        return jsonify(ok=True, **data)
    return jsonify(ok=False, error=data), 400


@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.values.get("role", "buyer")
    if role not in ROLE_LABELS:
        role = "buyer"
    nxt = _safe_next(request.values.get("next"))

    if request.method == "POST":
        ok, data = api(
            "POST", "/auth/login", data={"username": request.form["phone"].strip(), "password": request.form["password"]}
        )
        if ok and data["user"]["role"] != role:
            actual = ROLE_LABELS.get(data["user"]["role"], data["user"]["role"])
            flash(f"This is a {actual} account. Please use the {actual} login.", "danger")
        elif ok:
            session["token"], session["user"] = data["access_token"], data["user"]
            return redirect(nxt or _home_for(role))
        else:
            flash(data, "danger")
    return render_template("login.html", role=role, next=nxt)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- Buyer: ordering ----------
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
    return render_template("order_new.html", listing=listing, lat=lat, lon=lon, form=request.form)


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
            flash("Farm profile saved. You can add your stock now.", "success")
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
    if ok:
        flash("Stock sent to the admin for approval. Buyers will see it once it is approved.", "success")
    else:
        flash(data, "danger")
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
    ok, stats = api("GET", "/admin/stats")
    if not ok:
        flash(stats, "danger")
        stats = {}
    ok, pending = api("GET", "/admin/stock/pending")
    if not ok:
        flash(pending, "danger")
    return render_template("admin_dashboard.html", stats=stats, pending=pending if ok else [])


@app.route("/admin/farmers")
@login_required("admin")
def admin_farmers():
    ok, farmers = api("GET", "/admin/farmers")
    if not ok:
        flash(farmers, "danger")
    return render_template("admin_farmers.html", farmers=farmers if ok else [])


@app.route("/admin/buyers")
@login_required("admin")
def admin_buyers():
    ok, buyers = api("GET", "/admin/users", params={"role": "buyer"})
    if not ok:
        flash(buyers, "danger")
    return render_template("admin_buyers.html", buyers=buyers if ok else [])


ORDER_STATUSES = [
    "placed", "accepted", "preparing", "ready_for_pickup", "out_for_delivery",
    "completed", "rejected", "cancelled", "failed_delivery",
]


@app.route("/admin/orders")
@login_required("admin")
def admin_orders():
    status = request.args.get("status", "").strip()
    ok, orders_ = api("GET", "/admin/orders", params={"status": status} if status else None)
    if not ok:
        flash(orders_, "danger")
    return render_template(
        "admin_orders.html", orders=orders_ if ok else [], status=status, statuses=ORDER_STATUSES
    )


@app.route("/admin/orders/<int:order_id>")
@login_required("admin")
def admin_order_detail(order_id):
    ok, order = api("GET", f"/admin/orders/{order_id}")
    if not ok:
        flash(order, "danger")
        return redirect(url_for("admin_orders"))
    return render_template("admin_order_detail.html", order=order)


@app.route("/admin/stock/<int:listing_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_stock_action(listing_id, action):
    back = _safe_next(request.form.get("next")) or url_for("admin_dashboard")
    if action not in ("approve", "reject"):
        return redirect(back)
    body = {"reason": request.form.get("reason", "").strip() or None} if action == "reject" else None
    ok, data = api("POST", f"/admin/stock/{listing_id}/{action}", json=body)
    flash(
        (f"Stock {action}d." if action == "approve" else "Stock rejected.") if ok else data,
        "success" if ok else "danger",
    )
    return redirect(back)


@app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_user_action(user_id, action):
    back = _safe_next(request.form.get("next")) or url_for("admin_dashboard")
    if action not in ("suspend", "activate"):
        return redirect(back)
    ok, data = api("POST", f"/admin/users/{user_id}/{action}")
    flash(
        "Account suspended." if ok and action == "suspend" else "Account re-activated." if ok else data,
        "success" if ok else "danger",
    )
    return redirect(back)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
