"""AI-агент: определяет интент, собирает контекст, формирует ответ через LLM."""
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings
from app.models import Product, Location, Batch, Movement, MovementType
from app.services.calculations import (
    BatchDTO, MovementDTO,
    calculate_stock, calculate_avg_daily_consumption, calculate_days_of_stock,
    calculate_reorder_point, calculate_recommended_quantity, calculate_cost,
)

# ---------- Интенты ----------
INTENTS = {
    "add_product": ["добавить товар", "создать товар", "новый товар", "завести товар"],
    "add_batch": ["приход", "добавить партию", "поставить", "завезти", "поступление"],
    "stock_list": ["остатк", "склад", "что на складе", "сколько на складе"],
    "stock_detail": ["сколько", "остаток по", "детали"],
    "alerts_deficit": ["дефицит", "нехватк", "заканчива", "мало"],
    "alerts_expiry": ["срок годност", "истека", "просроч", "списан"],
    "alerts_all": ["риск", "предупрежд", "алерт", "проблем"],
    "forecast": ["прогноз", "закуп", "заказать", "потребност", "сколько нужно"],
    "budget": ["бюджет", "стоимост", "сумм", "трат"],
    "help": ["помощ", "help", "что ты умеешь", "как пользоваться"],
}


def detect_intent(message: str, db: Session = None) -> str:
    msg = message.lower()
    # Сначала проверяем специфичные интенты (add_product, add_batch)
    for intent in ("add_product", "add_batch"):
        for kw in INTENTS[intent]:
            if kw in msg:
                return intent
    # Потом остальные
    for intent, keywords in INTENTS.items():
        if intent in ("add_product", "add_batch"):
            continue
        for kw in keywords:
            if kw in msg:
                return intent
    # Если нашли SKU — считаем запросом по товару
    if db:
        products = db.query(Product).all()
        for p in products:
            if p.sku.lower() in msg:
                return "stock_detail"
    return "unknown"


def _get_product_by_name(db: Session, message: str) -> Optional[Product]:
    """Ищет товар по SKU или корням слов названия (с учётом падежей)."""
    products = db.query(Product).all()
    msg = message.lower()

    # 1. Прямое вхождение SKU
    for p in products:
        if p.sku.lower() in msg:
            return p

    # 2. Поиск по корням слов (первые 5 букв)
    best_match = None
    best_score = 0
    for p in products:
        name = p.name.lower()
        words = [w for w in name.replace(",", " ").split() if len(w) >= 4]
        score = 0
        for w in words:
            root = w[:5]
            if root in msg:
                score += 1
        if score > best_score:
            best_score = score
            best_match = p

    return best_match if best_score >= 1 else None


# ---------- LLM ----------
def _get_llm_client() -> OpenAI:
    """Создаёт OpenAI-клиент с заголовком OpenAI-Project для Yandex AI Studio."""
    http_client = httpx.Client(
        headers={"OpenAI-Project": settings.llm_folder_id}
    )
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        http_client=http_client,
        timeout=10.0,
    )


SYSTEM_PROMPT = """Ты — AI-помощник по складскому учёту спа-оператора.
Отвечай на русском языке, кратко и структурированно.
Используй ТОЛЬКО данные из контекста. Не выдумывай числа.
Формат ответа:
1. Исходные параметры (что взято из данных).
2. Логика (как считалось).
3. Предупреждения (если есть ограничения).
Отвечай в столбик, с отступами, без воды.
"""


def extract_product_params(message: str) -> dict:
    """Извлекает параметры товара из сообщения через LLM."""
    if not settings.llm_api_key or not settings.llm_folder_id:
        return {}
    try:
        client = _get_llm_client()
        prompt = f"""Извлеки параметры товара из сообщения. Верни ТОЛЬКО JSON без пояснений.
Поля: sku, name, unit, pack_size, min_lot, price, lead_time_days.
Если поле не указано — используй значения по умолчанию: unit="шт", pack_size=1, min_lot=1, lead_time_days=7.
Сообщение: "{message}"
JSON:"""
        r = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.0,
        )
        text = r.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"[extract_product_params] error: {e}")
        return {}


def extract_batch_params(message: str) -> dict:
    """Извлекает параметры партии из сообщения через LLM."""
    if not settings.llm_api_key or not settings.llm_folder_id:
        return {}
    try:
        client = _get_llm_client()
        prompt = f"""Извлеки параметры партии товара из сообщения. Верни ТОЛЬКО JSON без пояснений.
Поля: sku, location_code, quantity, expiry_date (формат YYYY-MM-DD), invoice_number.
Если location_code не указан — "WH-01".
Сообщение: "{message}"
JSON:"""
        r = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.0,
        )
        text = r.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"[extract_batch_params] error: {e}")
        return {}


def ask_llm(message: str, context: dict) -> str:
    """Отправляет запрос в LLM. При ошибке — fallback."""
    if not settings.llm_api_key or not settings.llm_folder_id:
        return _fallback_response(message, context)

    try:
        client = _get_llm_client()
        context_str = str(context)[:2500]
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Контекст:\n{context_str}\n\nВопрос: {message}"},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[ai_agent] LLM error: {e}")
        return _fallback_response(message, context)


# ---------- Контексты ----------
def _stock_context(db: Session) -> dict:
    locations = db.query(Location).all()
    products = db.query(Product).all()
    result = []
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
            result.append({
                "sku": p.sku,
                "name": p.name,
                "location": loc.code,
                "stock": round(float(stock), 1),
                "avg_daily": round(float(avg_daily), 2),
                "days_of_stock": round(float(days), 1) if days else None,
            })
    return {"items": result, "count": len(result)}


def _alerts_context(db: Session, filter_type: str | None = None, product: Product | None = None) -> dict:
    """Собирает алерты. filter_type: 'deficit' | 'expiry' | None.
    Если product указан — только по нему."""
    today = date.today()
    alerts = []
    locations = db.query(Location).all()
    products = [product] if product else db.query(Product).all()

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

            # Дефицит
            if filter_type in (None, "deficit"):
                if avg_daily > 0 and days is not None and days < p.lead_time_days:
                    alerts.append({
                        "type": "deficit",
                        "sku": p.sku,
                        "name": p.name,
                        "location": loc.code,
                        "days_of_stock": round(float(days), 1),
                        "lead_time": p.lead_time_days,
                        "stock": round(float(stock), 1),
                    })

            # Срок годности
            if filter_type in (None, "expiry"):
                for b in batches:
                    if b.expiry_date is None:
                        continue
                    days_to_exp = (b.expiry_date - today).days
                    if 0 <= days_to_exp <= 30:
                        remaining = calculate_stock([BatchDTO(
                            id=b.id, quantity=b.quantity, expiry_date=b.expiry_date, price=b.price
                        )], mv_dtos)
                        if remaining > 0:
                            alerts.append({
                                "type": "expiry",
                                "sku": p.sku,
                                "name": p.name,
                                "location": loc.code,
                                "batch_id": b.id,
                                "days_to_expiry": days_to_exp,
                                "expiry_date": str(b.expiry_date),
                                "remaining": round(float(remaining), 1),
                            })

    return {"alerts": alerts, "count": len(alerts), "filter": filter_type or "all"}


def _forecast_context(db: Session, product: Product, location_code: str = "WH-01") -> dict:
    loc = db.query(Location).filter(Location.code == location_code).first()
    if not loc:
        return {"error": "Локация не найдена"}

    batches = db.query(Batch).filter(
        Batch.product_id == product.id, Batch.location_id == loc.id
    ).all()
    movements = db.query(Movement).filter(
        Movement.product_id == product.id, Movement.location_id == loc.id
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
    safety_stock_days = 7
    reorder_point = calculate_reorder_point(avg_daily, product.lead_time_days, safety_stock_days)
    recommended_qty = calculate_recommended_quantity(
        reorder_point=avg_daily * 30 + avg_daily * safety_stock_days,
        stock=stock,
        incoming=Decimal("0"),
        pack_size=product.pack_size,
        min_lot=product.min_lot,
    )
    cost = calculate_cost(recommended_qty, product.price)

    return {
        "sku": product.sku,
        "name": product.name,
        "location": loc.code,
        "current_stock": round(float(stock), 1),
        "avg_daily": round(float(avg_daily), 2),
        "reorder_point": round(float(reorder_point), 1),
        "recommended_quantity": round(float(recommended_qty), 0),
        "estimated_cost": round(float(cost), 2),
        "lead_time_days": product.lead_time_days,
    }


def _budget_context(db: Session, horizon_days: int = 30) -> dict:
    """Считает бюджет закупок на период по всем позициям."""
    products = db.query(Product).all()
    locations = db.query(Location).all()
    items = []
    total = Decimal("0")

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
            qty = calculate_recommended_quantity(
                reorder_point=avg_daily * horizon_days + avg_daily * 7,
                stock=stock,
                incoming=Decimal("0"),
                pack_size=p.pack_size,
                min_lot=p.min_lot,
            )
            cost = calculate_cost(qty, p.price)
            if qty > 0:
                items.append({
                    "sku": p.sku,
                    "name": p.name,
                    "quantity": float(qty),
                    "cost": float(cost),
                })
                total += cost

    return {
        "horizon_days": horizon_days,
        "items": items,
        "total_cost": float(total),
        "count": len(items),
    }


def build_context(db: Session, intent: str, message: str) -> dict:
    if intent == "stock_list":
        return _stock_context(db)
    if intent == "alerts_deficit":
        product = _get_product_by_name(db, message)
        return _alerts_context(db, filter_type="deficit", product=product)
    if intent == "alerts_expiry":
        product = _get_product_by_name(db, message)
        return _alerts_context(db, filter_type="expiry", product=product)
    if intent == "alerts_all":
        return _alerts_context(db, filter_type=None)
    if intent == "budget":
        return _budget_context(db, horizon_days=30)
    if intent in ("forecast", "stock_detail"):
        product = _get_product_by_name(db, message)
        if product:
            return _forecast_context(db, product)
        products = db.query(Product).all()
        return {
            "error": "Товар не найден",
            "available_products": [
                {"sku": p.sku, "name": p.name} for p in products
            ],
            "hint": "Укажите SKU или часть названия, например: 'OIL-MASS-01' или 'масло массажное'",
        }
    if intent == "help":
        return {
            "commands": [
                "Какие остатки на складе?",
                "Какие товары в дефиците?",
                "Что скоро истекает?",
                "Сколько закупить масла на месяц?",
                "Какой бюджет на закупки?",
                "Добавь товар: масло кедровое, SKU OIL-CEDAR-11, цена 950",
                "Приход масла кедрового 100 штук, партия INV-001",
            ]
        }
    return {"error": "Не удалось определить запрос. Попробуйте переформулировать."}


# ---------- Fallback ----------
def _fallback_response(message: str, context: dict) -> str:
    if "error" in context:
        lines = [f"❌ {context['error']}"]
        if "available_products" in context:
            lines.append("\nДоступные товары:")
            for p in context["available_products"][:10]:
                lines.append(f"  • {p['sku']} — {p['name']}")
            lines.append(f"\n💡 {context.get('hint', '')}")
        return "\n".join(lines)

    if "items" in context and "total_cost" in context:
        # Бюджет
        lines = [f"💰 Бюджет закупок на {context['horizon_days']} дней:\n"]
        for item in context["items"][:15]:
            lines.append(
                f"• {item['sku']} — {item['name']}\n"
                f"  {item['quantity']:.0f} ед. = {item['cost']:.2f} руб."
            )
        lines.append(f"\n💵 Итого: {context['total_cost']:.2f} руб.")
        lines.append(f"📦 Позиций: {context['count']}")
        return "\n".join(lines)

    if "items" in context:
        lines = [f"📦 На складе {context['count']} позиций:\n"]
        for item in context["items"][:10]:
            days = f"{item['days_of_stock']:.1f}" if item['days_of_stock'] else "—"
            lines.append(
                f"• {item['sku']} — {item['name']}\n"
                f"  Остаток: {item['stock']:.0f} ед. | Запас: {days} дн."
            )
        if context['count'] > 10:
            lines.append(f"\n... и ещё {context['count'] - 10} позиций.")
        return "\n".join(lines)

    if "alerts" in context:
        if not context["alerts"]:
            return "✅ Предупреждений нет. Все запасы в норме."
        filter_name = context.get("filter", "all")
        titles = {
            "deficit": "⚠️ Дефицит",
            "expiry": "⏰ Срок годности",
            "all": "🔔 Все предупреждения",
        }
        lines = [f"{titles.get(filter_name, 'Предупреждения')}: {context['count']}\n"]
        for a in context["alerts"][:10]:
            if a["type"] == "deficit":
                lines.append(
                    f"• {a['sku']} — {a['name']}\n"
                    f"  Запас: {a['days_of_stock']} дн. | Срок поставки: {a['lead_time']} дн."
                )
            elif a["type"] == "expiry":
                lines.append(
                    f"• {a['sku']} — {a['name']}\n"
                    f"  Партия #{a['batch_id']}: истекает через {a['days_to_expiry']} дн.\n"
                    f"  Остаток: {a['remaining']} ед. | Дата: {a.get('expiry_date', '—')}"
                )
        return "\n".join(lines)

    if "recommended_quantity" in context:
        return (
            f"📈 Прогноз: {context['name']}\n"
            f"   SKU: {context['sku']}\n\n"
            f"• Текущий остаток: {context['current_stock']:.0f} ед.\n"
            f"• Средний расход: {context['avg_daily']:.1f} ед./день\n"
            f"• Точка заказа: {context['reorder_point']:.0f} ед.\n"
            f"• Рекомендуемый объём: {context['recommended_quantity']:.0f} ед.\n"
            f"• Стоимость: {context['estimated_cost']:.2f} руб.\n"
            f"• Срок поставки: {context['lead_time_days']} дн."
        )

    if "commands" in context:
        lines = ["🤖 Я умею отвечать на вопросы:\n"]
        for c in context["commands"]:
            lines.append(f"• {c}")
        return "\n".join(lines)

    return "Не удалось обработать запрос."


# ---------- Главная функция ----------
def process_message(db: Session, message: str) -> dict:
    """Полный цикл: интент → контекст → LLM → ответ."""
    intent = detect_intent(message, db)

    # --- Добавление товара ---
    if intent == "add_product":
        params = extract_product_params(message)
        if not params.get("sku") or not params.get("name"):
            return {
                "message": message,
                "intent": intent,
                "response": (
                    "❌ Не удалось извлечь SKU и название товара.\n"
                    "Пример: 'Добавь товар: масло кедровое, SKU OIL-CEDAR-11, цена 950, упаковка 6'"
                ),
                "context_used": {"params": params},
                "warnings": [],
            }
        existing = db.query(Product).filter(Product.sku == params["sku"]).first()
        if existing:
            return {
                "message": message,
                "intent": intent,
                "response": f"⚠️ Товар с SKU {params['sku']} уже существует.",
                "context_used": {"sku": params["sku"]},
                "warnings": [],
            }
        product = Product(
            sku=params["sku"],
            name=params["name"],
            unit=params.get("unit", "шт"),
            pack_size=int(params.get("pack_size", 1)),
            min_lot=int(params.get("min_lot", 1)),
            price=Decimal(str(params.get("price", 0))),
            lead_time_days=int(params.get("lead_time_days", 7)),
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return {
            "message": message,
            "intent": intent,
            "response": (
                f"✅ Товар создан:\n"
                f"• SKU: {product.sku}\n"
                f"• Название: {product.name}\n"
                f"• Цена: {product.price} руб.\n"
                f"• Упаковка: {product.pack_size} | Мин. партия: {product.min_lot}\n"
                f"• Срок поставки: {product.lead_time_days} дн."
            ),
            "context_used": {"sku": product.sku, "name": product.name},
            "warnings": [],
        }

    # --- Добавление партии ---
    if intent == "add_batch":
        params = extract_batch_params(message)
        if not params.get("sku") or not params.get("quantity"):
            return {
                "message": message,
                "intent": intent,
                "response": (
                    "❌ Не удалось извлечь SKU и количество.\n"
                    "Пример: 'Приход масла кедрового 100 штук, партия INV-001, срок годности 2027-06-01'"
                ),
                "context_used": {"params": params},
                "warnings": [],
            }
        product = db.query(Product).filter(Product.sku == params["sku"]).first()
        if not product:
            return {
                "message": message,
                "intent": intent,
                "response": f"❌ Товар с SKU {params['sku']} не найден. Сначала создайте товар.",
                "context_used": {"sku": params["sku"]},
                "warnings": [],
            }
        loc_code = params.get("location_code", "WH-01")
        location = db.query(Location).filter(Location.code == loc_code).first()
        if not location:
            return {
                "message": message,
                "intent": intent,
                "response": f"❌ Объект {loc_code} не найден.",
                "context_used": {"location": loc_code},
                "warnings": [],
            }
        invoice = params.get("invoice_number") or f"INV-{params['sku']}-{date.today()}"
        existing = db.query(Batch).filter(
            Batch.product_id == product.id,
            Batch.location_id == location.id,
            Batch.invoice_number == invoice,
        ).first()
        if existing:
            return {
                "message": message,
                "intent": intent,
                "response": f"⚠️ Партия с накладной {invoice} уже существует.",
                "context_used": {"invoice": invoice},
                "warnings": [],
            }
        expiry = None
        if params.get("expiry_date"):
            try:
                expiry = datetime.strptime(params["expiry_date"], "%Y-%m-%d").date()
            except Exception:
                pass
        batch = Batch(
            product_id=product.id,
            location_id=location.id,
            quantity=Decimal(str(params["quantity"])),
            expiry_date=expiry,
            price=product.price,
            invoice_number=invoice,
        )
        db.add(batch)
        db.flush()
        mv = Movement(
            date=date.today(),
            product_id=product.id,
            location_id=location.id,
            type=MovementType.receipt,
            quantity=Decimal(str(params["quantity"])),
            batch_id=batch.id,
            document_number=invoice,
        )
        db.add(mv)
        db.commit()
        return {
            "message": message,
            "intent": intent,
            "response": (
                f"✅ Партия добавлена:\n"
                f"• Товар: {product.name} ({product.sku})\n"
                f"• Количество: {batch.quantity} {product.unit}\n"
                f"• Накладная: {invoice}\n"
                f"• Срок годности: {expiry or '—'}\n"
                f"• Объект: {location.code}"
            ),
            "context_used": {
                "sku": product.sku,
                "batch_id": batch.id,
                "quantity": str(batch.quantity),
            },
            "warnings": [],
        }

    # --- Обычные интенты ---
    context = build_context(db, intent, message)
    answer = ask_llm(message, context)

    warnings = []
    if intent in ("alerts_deficit", "alerts_expiry", "alerts_all"):
        warnings.append("Алерты основаны на среднем расходе за 90 дней")
    if intent in ("forecast", "budget"):
        warnings.append("Поставки в пути не учитываются")

    return {
        "message": message,
        "intent": intent,
        "response": answer,
        "context_used": context,
        "warnings": warnings,
    }