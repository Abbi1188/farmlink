"""FarmBridge web frontend (Flask). Talks to the FastAPI backend through api_client.api()."""
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for

from api_client import api, api_many, fetch_media

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = timedelta(days=365)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-change-me")
# Three photos of up to 5 MB each, plus the form fields. Anything bigger is refused before it is read.
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024



def _asset(filename):
    """URL of a static file with its modified time, so browsers cache it but still get new versions."""
    try:
        version = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
    except OSError:
        version = 0
    return url_for("static", filename=filename, v=version)


app.jinja_env.globals["asset"] = _asset


def _media_url(path):
    """Web address (on this site) of a stock photo that the API reports as /uploads/stock/<name>."""
    return url_for("media", filename=path.removeprefix("/uploads/"))


app.jinja_env.globals["media_url"] = _media_url

_MEDIA_NAME = re.compile(r"^stock/[0-9a-f]{32}\.(jpg|png|webp)$")


@app.route("/media/<path:filename>")
def media(filename):
    """Stock photos. The pictures are stored by the API; this route passes them on to the browser."""
    if not _MEDIA_NAME.match(filename):
        abort(404)
    found = fetch_media(filename)
    if not found:
        abort(404)
    body, content_type = found
    response = Response(body, mimetype=content_type)
    response.headers["Cache-Control"] = "public, max-age=604800, immutable"  # file names never repeat
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# ---------- Installable app (PWA) ----------
@app.route("/manifest.webmanifest")
def manifest():
    data = {
        "name": "FarmBridge",
        "short_name": "FarmBridge",
        "description": "Farm to City. Buy fresh stock from farms near you.",
        "id": "/",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#F9F9F3",
        "theme_color": "#245B3C",
        "icons": [
            {"src": url_for("static", filename="img/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": url_for("static", filename="img/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": url_for("static", filename="img/icon-maskable-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": url_for("static", filename="img/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    response = jsonify(data)
    response.headers["Content-Type"] = "application/manifest+json"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/sw.js")
def service_worker():
    """The service worker must be served from the site root so it covers every page."""
    response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/offline")
def offline():
    return render_template("offline.html")


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
                if role == "admin":
                    return redirect(url_for("admin_login"))
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
    return {
        "current_user": session.get("user"),
        "ROLE_LABELS": ROLE_LABELS,
        "cart_count": len(session.get("cart", {})),
    }


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


# ---------- Splash screen (shown the first time the app is opened) ----------
@app.route("/splash")
def splash():
    session["splash_seen"] = True
    return render_template("splash.html", next=_safe_next(request.args.get("next")) or url_for("index"))


# ---------- Welcome page ----------
@app.route("/welcome")
def welcome():
    if not session.get("splash_seen"):
        return redirect(url_for("splash", next=url_for("welcome")))
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
    if not session.get("splash_seen"):
        return redirect(url_for("splash"))
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
    cat_id = args.get("cat", "").strip()

    if params["lat"] and params["lon"]:
        session["buyer_loc"] = {"lat": params["lat"], "lon": params["lon"]}

    # lat/lon alone (set by the location button) is not a search
    searched = any(v for k, v in params.items() if k not in ("lat", "lon")) or bool(cat_id)
    filters_active = any(params[k] for k in ("city", "district", "origin", "radius_km")) or bool(
        args.get("organic") or args.get("deliverable_only")
    )

    # Ask the backend for everything this page needs at the same time
    calls = [("GET", "/catalog/categories")]
    if searched:
        query = {k: v for k, v in params.items() if v}
        if cat_id:
            query["limit"] = 100
            calls.append(("GET", "/catalog/products", {"params": {"category_id": cat_id}}))
        calls.append(("GET", "/search", {"params": query}))
        if params["q"]:
            _remember_search(params["q"])
    else:
        calls += [("GET", "/listings/popular", {"params": {"limit": 6}}), ("GET", "/listings/recent", {"params": {"limit": 6}})]
        if params["lat"] and params["lon"]:
            calls.append(("GET", "/search", {"params": {"lat": params["lat"], "lon": params["lon"], "limit": 6}}))
    answers = api_many(*calls)

    ok_c, categories = answers[0]
    categories = categories if ok_c else []
    active_cat = next((c for c in categories if str(c["id"]) == cat_id), None)

    results, popular, recent, near = [], [], [], []
    if searched:
        ok, data = answers[-1]
        if ok:
            results = data
            if cat_id:
                ok_p, prods = answers[1]
                names = {p["name"].lower() for p in prods} if ok_p else set()
                results = [r for r in data if r["product_name"].lower() in names]
        else:
            flash(data, "danger")
    else:
        (ok_p, data_p), (ok_r, data_r) = answers[1], answers[2]
        popular = data_p if ok_p else []
        recent = data_r if ok_r else []
        if not ok_p and not ok_r:
            if "Cannot reach" in str(data_p):
                return render_template(
                    "error.html",
                    title="No internet connection",
                    message="We cannot reach the FarmBridge server. Check your connection and try again.",
                    retry_url=url_for("index"),
                )
            flash(data_p, "danger")
        if len(answers) > 3:
            ok_n, data_n = answers[3]
            near = data_n if ok_n else []

    # "Shop by farm": the farms behind the stock shown on this page
    farms, seen_listings = {}, set()
    for r in near + popular + recent:
        if r["id"] in seen_listings:
            continue
        seen_listings.add(r["id"])
        farm = farms.setdefault(
            r["farm_id"],
            {"id": r["farm_id"], "name": r["farm_name"], "city": r["city"], "distance_km": r["distance_km"], "count": 0},
        )
        farm["count"] += 1

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
        near=near,
        categories=categories,
        active_cat=active_cat,
        farms=list(farms.values()),
        recent_searches=session.get("recent_searches", []),
        show_welcome=show_welcome,
    )


# ---------- Auth ----------
# Sign-up has two steps on two screens: 1) your details, 2) the 6-digit code.
# The details wait here on the server (never in the browser cookie) until the code is confirmed.
PENDING_REG = {}
PENDING_MINUTES = 15


def _pending_get():
    now = time.time()
    for key in [k for k, v in PENDING_REG.items() if v["expires"] < now]:
        PENDING_REG.pop(key, None)
    return PENDING_REG.get(session.get("reg_token", ""))


def _digits(text):
    return re.sub(r"\D", "", text or "")


def _mask_phone(phone):
    digits = _digits(phone)
    return f"{digits[:2]}•• ••• {digits[-4:]}" if len(digits) >= 6 else phone


@app.route("/register", methods=["GET", "POST"])
def register():
    role = request.values.get("role", "buyer")
    if role == "admin":
        flash("The admin account is created by the system. Use the admin login page.", "warning")
        return redirect(url_for("admin_login"))
    if role not in ("farmer", "buyer"):
        role = "buyer"

    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("name", "phone", "password", "language", "cnic")}
        form["phone"] = re.sub(r"[\s-]", "", form["phone"])
        errors = []
        if len(form["name"]) < 2:
            errors.append("Please enter your full name.")
        if len(_digits(form["phone"])) < 10:
            errors.append("Please enter a valid phone number.")
        if len(form["password"]) < 6:
            errors.append("Your password must be at least 6 characters.")
        cnic = _digits(form["cnic"])
        if role == "farmer" and len(cnic) != 13:
            errors.append("Please enter your 13-digit CNIC number.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", role=role, form=request.form)

        ok, data = api("POST", "/auth/otp/request", json={"phone": form["phone"]})
        if not ok:
            flash(data, "danger")
            return render_template("register.html", role=role, form=request.form)

        token = secrets.token_urlsafe(24)
        PENDING_REG[token] = {
            "payload": {
                "name": form["name"], "phone": form["phone"], "password": form["password"],
                "language": form["language"] or "en", "role": role,
                **({"cnic": f"{cnic[:5]}-{cnic[5:12]}-{cnic[12]}"} if role == "farmer" else {}),
            },
            "dev_otp": data.get("dev_otp"),
            "expires": time.time() + PENDING_MINUTES * 60,
        }
        session["reg_token"] = token
        return redirect(url_for("verify"))
    return render_template("register.html", role=role, form=request.form)


@app.route("/verify", methods=["GET", "POST"])
def verify():
    pending = _pending_get()
    if not pending:
        flash("Your sign-up session ended. Please enter your details again.", "warning")
        return redirect(url_for("register"))
    payload = pending["payload"]
    role = payload["role"]

    if request.method == "POST":
        otp = _digits(request.form.get("otp"))
        if len(otp) != 6:
            flash("Please enter all 6 digits of the code.", "danger")
        else:
            ok, data = api("POST", "/auth/register", json={**payload, "otp": otp})
            if ok:
                PENDING_REG.pop(session.pop("reg_token", ""), None)
                session["token"], session["user"] = data["access_token"], data["user"]
                flash("Welcome to FarmBridge!", "success")
                if role == "farmer":
                    flash("Set up your farm to start adding stock.", "success")
                return redirect(_home_for(role))
            flash(data, "danger")
    return render_template(
        "verify.html", role=role, masked_phone=_mask_phone(payload["phone"]), dev_otp=pending.get("dev_otp")
    )


@app.post("/verify/resend")
def verify_resend():
    pending = _pending_get()
    if not pending:
        return redirect(url_for("register"))
    ok, data = api("POST", "/auth/otp/request", json={"phone": pending["payload"]["phone"]})
    if ok:
        pending["dev_otp"] = data.get("dev_otp")
        flash("A new code was sent.", "success")
    else:
        flash(data, "danger")
    return redirect(url_for("verify"))


@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.values.get("role", "buyer")
    if role == "admin":
        return redirect(url_for("admin_login"))
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


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """The administrator signs in here. It is a separate page that is not linked from the public screens."""
    user = session.get("user")
    if user and user["role"] == "admin":
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        ok, data = api(
            "POST", "/auth/login", data={"username": request.form["phone"].strip(), "password": request.form["password"]}
        )
        if ok and data["user"]["role"] == "admin":
            session["token"], session["user"] = data["access_token"], data["user"]
            return redirect(url_for("admin_dashboard"))
        flash("This is not an admin account." if ok else data, "danger")
    return render_template("admin_login.html")


@app.route("/logout")
def logout():
    was_admin = (session.get("user") or {}).get("role") == "admin"
    session.clear()
    session["splash_seen"] = True
    return redirect(url_for("admin_login") if was_admin else url_for("index"))


@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


# ---------- Buyer: ordering ----------
def _back_url(default):
    """Go back to the page the visitor came from, if it is on this site."""
    ref = request.referrer
    if ref and ref.startswith(request.host_url) and request.base_url not in ref:
        return ref
    return default


@app.route("/listing/<int:listing_id>")
def product(listing_id):
    lat, lon = request.args.get("lat"), request.args.get("lon")
    ok, listing = api("GET", f"/listings/{listing_id}", params={k: v for k, v in (("lat", lat), ("lon", lon)) if v})
    if not ok:
        flash(listing, "danger")
        return redirect(url_for("index"))
    ok_f, farm = api("GET", f"/farms/{listing['farm_id']}")
    return render_template(
        "product.html", listing=listing, farm=farm if ok_f else None, lat=lat, lon=lon, back_url=_back_url(url_for("index"))
    )


@app.route("/farm/<int:farm_id>")
def farm_public(farm_id):
    lat, lon = request.args.get("lat"), request.args.get("lon")
    params = {"limit": 100}
    if lat and lon:
        params.update(lat=lat, lon=lon)
    (ok, farm), (_, reviews), (ok_s, found) = api_many(
        ("GET", f"/farms/{farm_id}"), ("GET", f"/reviews/farm/{farm_id}"), ("GET", "/search", {"params": params})
    )
    if not ok:
        flash(farm, "danger")
        return redirect(url_for("index"))
    reviews = reviews or []
    listings = [r for r in (found if ok_s else []) if r["farm_id"] == farm_id]
    avg = sum(r["stars"] for r in reviews) / len(reviews) if reviews else None
    return render_template(
        "farm_public.html", farm=farm, reviews=reviews, avg_rating=avg, listings=listings,
        lat=lat, lon=lon, back_url=_back_url(url_for("index")),
    )


# ---------- Buyer: cart and checkout (the cart lives in the browser session) ----------
def _cart_details():
    cart = dict(session.get("cart", {}))
    items, changed = [], False
    fetched = api_many(*[("GET", f"/listings/{lid}") for lid in cart])
    for (lid, qty), (ok, listing) in zip(list(cart.items()), fetched):
        if not ok:
            cart.pop(lid)
            changed = True
            continue
        qty = min(float(qty), listing["available_qty"])
        if qty <= 0:
            cart.pop(lid)
            changed = True
            continue
        items.append({"listing": listing, "qty": qty, "line": qty * listing["price_per_unit"]})
    if changed:
        session["cart"] = cart
        flash("Some items are no longer available and were removed from your cart.", "warning")
    subtotal = sum(i["line"] for i in items)
    farm_id = items[0]["listing"]["farm_id"] if items else None
    farm_name = items[0]["listing"]["farm_name"] if items else ""
    return items, farm_id, farm_name, subtotal


@app.route("/cart")
def cart():
    user = session.get("user")
    if user and user["role"] != "buyer":
        return redirect(_home_for(user["role"]))
    items, _, farm_name, subtotal = _cart_details()
    return render_template("cart.html", items=items, farm_name=farm_name, subtotal=subtotal)


@app.post("/cart/add/<int:listing_id>")
def cart_add(listing_id):
    user = session.get("user")
    if user and user["role"] != "buyer":
        flash("Only buyers can use the cart.", "warning")
        return redirect(_home_for(user["role"]))
    qty = _float(request.form.get("qty"), 1)
    if not qty or qty <= 0:
        qty = 1
    ok, listing = api("GET", f"/listings/{listing_id}")
    if not ok:
        flash(listing, "danger")
        return redirect(url_for("index"))
    cart_ = dict(session.get("cart", {}))
    if cart_:
        ok_first, first = api("GET", f"/listings/{next(iter(cart_))}")
        if ok_first and first["farm_id"] != listing["farm_id"]:
            flash("An order can contain items from one farm only. Finish that order or remove those items first.", "warning")
            return redirect(url_for("cart"))
    key = str(listing_id)
    cart_[key] = min(cart_.get(key, 0) + qty, listing["available_qty"])
    session["cart"] = cart_
    lat, lon = request.form.get("lat"), request.form.get("lon")
    if lat and lon:
        session["buyer_loc"] = {"lat": lat, "lon": lon}
    flash(f"{listing['product_name']} added to your cart.", "success")
    return redirect(url_for("cart"))


@app.post("/cart/update/<int:listing_id>")
def cart_update(listing_id):
    cart_ = dict(session.get("cart", {}))
    key = str(listing_id)
    if key in cart_:
        qty = float(cart_[key]) + (1 if request.form.get("action") == "inc" else -1)
        if qty < 1:
            cart_.pop(key)
        else:
            cart_[key] = qty
        session["cart"] = cart_
    return redirect(url_for("cart"))


@app.post("/cart/remove/<int:listing_id>")
def cart_remove(listing_id):
    cart_ = dict(session.get("cart", {}))
    cart_.pop(str(listing_id), None)
    session["cart"] = cart_
    return redirect(url_for("cart"))


@app.route("/order/new/<int:listing_id>")
def order_new(listing_id):
    """Old link: send people to the product page, where they can add it to the cart."""
    return redirect(url_for("product", listing_id=listing_id, lat=request.args.get("lat"), lon=request.args.get("lon")))


@app.route("/checkout", methods=["GET", "POST"])
@login_required("buyer")
def checkout():
    items, farm_id, _, subtotal = _cart_details()
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))
    ok, farm = api("GET", f"/farms/{farm_id}")
    if not ok:
        flash(farm, "danger")
        return redirect(url_for("cart"))
    loc = session.get("buyer_loc", {})
    lat, lon = request.values.get("lat") or loc.get("lat"), request.values.get("lon") or loc.get("lon")

    if request.method == "POST":
        payload = {
            "items": [{"listing_id": i["listing"]["id"], "qty": i["qty"]} for i in items],
            "fulfilment_type": request.form.get("fulfilment_type", "pickup"),
            "payment_method": request.form.get("payment_method", "cod"),
            "delivery_address": request.form.get("delivery_address") or None,
            "delivery_lat": _float(request.form.get("delivery_lat")),
            "delivery_lon": _float(request.form.get("delivery_lon")),
        }
        ok, data = api("POST", "/orders", json=payload)
        if ok:
            session.pop("cart", None)
            return redirect(url_for("order_placed", order_id=data["id"]))
        flash(data, "danger")
    return render_template(
        "checkout.html", items=items, farm=farm, subtotal=subtotal, lat=lat, lon=lon, form=request.form,
        addresses=session.get("addresses", []), pickup_point=items[0]["listing"],
    )


@app.route("/order/<int:order_id>/placed")
@login_required("buyer")
def order_placed(order_id):
    ok, data = api("GET", "/orders/mine")
    order = next((o for o in data if o["id"] == order_id), None) if ok else None
    return render_template("order_placed.html", order=order)


@app.route("/orders")
@login_required("buyer")
def orders():
    tab = "past" if request.args.get("tab") == "past" else "active"
    ok, data = api("GET", "/orders/mine")
    if not ok:
        flash(data, "danger")
    finished = ("completed", "rejected", "cancelled", "failed_delivery")
    shown = [o for o in (data if ok else []) if (o["status"] in finished) == (tab == "past")]
    return render_template("orders.html", orders=shown, tab=tab)


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required("buyer")
def order_cancel(order_id):
    ok, data = api("POST", f"/orders/{order_id}/status", json={"status": "cancelled"})
    flash("Order cancelled." if ok else data, "success" if ok else "danger")
    return redirect(url_for("orders"))


# ---------- Account pages: profile, settings, help, about, saved addresses ----------
DEFAULT_PREFS = {"order_updates": True, "offers": False, "sms": True, "language": "en"}

FAQS = [
    ("How do I track my order?", "Open the Orders tab to see your orders and how far each one has come, from placed to completed."),
    ("Can I change my delivery address?", "Yes. Pick a saved address or add a new one at checkout, before you place the order."),
    ("Which payment methods are accepted?", "Cash on delivery or pickup for now. JazzCash and Easypaisa are coming soon."),
    ("How are farms verified?", "Every farm is checked by the FarmBridge admin, and every new stock is approved before buyers can see it."),
]


@app.route("/profile")
def profile():
    return render_template("profile.html")


@app.route("/settings", methods=["GET", "POST"])
@login_required()
def settings():
    prefs = {**DEFAULT_PREFS, **session.get("prefs", {})}
    if request.method == "POST":
        prefs = {
            "order_updates": bool(request.form.get("order_updates")),
            "offers": bool(request.form.get("offers")),
            "sms": bool(request.form.get("sms")),
            "language": request.form.get("language", "en"),
        }
        session["prefs"] = prefs
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", prefs=prefs)


@app.route("/help")
def help_page():
    return render_template("help.html", faqs=FAQS)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/addresses", methods=["GET", "POST"])
@login_required("buyer")
def addresses():
    saved = list(session.get("addresses", []))
    if request.method == "POST":
        label = request.form.get("label", "").strip()
        address = request.form.get("address", "").strip()
        lat, lon = _float(request.form.get("lat")), _float(request.form.get("lon"))
        if not label or not address or lat is None or lon is None:
            flash("Please enter a label and an address, and set the location on the map.", "danger")
        elif len(saved) >= 5:
            flash("You can save up to 5 addresses. Remove one first.", "warning")
        else:
            saved.append({"label": label, "address": address, "lat": lat, "lon": lon})
            session["addresses"] = saved
            flash("Address saved.", "success")
            return redirect(url_for("addresses"))
    return render_template("addresses.html", addresses=saved)


@app.post("/addresses/<int:index>/delete")
@login_required("buyer")
def address_delete(index):
    saved = list(session.get("addresses", []))
    if 0 <= index < len(saved):
        saved.pop(index)
        session["addresses"] = saved
    return redirect(url_for("addresses"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", title="Page not found", message="We could not find that page.", retry_url=None), 404


@app.errorhandler(413)
def too_large(_error):
    flash("The photos are too big. Each photo must be 5 MB or smaller.", "danger")
    return redirect(request.referrer or url_for("farmer_listings"))


@app.errorhandler(500)
def server_error(_error):
    return render_template(
        "error.html", title="Something went wrong", message="Please try again in a moment.", retry_url=request.path
    ), 500


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
    (ok, farm), (_, listings), (_, orders_) = api_many(("GET", "/farms/me"), ("GET", "/stock/mine"), ("GET", "/orders/farm"))
    if not ok:
        return redirect(url_for("farm_profile"))
    return render_template("farmer_dashboard.html", farm=farm, listings=listings or [], orders=orders_ or [])


@app.route("/farmer/listings")
@login_required("farmer")
def farmer_listings():
    ok, farm = api("GET", "/farms/me")
    if not ok:
        return redirect(url_for("farm_profile"))
    _, listings = api("GET", "/stock/mine")
    return render_template("farmer_listings.html", listings=listings or [])


@app.route("/farmer/listings/new")
@login_required("farmer")
def farmer_add_form():
    ok, farm = api("GET", "/farms/me")
    if not ok:
        return redirect(url_for("farm_profile"))
    _, products = api("GET", "/catalog/products")
    return render_template("farmer_add.html", farm=farm, products=products or [])


def _photo_files():
    """The chosen picture files from the form, ready to send to the API. Empty slots are skipped."""
    files = []
    for item in request.files.getlist("photos"):
        if item and item.filename:
            files.append(("files", (item.filename, item.stream, item.mimetype or "application/octet-stream")))
    return files


@app.route("/farmer/stock", methods=["POST"])
@login_required("farmer")
def farmer_add_stock():
    f = request.form
    photos = _photo_files()
    if len(photos) < 3:
        flash("Please add all 3 photos of your stock.", "danger")
        return redirect(url_for("farmer_add_form"))
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
    if not ok:
        flash(data, "danger")
        return redirect(url_for("farmer_add_form"))
    ok_photos, message = api("POST", f"/stock/{data['id']}/photos", files=photos)
    if ok_photos:
        flash("Stock sent to the admin for approval. Buyers will see it once it is approved.", "success")
    else:
        flash(f"Your stock was saved, but the photos were not uploaded: {message}. Add them below.", "danger")
    return redirect(url_for("farmer_listings"))


@app.route("/farmer/stock/<int:listing_id>/photos", methods=["POST"])
@login_required("farmer")
def farmer_add_photos(listing_id):
    photos = _photo_files()
    if not photos:
        flash("Choose at least one photo.", "danger")
    else:
        ok, data = api("POST", f"/stock/{listing_id}/photos", files=photos)
        flash("Photos added." if ok else data, "success" if ok else "danger")
    return redirect(url_for("farmer_listings"))


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
    return redirect(url_for("farmer_listings"))


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
