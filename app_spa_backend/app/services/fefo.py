from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

@dataclass
class FEFOBatch:
    id: int
    quantity: Decimal
    expiry_date: date | None

@dataclass
class FEFOResult:
    allocations: list[tuple[int, Decimal]]  # (batch_id, quantity)
    remaining: Decimal

def apply_fefo(
    batches: Iterable[FEFOBatch],
    consume_qty: Decimal,
    today: date | None = None,
) -> FEFOResult:
    """
    FEFO: сначала партии с ближайшим сроком годности.
    Партии с истёкшим сроком игнорируются (закрываются отдельной операцией writeoff).
    """
    today = today or date.today()
    valid = [
        b for b in batches
        if b.quantity > 0 and (b.expiry_date is None or b.expiry_date >= today)
    ]
    valid.sort(key=lambda b: (b.expiry_date is None, b.expiry_date or date.max))

    allocations: list[tuple[int, Decimal]] = []
    remaining = consume_qty

    for b in valid:
        if remaining <= 0:
            break
        take = min(b.quantity, remaining)
        allocations.append((b.id, take))
        remaining -= take

    if remaining > 0:
        raise ValueError(f"Недостаточно остатка для списания. Не хватает: {remaining}")

    return FEFOResult(allocations=allocations, remaining=Decimal("0"))
