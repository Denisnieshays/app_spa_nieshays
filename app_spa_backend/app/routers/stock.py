from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, Location, Batch, Movement
from app.schemas import (
    StockItem, StockListResponse,
    StockDetailResponse, StockLocationDetail, BatchDetail,
)
from app.services.calculations import (
    BatchDTO, MovementDTO,
    calculate_stock, calculate_avg_daily_consumption, calculate_days_of_stock,
)

router = APIRouter(prefix="/api/stock", tags=["stock"])


def _aggregate_for(db: Session, product: Product, location: Location) -> StockItem:
    batches = db.query(Batch).filter(
        Batch.product_id == product.id, Batch.location_id == location.id
    ).all()
    movements = db.query(Movement).filter(
        Movement.product_id == product.id, Movement.location_id == location.id
    ).all()

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

    expiries = [b.expiry_date for b in batches if b.expiry_date]
    nearest = min(expiries) if expiries else None

    return StockItem(
        sku=product.sku,
        name=product.name,
        location_code=location.code,
        location_name=location.name,
        stock=stock,
        avg_daily_consumption=avg_daily,
        days_of_stock=days,
        nearest_expiry=nearest,
    )


@router.get("", response_model=StockListResponse)
def list_stock(db: Session = Depends(get_db)):
    """Текущие остатки по всем позициям и объектам."""
    items: list[StockItem] = []
    products = db.query(Product).all()
    locations = db.query(Location).all()

    for p in products:
        for loc in locations:
            # есть ли вообще партии или движения по этой позиции и объекту?
            has_batches = db.query(Batch).filter(
                Batch.product_id == p.id, Batch.location_id == loc.id
            ).count() > 0
            has_moves = db.query(Movement).filter(
                Movement.product_id == p.id, Movement.location_id == loc.id
            ).count() > 0
            if not has_batches and not has_moves:
                continue
            items.append(_aggregate_for(db, p, loc))

    return StockListResponse(items=items)


@router.get("/{sku}", response_model=StockDetailResponse)
def stock_detail(sku: str, db: Session = Depends(get_db)):
    """Детализация по позиции: остатки по объектам и партиям."""
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' не найден")

    locations = db.query(Location).all()
    loc_details: list[StockLocationDetail] = []
    total_stock = Decimal("0")

    for loc in locations:
        batches = db.query(Batch).filter(
            Batch.product_id == product.id, Batch.location_id == loc.id
        ).all()
        movements = db.query(Movement).filter(
            Movement.product_id == product.id, Movement.location_id == loc.id
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
        total_stock += stock

        batch_details = []
        for b in batches:
            # остаток по конкретной партии
            b_dto = BatchDTO(id=b.id, quantity=b.quantity, expiry_date=b.expiry_date, price=b.price)
            remaining = calculate_stock([b_dto], mv_dtos)
            batch_details.append(BatchDetail(
                batch_id=b.id,
                quantity=remaining,
                expiry_date=b.expiry_date,
                price=b.price,
                invoice_number=b.invoice_number,
            ))

        loc_details.append(StockLocationDetail(
            location_code=loc.code,
            location_name=loc.name,
            stock=stock,
            batches=batch_details,
        ))

    return StockDetailResponse(
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        pack_size=product.pack_size,
        min_lot=product.min_lot,
        price=product.price,
        lead_time_days=product.lead_time_days,
        total_stock=total_stock,
        locations=loc_details,
    )
