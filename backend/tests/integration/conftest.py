"""End-to-end tests against a REAL PostgreSQL database (never run against production data!).

    export TEST_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/cakestudio_test
    pytest tests/integration

The schema is dropped and rebuilt with the Alembic migrations at the start of the run.
"""
import os

import pytest

URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("set TEST_DATABASE_URL to run integration tests", allow_module_level=True)

os.environ["DATABASE_URL"] = URL
os.environ.setdefault("JWT_SECRET", "integration-test-secret-integration-test")
os.environ["SEED_ADMIN_EMAIL"] = "root@example.com"
os.environ["SEED_ADMIN_PASSWORD"] = "Correct-Horse-Battery-9"
os.environ["MEDIA_DIR"] = os.environ.get("MEDIA_DIR", "/tmp/cakestudio-test-media")

from datetime import date, timedelta  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

ADMIN = ("root@example.com", "Correct-Horse-Battery-9")


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.db.session import get_engine

    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config("alembic.ini"), "head")
    from app import seed

    seed.run()
    yield


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    from app.services.ratelimit import limiter

    limiter._hits.clear()


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    with TestClient(app) as c:
        yield c


def bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="session")
def admin(client):
    r = client.post("/api/v1/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    return bearer(r.json()["access_token"])


@pytest.fixture(scope="session")
def product(client, admin):
    """A simple tracked-stock product with exactly 3 in stock."""
    r = client.post("/api/v1/admin/products", headers=admin, json={"name": "Test Chocolate Cake", "base_price": "25.00", "track_stock": True, "stock_qty": 3, "prep_time_hours": 0})
    assert r.status_code == 201, r.text
    return r.json()


def new_cart_with(client, product_id: int, qty: int = 1) -> str:
    tok = client.post("/api/v1/cart").json()["token"]
    r = client.post(f"/api/v1/cart/{tok}/items", json={"product_id": product_id, "quantity": qty})
    assert r.status_code == 201, r.text
    return tok


def order_day() -> str:
    return (date.today() + timedelta(days=3)).isoformat()


def checkout(client, cart: str, phone="+923001234567", headers=None, key=None):
    day = order_day()
    slot = client.get(f"/api/v1/public/delivery/slots?day={day}").json()[0]["slot_id"]
    h = dict(headers or {})
    if key:
        h["Idempotency-Key"] = key
    return client.post("/api/v1/checkout", headers=h, json={
        "cart_token": cart, "full_name": "Test Customer", "phone": phone, "email": "buyer@example.com", "fulfillment": "delivery",
        "address": {"line": "12 Baker Street", "city": "Lahore"}, "day": day, "slot_id": slot, "payment_method": "cod"})
