from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_has_all_endpoints():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in ["/api/movements", "/api/stock", "/api/stock/{sku}", "/api/forecast", "/api/alerts"]:
        assert p in paths


def test_movements_list():
    r = client.get("/api/movements?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert len(body["items"]) <= 5


def test_movement_invalid_sku():
    r = client.post("/api/movements", json={
        "date": str(date.today()),
        "sku": "UNKNOWN-SKU",
        "location_code": "WH-01",
        "type": "receipt",
        "quantity": 10,
        "document_number": "TEST-UNKNOWN",
    })
    assert r.status_code == 404


def test_movement_future_date():
    r = client.post("/api/movements", json={
        "date": str(date.today() + timedelta(days=10)),
        "sku": "OIL-MASS-01",
        "location_code": "WH-01",
        "type": "receipt",
        "quantity": 10,
        "document_number": "TEST-FUTURE",
    })
    assert r.status_code == 422


def test_stock_list():
    r = client.get("/api/stock")
    assert r.status_code == 200
    assert "items" in r.json()


def test_stock_detail_unknown():
    r = client.get("/api/stock/UNKNOWN")
    assert r.status_code == 404


def test_alerts():
    r = client.get("/api/alerts")
    assert r.status_code == 200
    assert "items" in r.json()
