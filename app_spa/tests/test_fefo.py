from datetime import date, timedelta
from decimal import Decimal
import pytest
from app.services.fefo import FEFOBatch, apply_fefo

def test_fefo_picks_earliest_expiry():
    today = date.today()
    batches = [
        FEFOBatch(id=1, quantity=Decimal("10"), expiry_date=today + timedelta(days=30)),
        FEFOBatch(id=2, quantity=Decimal("10"), expiry_date=today + timedelta(days=5)),
        FEFOBatch(id=3, quantity=Decimal("10"), expiry_date=today + timedelta(days=15)),
    ]
    result = apply_fefo(batches, Decimal("15"), today=today)
    assert result.allocations == [(2, Decimal("10")), (3, Decimal("5"))]

def test_fefo_skips_expired():
    today = date.today()
    batches = [
        FEFOBatch(id=1, quantity=Decimal("10"), expiry_date=today - timedelta(days=1)),
        FEFOBatch(id=2, quantity=Decimal("10"), expiry_date=today + timedelta(days=10)),
    ]
    result = apply_fefo(batches, Decimal("5"), today=today)
    assert result.allocations == [(2, Decimal("5"))]

def test_fefo_insufficient_stock():
    today = date.today()
    batches = [FEFOBatch(id=1, quantity=Decimal("5"), expiry_date=today + timedelta(days=10))]
    with pytest.raises(ValueError, match="Недостаточно остатка"):
        apply_fefo(batches, Decimal("10"), today=today)
