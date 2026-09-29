from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Movement, MovementType, Product, Location, Batch
from app.schemas import (
    MovementCreate, MovementResponse, MovementCreatedResponse,
    MovementListResponse, MovementTypeEnum,
)
from app.services.calculations import MovementDTO, BatchDTO, calculate_stock
from app.services.fefo import FEFOBatch, apply_fefo

router = APIRouter(prefix="/api/movements", tags=["movements"])


# ---------- helpers ----------
def _get_product(db: Session, sku: str) -> Product:
    p = db.query(Product).filter(Product.sku == sku).first()
    if not p:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' не найден")
    return p


def _get_location(db: Session, code: str) -> Location:
    loc = db.query(Location).filter(Location.code == code).first()
    if not loc:
        raise HTTPException(status_code=404, detail=f"Объект '{code}' не найден")
    return loc


def _calc_remaining(db: Session, product_id: int, location_id: int) -> Decimal:
    """Текущий остаток по позиции и объекту = партии − расход/списание + возвраты."""
    batches = db.query(Batch).filter(
        Batch.product_id == product_id, Batch.location_id == location_id
    ).all()
    movements = db.query(Movement).filter(
        Movement.product_id == product_id, Movement.location_id == location_id
    ).all()

    batch_dtos = [
        BatchDTO(id=b.id, quantity=b.quantity, expiry_date=b.expiry_date, price=b.price)
        for b in batches
    ]
    mv_dtos = [
        MovementDTO(date=m.date, type=m.type.value, quantity=m.quantity, batch_id=m.batch_id)
        for m in movements
    ]
    return calculate_stock(batch_dtos, mv_dtos)


# ---------- POST /api/movements ----------
@router.post("", response_model=MovementCreatedResponse, status_code=201)
def create_movement(payload: MovementCreate, db: Session = Depends(get_db)):
    # 1. Дата не в будущем
    if payload.date > date.today():
        raise HTTPException(status_code=422, detail="Дата операции не может быть в будущем")

    # 2. Товар и объект
    product = _get_product(db, payload.sku)
    location = _get_location(db, payload.location_code)

    # 3. Дубликат документа
    existing = db.query(Movement).filter(
        Movement.document_number == payload.document_number,
        Movement.product_id == product.id,
        Movement.location_id == location.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Движение с документом '{payload.document_number}' уже существует",
        )

    # 4. Текущий остаток (до операции)
    current_stock = _calc_remaining(db, product.id, location.id)

    # 5. FEFO для consume/writeoff
    batch_id = payload.batch_id
    if payload.type in (MovementTypeEnum.consume, MovementTypeEnum.writeoff):
        if payload.quantity > current_stock:
            raise HTTPException(
                status_code=422,
                detail=f"Недостаточно остатка. Доступно: {current_stock}",
            )
        if batch_id is None and payload.type == MovementTypeEnum.consume:
            batches = db.query(Batch).filter(
                Batch.product_id == product.id,
                Batch.location_id == location.id,
            ).all()
            fefo_batches = [
                FEFOBatch(id=b.id, quantity=b.quantity, expiry_date=b.expiry_date)
                for b in batches
            ]
            try:
                result = apply_fefo(fefo_batches, payload.quantity)
                batch_id = result.allocations[0][0]
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

    # 6. Создать движение
    mv = Movement(
        date=payload.date,
        product_id=product.id,
        location_id=location.id,
        type=MovementType(payload.type.value),
        quantity=payload.quantity,
        batch_id=batch_id,
        document_number=payload.document_number,
    )
    db.add(mv)
    db.commit()
    db.refresh(mv)

    # 7. Новый остаток
    new_stock = _calc_remaining(db, product.id, location.id)

    return MovementCreatedResponse(id=mv.id, remaining_stock=new_stock)


# ---------- GET /api/movements ----------
@router.get("", response_model=MovementListResponse)
def list_movements(
    sku: str | None = Query(None),
    location_code: str | None = Query(None),
    type: MovementTypeEnum | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Movement)

    if sku:
        product = _get_product(db, sku)
        query = query.filter(Movement.product_id == product.id)

    if location_code:
        location = _get_location(db, location_code)
        query = query.filter(Movement.location_id == location.id)

    if type:
        query = query.filter(Movement.type == MovementType(type.value))

    if date_from:
        query = query.filter(Movement.date >= date_from)
    if date_to:
        query = query.filter(Movement.date <= date_to)

    total = query.count()
    items = (
        query.order_by(Movement.date.desc(), Movement.id.desc())
        .limit(limit).offset(offset).all()
    )

    return MovementListResponse(
        items=[MovementResponse.model_validate(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )
