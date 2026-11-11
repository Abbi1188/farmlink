# FarmLink

A marketplace that connects city buyers with farmers. Farmers list organic and fresh stock (grains, dairy and more) with its location; buyers search by product and place, see which farms have it, and choose **delivery** or **pickup**.

Python 3.10 or newer. Backend: FastAPI + SQLAlchemy. Frontend: Flask + Jinja templates. Database: SQLite for development, PostgreSQL for production.

## Project structure

```
farmlink/
├── .gitignore
├── .env.example            copy to backend/.env
├── README.md
├── backend/                REST API (FastAPI)
│   ├── run.py              start the API
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py         app setup, router registration, expiry job
│   │   ├── config.py       settings from .env
│   │   ├── database.py     engine, session, Base
│   │   ├── core/           constants, security (JWT, roles), geo distance
│   │   ├── models/         user, farm, catalog (category, product, stock listing), order, review, notification
│   │   ├── schemas/        request and response shapes (Pydantic)
│   │   ├── routers/        auth, farms, catalog, stock, search, orders, reviews, notifications, admin
│   │   └── services/       stock rules, location search, order lifecycle, notifications
│   └── tests/              automated tests
├── frontend/               web app (Flask)
│   ├── app.py              pages and forms
│   ├── api_client.py       calls the backend
│   ├── requirements.txt
│   ├── templates/          HTML pages
│   └── static/             css and js
└── database/
    ├── init_db.py          create tables and catalogue
    ├── seed_demo.py        demo users and stock (development only)
    ├── schema.sql          reference PostgreSQL schema
    ├── migrations/         future Alembic migrations
    └── README.md
```

## Run it

```bash
# 1. Virtual environment
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS or Linux

# 2. Install
pip install -r backend/requirements.txt -r frontend/requirements.txt

# 3. Settings (Windows: copy .env.example backend\.env)
cp .env.example backend/.env

# 4. Database
python database/init_db.py
python database/seed_demo.py

# 5. Backend (terminal 1)         API docs at http://localhost:8000/docs
cd backend
uvicorn app.main:app --reload --port 8000

# 6. Frontend (terminal 2)        site at http://localhost:5000
cd frontend
python app.py
```

Demo logins after `seed_demo.py`: admin `03000000000` / `admin123`, farmer `03007654321` / `farmer123`, buyer `03001234567` / `buyer123`.

Run the tests: `cd backend && pytest`

## Git

```bash
git init
git add .
git commit -m "Initial FarmLink project structure"
```

The `.gitignore` already excludes `.env`, virtual environments, the SQLite database, uploads and caches.

## What is built

- Sign up and login by phone number; roles: farmer, buyer, admin
- Farm profile with location, pickup and delivery settings; admin approval before publishing
- Farmers add, edit, pause stock with its own location and optional region of origin
- Buyer search by product, city, district, region of origin, radius and "near me"; each result is labelled Delivers to you, Pickup only or Not available at your location
- Orders from one farm at a time; stock is reserved on order and released on reject, cancel or timeout (30 minutes)
- Order lifecycle with a 4-digit code the buyer gives at handover
- Reviews after completed orders, in-app notifications, admin farm approval

## Not built yet (next steps)

- Photo upload, online payments (JazzCash, Easypaisa), live delivery tracking
- Map view in the frontend, Urdu and Pashto translations, push notifications
- Subscriptions (daily milk), admin web dashboard pages
- Database migrations (Alembic) and production deployment settings
