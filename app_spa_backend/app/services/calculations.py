from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Iterable

@dataclass
class MovementDTO:
    date: date
    type: str
    quantity: Decimal
    batch_id: int | None = None

@dataclass
class BatchDTO:
    id: int
    quantity: Decimal
    expiry_date: date | None
    price: Decimal

def calculate_batch_remaining(batch: BatchDTO, movements: Iterable[MovementDTO]) -> Decimal:
    """Остаток по конкретной партии: приход минус расход/списание."""
    consumed = sum(
        (m.quantity for m in movements if m.batch_id == batch.id and m.type in ("consume", "writeoff")),
        Decimal("0"),
    )
    returned = sum(
        (m.quantity for m in movements if m.batch_id == batch.id and m.type == "return"),
        Decimal("0"),
    )
    return batch.quantity + returned - consumed

def calculate_stock(batches: Iterable[BatchDTO], movements: Iterable[MovementDTO]) -> Decimal:
    """Суммарный остаток по позиции и объекту."""
    return sum((calculate_batch_remaining(b, movements) for b in batches), Decimal("0"))

def calculate_avg_daily_consumption(
    movements: Iterable[MovementDTO], days: int = 90, today: date | None = None
) -> Decimal:
    """Средний расход в день за N дней (только consume)."""
    today = today or date.today()
    start = today - timedelta(days=days)
    total = sum(
        (m.quantity for m in movements if m.type == "consume" and start <= m.date <= today),
        Decimal("0"),
    )
    return (total / Decimal(days)) if days > 0 else Decimal("0")

def calculate_days_of_stock(stock: Decimal, avg_daily: Decimal) -> Decimal | None:
    if avg_daily <= 0:
        return None
    return stock / avg_daily

def calculate_reorder_point(avg_daily: Decimal, lead_time_days: int, safety_stock_days: int) -> Decimal:
    return avg_daily * Decimal(lead_time_days + safety_stock_days)

def round_up_to_pack(quantity: Decimal, pack_size: int, min_lot: int) -> Decimal:
    """Округление вверх до кратности упаковки и не меньше минимальной партии."""
    if quantity <= 0:
        return Decimal("0")
    pack = Decimal(pack_size or 1)
    lots = (quantity / pack).to_integral_value(rounding=ROUND_CEILING)
    result = lots * pack
    if result < min_lot:
        result = Decimal(min_lot)
    return result

def calculate_recommended_quantity(
    reorder_point: Decimal, stock: Decimal, incoming: Decimal,
    pack_size: int, min_lot: int
) -> Decimal:
    raw = reorder_point - stock - incoming
    if raw <= 0:
        return Decimal("0")
    return round_up_to_pack(raw, pack_size, min_lot)

def calculate_cost(quantity: Decimal, price: Decimal) -> Decimal:
    return (quantity * price).quantize(Decimal("0.01"))

def calculate_recommended_order_date(days_of_stock: Decimal | None, today: date | None = None) -> date | None:
    if days_of_stock is None:
        return None
    today = today or date.today()
    return today + timedelta(days=int(days_of_stock))
