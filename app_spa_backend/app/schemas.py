from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class MovementTypeEnum(str, Enum):
    receipt = "receipt"
    consume = "consume"
    writeoff = "writeoff"
    return_ = "return"
    correction = "correction"


# ---------- Movements ----------
class MovementCreate(BaseModel):
    date: date
    sku: str = Field(..., min_length=1)
    location_code: str = Field(..., min_length=1)
    type: MovementTypeEnum
    quantity: Decimal = Field(..., gt=0)
    batch_id: Optional[int] = None
    document_number: str = Field(..., min_length=1)


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    product_id: int
    location_id: int
    type: MovementTypeEnum
    quantity: Decimal
    batch_id: Optional[int]
    document_number: str
    created_at: datetime


class MovementCreatedResponse(BaseModel):
    id: int
    remaining_stock: Decimal


class MovementListResponse(BaseModel):
    items: List[MovementResponse]
    total: int
    limit: int
    offset: int


# ---------- Stock ----------
class StockItem(BaseModel):
    sku: str
    name: str
    location_code: str
    location_name: str
    stock: Decimal
    avg_daily_consumption: Decimal
    days_of_stock: Optional[Decimal]
    nearest_expiry: Optional[date]


class StockListResponse(BaseModel):
    items: List[StockItem]


class BatchDetail(BaseModel):
    batch_id: int
    quantity: Decimal
    expiry_date: Optional[date]
    price: Decimal
    invoice_number: Optional[str]


class StockLocationDetail(BaseModel):
    location_code: str
    location_name: str
    stock: Decimal
    batches: List[BatchDetail]


class StockDetailResponse(BaseModel):
    sku: str
    name: str
    unit: str
    pack_size: int
    min_lot: int
    price: Decimal
    lead_time_days: int
    total_stock: Decimal
    locations: List[StockLocationDetail]


# ---------- Forecast ----------
class ForecastRequest(BaseModel):
    sku: str
    location_code: str
    horizon_days: int = Field(..., gt=0)
    safety_stock_days: int = Field(..., ge=0)


class ForecastExplanation(BaseModel):
    inputs: dict
    formulas: dict
    assumptions: List[str]


class ForecastResponse(BaseModel):
    sku: str
    location_code: str
    horizon_days: int
    forecast_consumption: Decimal
    current_stock: Decimal
    incoming: Decimal
    safety_stock: Decimal
    reorder_point: Decimal
    recommended_quantity: Decimal
    estimated_cost: Decimal
    recommended_order_date: Optional[date]
    explanation: ForecastExplanation


# ---------- Alerts ----------
class AlertItem(BaseModel):
    type: str          # deficit | overstock | expiry | no_movement
    severity: str      # high | medium | low
    sku: str
    location_code: str
    message: str
    metrics: dict


class AlertsResponse(BaseModel):
    items: List[AlertItem]
