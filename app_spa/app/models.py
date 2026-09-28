from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db import Base

class MovementType(str, enum.Enum):
    receipt = "receipt"
    consume = "consume"
    writeoff = "writeoff"
    return_ = "return"
    correction = "correction"

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    sku = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    unit = Column(String(32), nullable=False, default="шт")
    pack_size = Column(Integer, nullable=False, default=1)
    min_lot = Column(Integer, nullable=False, default=1)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    lead_time_days = Column(Integer, nullable=False, default=7)
    batches = relationship("Batch", back_populates="product")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    quantity = Column(Numeric(14, 3), nullable=False, default=0)
    expiry_date = Column(Date, nullable=True)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    invoice_number = Column(String(64), nullable=True)
    product = relationship("Product", back_populates="batches")
    location = relationship("Location")

class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (
        UniqueConstraint("document_number", "product_id", "location_id", name="uq_movement_doc"),
    )
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    type = Column(Enum(MovementType), nullable=False)
    quantity = Column(Numeric(14, 3), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    document_number = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    product = relationship("Product")
    location = relationship("Location")
    batch = relationship("Batch")
