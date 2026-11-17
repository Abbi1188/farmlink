import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers all tables)
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, catalog, farms, notifications, orders, reviews, search, stock
from app.services.bootstrap import ensure_default_admin
from app.services.order_service import expire_stale_orders


def _run_expiry() -> None:
    db = SessionLocal()
    try:
        expire_stale_orders(db)
    finally:
        db.close()


async def _expiry_loop() -> None:
    """Every 5 minutes cancel orders the farmer never answered and release the stock."""
    while True:
        await asyncio.sleep(300)
        await asyncio.to_thread(_run_expiry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # fine for development; use migrations in production
    db = SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()
    task = asyncio.create_task(_expiry_loop())
    yield
    task.cancel()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, farms, catalog, stock, search, orders, reviews, notifications, admin):
    app.include_router(module.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name}
