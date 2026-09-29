from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, Location, Batch, Movement
from app.schemas import AlertItem, AlertsResponse
from app.services.calculations import (
    BatchDTO, MovementDTO,
    calculate_stock, calculate_avg_daily_consumption, calculate_days_of_stock,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

EXPIRY_THRESHOLD_DAYS = 30   # порог «приближается срок годности»
NO_MOVEMENT_DAYS = 60        # порог «нет движения»


@router.get("", response_model=AlertsResponse)
def alerts(db: Session = Depends(get_db)):
    today = date.today()
    items: list[AlertItem] = []

    products = db.query(Product).all()
    locations = db.query(Location).all()

    for p in products:
        for loc in locations:
            batches = db.query(Batch).filter(
                Batch.product_id == p.id, Batch.location_id == loc.id
            ).all()
            movements = db.query(Movement).filter(
                Movement.product_id == p.id, Movement.location_id == loc.id
            ).all()

            if not batches and not movements:
                continue

            batch_dtos = [
                BatchDTO(id=b.id, quantity=b.quantity, expiry_date=b.expiry_date, price=b.price)
                for b in batches
            ]
            mv_dtos = [
                MovementDTO(date=m.date, type=m.type.value, quantity=m.quantity, batch_id=m.batch_id)
                for m in movements
            ]

            stock = calculate_stock(batch_dtos, mv_dtos)
            avg_daily = calculate_avg_daily_consumption(mv_dtos, days=90)
            days = calculate_days_of_stock(stock, avg_daily)

            # 1. Риск дефицита: запас в днях < срока поставки
            if avg_daily > 0 and days is not None and days < p.lead_time_days:
                items.append(AlertItem(
                    type="deficit",
                    severity="high" if days < p.lead_time_days / 2 else "medium",
                    sku=p.sku,
                    location_code=loc.code,
                    message=f"Запас {days:.1f} дн. меньше срока поставки {p.lead_time_days} дн.",
                    metrics={
                        "days_of_stock": str(days),
                        "lead_time_days": p.lead_time_days,
                        "stock": str(stock),
                        "avg_daily": str(avg_daily),
                    },
                ))

            # 2. Риск списания: срок годности ближе, чем порог
            for b in batches:
                if b.expiry_date is None:
                    continue
                days_to_expiry = (b.expiry_date - today).days
                b_remaining = calculate_stock(
                    [BatchDTO(id=b.id, quantity=b.quantity, expiry_date=b.expiry_date, price=b.price)],
                    mv_dtos,
                )
                if b_remaining > 0 and 0 <= days_to_expiry <= EXPIRY_THRESHOLD_DAYS:
                    items.append(AlertItem(
                        type="expiry",
                        severity="high" if days_to_expiry <= 7 else "medium",
                        sku=p.sku,
                        location_code=loc.code,
                        message=f"Партия #{b.id} истекает через {days_to_expiry} дн. Остаток: {b_remaining}",
                        metrics={
                            "batch_id": b.id,
                            "expiry_date": str(b.expiry_date),
                            "days_to_expiry": days_to_expiry,
                            "remaining": str(b_remaining),
                        },
                    ))

            # 3. Риск излишка: запас в днях > 180 (при наличии расхода)
            if avg_daily > 0 and days is not None and days > 180:
                items.append(AlertItem(
                    type="overstock",
                    severity="medium",
                    sku=p.sku,
                    location_code=loc.code,
                    message=f"Излишек: запаса хватит на {days:.0f} дн.",
                    metrics={
                        "days_of_stock": str(days),
                        "stock": str(stock),
                        "avg_daily": str(avg_daily),
                    },
                ))

            # 4. Нет движения
            if movements:
                last_date = max(m.date for m in movements)
                days_since = (today - last_date).days
                if days_since > NO_MOVEMENT_DAYS:
                    items.append(AlertItem(
                        type="no_movement",
                        severity="low",
                        sku=p.sku,
                        location_code=loc.code,
                        message=f"Нет движений {days_since} дн. (последнее: {last_date})",
                        metrics={
                            "days_since_last_movement": days_since,
                            "last_movement_date": str(last_date),
                        },
                    ))

    return AlertsResponse(items=items)
