from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.db import get_db
from app.models import Product, Location, Batch, Movement
from app.services.calculations import (
    BatchDTO, MovementDTO,
    calculate_stock, calculate_avg_daily_consumption, calculate_days_of_stock,
    calculate_reorder_point, calculate_recommended_quantity, calculate_cost,
)

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


# ---------- Схемы ----------
class ForecastRequest(BaseModel):
    sku: str
    location_code: str
    horizon_days: int = Field(..., gt=0)
    safety_stock_days: int = Field(7, ge=0)


class Period(BaseModel):
    from_: date = Field(..., alias="from")
    to: date
    days: int

    class Config:
        populate_by_name = True


class Warning(BaseModel):
    level: str   # info | warning | critical
    message: str


class ForecastExplanation(BaseModel):
    data_used: list[str]
    formulas: list[str]
    assumptions: list[str]
    as_of: date


class ForecastResponse(BaseModel):
    sku: str
    name: str
    unit: str
    location: str
    period: dict
    avg_daily_consumption: Decimal
    forecast_demand: Decimal
    current_stock: Decimal
    incoming_qty: Decimal
    safety_stock: Decimal
    reorder_point: Decimal
    recommended_purchase_qty: Decimal
    unit_price: Decimal
    estimated_cost: Decimal
    recommended_order_date: Optional[date]
    stockout_date: Optional[date]
    explanation: ForecastExplanation
    warnings: list[Warning]


# ---------- Эндпоинт ----------
@router.post("", response_model=ForecastResponse)
def forecast(payload: ForecastRequest, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.sku == payload.sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"SKU '{payload.sku}' не найден")
    location = db.query(Location).filter(Location.code == payload.location_code).first()
    if not location:
        raise HTTPException(status_code=404, detail=f"Объект '{payload.location_code}' не найден")

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

    today = date.today()
    period_to = today + timedelta(days=payload.horizon_days)

    # 1. Остаток
    current_stock = calculate_stock(batch_dtos, mv_dtos)

    # 2. Средний расход за 90 дней
    avg_daily = calculate_avg_daily_consumption(mv_dtos, days=90)

    # 3. Поставки в пути (упрощённо: 0)
    incoming = Decimal("0")

    # 4. Страховой запас в единицах
    safety_stock = avg_daily * Decimal(payload.safety_stock_days)

    # 5. Точка заказа
    reorder_point = calculate_reorder_point(
        avg_daily=avg_daily,
        lead_time_days=product.lead_time_days,
        safety_stock_days=payload.safety_stock_days,
    )

    # 6. Прогноз спроса за период
    forecast_demand = avg_daily * Decimal(payload.horizon_days)

    # 7. Рекомендуемый объём
    recommended_qty = calculate_recommended_quantity(
        reorder_point=forecast_demand + safety_stock,
        stock=current_stock,
        incoming=incoming,
        pack_size=product.pack_size,
        min_lot=product.min_lot,
    )

    # 8. Стоимость
    estimated_cost = calculate_cost(recommended_qty, product.price)

    # 9. Дата заказа и дата стокаута
    days_of_stock = calculate_days_of_stock(current_stock, avg_daily)
    if days_of_stock is not None and days_of_stock > 0:
        recommended_order_date = today + timedelta(days=int(days_of_stock))
        # Стокоут — когда запас закончится, если не заказывать
        stockout_date = recommended_order_date
    else:
        recommended_order_date = today
        stockout_date = today

    # 10. Предупреждения
    warnings: list[Warning] = []
    if current_stock < reorder_point:
        warnings.append(Warning(level="warning", message="Остаток ниже точки заказа"))
    if avg_daily > 0 and days_of_stock is not None and days_of_stock < product.lead_time_days:
        warnings.append(Warning(
            level="critical",
            message=f"Запас {days_of_stock:.1f} дн. меньше срока поставки {product.lead_time_days} дн."
        ))
    if avg_daily == 0:
        warnings.append(Warning(
            level="info",
            message="Нет расхода за последние 90 дней — прогноз неопределён."
        ))

    # 11. Explanation
    explanation = ForecastExplanation(
        data_used=[
            "Движение товара за последние 90 дней",
            f"Остатки по партиям на {today}",
            f"Срок поставки: {product.lead_time_days} дн.",
            f"Упаковка: {product.pack_size}, мин. партия: {product.min_lot}",
        ],
        formulas=[
            "средний расход/день = расход за 90 дн. ÷ 90",
            "прогноз = средний расход/день × дней в периоде",
            "страховой запас = средний расход/день × страховой запас в днях",
            "точка заказа = средний расход/день × (срок поставки + страховой запас в днях)",
            "объём = прогноз + страховой запас − остаток − поставки в пути",
            "объём округляется вверх до кратности упаковки и не меньше мин. партии",
        ],
        assumptions=[
            "Цена принята на уровне справочной цены товара.",
            "Поставки в пути не учитываются (incoming = 0).",
            "Прогноз линейный на основе среднего расхода за 90 дней.",
            "Дата заказа = today + запас в днях.",
        ],
        as_of=today,
    )

    return ForecastResponse(
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        location=location.code,
        period={
            "from": str(today),
            "to": str(period_to),
            "days": payload.horizon_days,
        },
        avg_daily_consumption=round(avg_daily, 3),
        forecast_demand=round(forecast_demand, 1),
        current_stock=round(current_stock, 2),
        incoming_qty=incoming,
        safety_stock=round(safety_stock, 2),
        reorder_point=round(reorder_point, 2),
        recommended_purchase_qty=recommended_qty,
        unit_price=product.price,
        estimated_cost=estimated_cost,
        recommended_order_date=recommended_order_date,
        stockout_date=stockout_date,
        explanation=explanation,
        warnings=warnings,
    )