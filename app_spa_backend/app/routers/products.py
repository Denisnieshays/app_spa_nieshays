from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional

from app.db import get_db
from app.models import Product

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = "шт"
    pack_size: int = Field(1, ge=1)
    min_lot: int = Field(1, ge=1)
    price: Decimal = Field(..., ge=0)
    lead_time_days: int = Field(7, ge=0)


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    unit: str
    pack_size: int
    min_lot: int
    price: Decimal
    lead_time_days: int

    class Config:
        from_attributes = True


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """Создать новый товар."""
    existing = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Товар с SKU '{payload.sku}' уже существует"
        )
    product = Product(
        sku=payload.sku,
        name=payload.name,
        unit=payload.unit,
        pack_size=payload.pack_size,
        min_lot=payload.min_lot,
        price=payload.price,
        lead_time_days=payload.lead_time_days,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    """Список всех товаров."""
    return db.query(Product).all()


@router.get("/{sku}", response_model=ProductResponse)
def get_product(sku: str, db: Session = Depends(get_db)):
    """Получить товар по SKU."""
    product = db.query(Product).filter(Product.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' не найден")
    return product
