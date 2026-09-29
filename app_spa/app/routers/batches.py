from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date
from pydantic import BaseModel, Field
from typing import Optional

from app.db import get_db
from app.models import Product, Location, Batch, Movement, MovementType

router = APIRouter(prefix="/api/batches", tags=["batches"])


class BatchCreate(BaseModel):
    sku: str = Field(..., min_length=1)
    location_code: str = Field(..., min_length=1)
    quantity: Decimal = Field(..., gt=0)
    expiry_date: Optional[date] = None
    price: Optional[Decimal] = None  # если не указана — берётся из товара
    invoice_number: str = Field(..., min_length=1)


class BatchResponse(BaseModel):
    id: int
    product_id: int
    location_id: int
    quantity: Decimal
    expiry_date: Optional[date]
    price: Decimal
    invoice_number: Optional[str]
    movement_id: int

    class Config:
        from_attributes = True


@router.post("", response_model=BatchResponse, status_code=201)
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    """Создать партию (приход). Автоматически создаёт движение receipt."""
    product = db.query(Product).filter(Product.sku == payload.sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU '{payload.sku}' не найден")

    location = db.query(Location).filter(Location.code == payload.location_code).first()
    if not location:
        raise HTTPException(status_code=404, detail=f"Объект '{payload.location_code}' не найден")

    # Дубликат накладной по этому товару и объекту
    existing = db.query(Batch).filter(
        Batch.product_id == product.id,
        Batch.location_id == location.id,
        Batch.invoice_number == payload.invoice_number,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Партия с накладной '{payload.invoice_number}' уже существует"
        )

    # Создаём партию
    batch = Batch(
        product_id=product.id,
        location_id=location.id,
        quantity=payload.quantity,
        expiry_date=payload.expiry_date,
        price=payload.price if payload.price is not None else product.price,
        invoice_number=payload.invoice_number,
    )
    db.add(batch)
    db.flush()

    # Создаём движение receipt
    movement = Movement(
        date=date.today(),
        product_id=product.id,
        location_id=location.id,
        type=MovementType.receipt,
        quantity=payload.quantity,
        batch_id=batch.id,
        document_number=payload.invoice_number,
    )
    db.add(movement)
    db.commit()
    db.refresh(batch)
    db.refresh(movement)

    return BatchResponse(
        id=batch.id,
        product_id=batch.product_id,
        location_id=batch.location_id,
        quantity=batch.quantity,
        expiry_date=batch.expiry_date,
        price=batch.price,
        invoice_number=batch.invoice_number,
        movement_id=movement.id,
    )


@router.get("")
def list_batches(sku: Optional[str] = None, db: Session = Depends(get_db)):
    """Список партий (опционально — по SKU)."""
    query = db.query(Batch)
    if sku:
        product = db.query(Product).filter(Product.sku == sku).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"SKU '{sku}' не найден")
        query = query.filter(Batch.product_id == product.id)
    batches = query.all()
    return [
        {
            "id": b.id,
            "product_id": b.product_id,
            "location_id": b.location_id,
            "quantity": str(b.quantity),
            "expiry_date": str(b.expiry_date) if b.expiry_date else None,
            "price": str(b.price),
            "invoice_number": b.invoice_number,
        }
        for b in batches
    ]
