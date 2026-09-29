"""Загрузка стартовых данных для демонстрации."""
from datetime import date, timedelta
from decimal import Decimal
import random

from app.db import SessionLocal
from app.models import Product, Location, Batch, Movement, MovementType


def seed():
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("Данные уже загружены, пропускаем.")
            return

        # --- Локации ---
        locations = [
            Location(code="WH-01", name="Основной склад"),
            Location(code="SPA-01", name="Спа-кабинет №1"),
            Location(code="SPA-02", name="Спа-кабинет №2"),
        ]
        db.add_all(locations)
        db.flush()

        # --- Товары (спа-оператор) ---
        products_data = [
            ("OIL-MASS-01", "Масло массажное базовое, 1л", "фл", 6, 12, Decimal("850.00"), 7),
            ("OIL-AROM-02", "Масло ароматическое лаванда, 100мл", "фл", 12, 24, Decimal("420.00"), 10),
            ("CREAM-HAND-03", "Крем для рук питательный, 250мл", "шт", 24, 24, Decimal("310.00"), 5),
            ("SCRUB-SALT-04", "Скраб солевой морской, 500г", "шт", 12, 12, Decimal("380.00"), 7),
            ("TOWEL-WHITE-05", "Полотенце вафельное белое", "шт", 50, 100, Decimal("120.00"), 14),
            ("OIL-COCONUT-06", "Масло кокосовое, 500мл", "фл", 6, 12, Decimal("540.00"), 7),
            ("MASK-CLAY-07", "Маска глиняная, 200г", "шт", 12, 12, Decimal("290.00"), 10),
            ("TEA-HERBAL-08", "Чай травяной для клиентов, 100 пак.", "уп", 10, 10, Decimal("650.00"), 5),
            ("CANDLE-AROM-09", "Свеча ароматическая, 200г", "шт", 6, 12, Decimal("720.00"), 14),
            ("ROBE-SPA-10", "Халат спа-махра, унисекс", "шт", 10, 20, Decimal("1450.00"), 21),
        ]
        products = []
        for sku, name, unit, pack, min_lot, price, lead in products_data:
            p = Product(
                sku=sku, name=name, unit=unit,
                pack_size=pack, min_lot=min_lot,
                price=price, lead_time_days=lead,
            )
            products.append(p)
        db.add_all(products)
        db.flush()

        # --- Партии ---
        today = date.today()
        batches = []
        random.seed(42)

        for p in products:
            for i in range(random.randint(1, 2)):
                qty = Decimal(random.randint(50, 300))
                expiry = today + timedelta(days=random.randint(30, 400))
                b = Batch(
                    product_id=p.id,
                    location_id=locations[0].id,
                    quantity=qty,
                    expiry_date=expiry,
                    price=p.price,
                    invoice_number=f"INV-{p.sku}-{i+1}",
                )
                batches.append(b)
        db.add_all(batches)
        db.flush()

        # --- Движения за 90 дней ---
        movements = []
        for p in products:
            daily_avg = random.randint(2, 10)
            for day_offset in range(90, 0, -1):
                d = today - timedelta(days=day_offset)
                qty = Decimal(random.randint(0, daily_avg * 2))
                if qty > 0:
                    mv = Movement(
                        date=d,
                        product_id=p.id,
                        location_id=locations[0].id,
                        type=MovementType.consume,
                        quantity=qty,
                        document_number=f"DOC-{p.sku}-{day_offset}",
                    )
                    movements.append(mv)
        db.add_all(movements)

        db.commit()
        print(f"Загружено: {len(locations)} локаций, {len(products)} товаров, "
              f"{len(batches)} партий, {len(movements)} движений.")
    except Exception as e:
        db.rollback()
        print(f"Ошибка: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
