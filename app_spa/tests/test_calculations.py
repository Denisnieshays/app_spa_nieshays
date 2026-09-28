from datetime import date, timedelta
from decimal import Decimal
from app.services.calculations import (
    MovementDTO, BatchDTO,
    calculate_stock, calculate_avg_daily_consumption,
    calculate_reorder_point, round_up_to_pack,
    calculate_recommended_quantity, calculate_cost,
)

def test_calculate_stock_from_movements():
    batches = [BatchDTO(id=1, quantity=Decimal("100"), expiry_date=None, price=Decimal("10"))]
    movements = [
        MovementDTO(date=date.today(), type="consume", quantity=Decimal("30"), batch_id=1),
        MovementDTO(date=date.today(), type="writeoff", quantity=Decimal("10"), batch_id=1),
    ]
    assert calculate_stock(batches, movements) == Decimal("60")

def test_avg_daily_consumption():
    today = date.today()
    movements = [
        MovementDTO(date=today - timedelta(days=10), type="consume", quantity=Decimal("90"), batch_id=1),
    ]
    avg = calculate_avg_daily_consumption(movements, days=90, today=today)
    assert avg == Decimal("1")

def test_reorder_point():
    rp = calculate_reorder_point(Decimal("5"), lead_time_days=7, safety_stock_days=3)
    assert rp == Decimal("50")

def test_round_up_to_pack_and_min_lot():
    assert round_up_to_pack(Decimal("23"), pack_size=10, min_lot=20) == Decimal("30")
    assert round_up_to_pack(Decimal("5"), pack_size=10, min_lot=20) == Decimal("20")
    assert round_up_to_pack(Decimal("0"), pack_size=10, min_lot=20) == Decimal("0")

def test_recommended_quantity_and_cost():
    qty = calculate_recommended_quantity(
        reorder_point=Decimal("100"), stock=Decimal("20"),
        incoming=Decimal("10"), pack_size=12, min_lot=24,
    )
    # (100 - 20 - 10) = 70 → округление до 12 → 72
    assert qty == Decimal("72")
    assert calculate_cost(qty, Decimal("9.99")) == Decimal("719.28")
