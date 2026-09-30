# ABS Inventory & Procurement Assistant

Демонстрационный MVP встроенного ИИ-помощника по складскому учёту и планированию закупок для сети спа-салонов.

## Содержание

- [Что умеет](#что-умеет)
- [Стек](#стек)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Запуск с нуля на новой машине](#запуск-с-нуля-на-новой-машине)
- [Переменные окружения](#переменные-окружения)
- [API](#api)
- [AI-помощник](#ai-помощник)
- [Тесты](#тесты)
- [Разработка](#разработка)
- [Ограничения MVP](#ограничения-mvp)
- [План развития](#план-развития)

---

## Что умеет

- Вести движения товаров (приход, расход, списание, возврат, корректировка) с проверкой остатков.
- Списывать расход по **FEFO** (первая истекает — первая уходит).
- Считать текущие остатки из движений и партий (без хранения изменяемого поля).
- Прогнозировать потребность и рассчитывать рекомендуемый объём закупки.
- Формировать бюджет закупок на месяц, квартал, полугодие, год.
- Выдавать предупреждения: дефицит, излишек, срок годности, отсутствие движения.
- **AI-помощник** — отвечает на вопросы по складу на русском языке.
- **Добавление товаров и партий** — через REST API и через агента.

---

## Стек

| Компонент | Технология | Почему |
|---|---|---|
| Язык | Python 3.11 | Требование ТЗ |
| Web-фреймворк | FastAPI | Автодокументация (Swagger), Pydantic-валидация |
| ORM | SQLAlchemy 2.x | Гибкость, поддержка PostgreSQL |
| БД | PostgreSQL 16 | Требование ТЗ, работа с decimal и датами |
| Миграции | Alembic | Стандарт для SQLAlchemy |
| Валидация | Pydantic v2 | Требование ТЗ |
| AI | OpenAI SDK + Yandex AI Studio | Работа с LLM на русском |
| Тесты | pytest + httpx | Требование ТЗ |
| Контейнеризация | Docker + docker compose | Запуск одной командой |

---

## Архитектура

```
app/
├── main.py              # точка входа, подключение роутеров
├── config.py            # настройки из .env (Pydantic Settings)
├── db.py                # engine, SessionLocal, Base, get_db
├── models.py            # SQLAlchemy-модели: Product, Location, Batch, Movement
├── schemas.py           # Pydantic-схемы
├── routers/             # HTTP-слой (тонкий)
│   ├── movements.py     # POST/GET /api/movements
│   ├── stock.py         # GET /api/stock, /api/stock/{sku}
│   ├── forecast.py      # POST /api/forecast
│   ├── alerts.py        # GET /api/alerts
│   ├── products.py      # POST/GET /api/products
│   ├── batches.py       # POST/GET /api/batches
│   └── chat.py          # POST /api/chat — AI-помощник
└── services/            # бизнес-логика (без БД и HTTP)
    ├── calculations.py  # расчёты: остаток, средний расход, точка заказа
    ├── fefo.py          # FEFO-списание
    └── ai_agent.py      # AI-агент: интенты, контекст, LLM
```

**Принципы:**

1. **Расчёты отделены от API.** `calculations.py` и `fefo.py` — чистые функции, тестируются без БД и HTTP.
2. **Остаток не хранится полем.** Считается из `Batch.quantity` и движений.
3. **FEFO реализован в `services/fefo.py`.** Партии с истёкшим сроком игнорируются.
4. **API — тонкий слой.** Роутеры принимают запрос, вызывают сервис, отдают ответ.

### Как считается остаток

```
остаток_партии = Batch.quantity + Σ(return) − Σ(consume) − Σ(writeoff)
остаток_позиции = Σ(остаток_партии по всем партиям объекта)
```

### Формулы прогноза

```
avg_daily            = Σ(consume за 90 дней) / 90
safety_stock         = avg_daily × safety_stock_days
reorder_point        = avg_daily × (lead_time_days + safety_stock_days)
forecast_demand      = avg_daily × horizon_days
recommended_qty      = ceil((forecast_demand + safety_stock − stock − incoming) / pack_size) × pack_size,
                       но не меньше min_lot
estimated_cost       = recommended_qty × price
recommended_date     = today + days_of_stock
```

---

## Быстрый старт

### Требования

- Docker 24+ и docker-compose v2
- Свободные порты: 8000 (API), 5432 (PostgreSQL)
- (Опционально) API-ключ Yandex AI Studio для LLM
- Подключиться по ssh при помощи команды ```ssh -L 8000:localhost:8000 user_name@ip_vm```, где **user_name** - имя пользователя, **ip_vm** - ip-адрес виртуальной машины(хоста), чтобы использовать **http://localhost:8000/ui** 

### Запуск одной командой

```bash
cp .env.example .env
# Отредактируй .env — заполни LLM_API_KEY, LLM_FOLDER_ID
docker-compose build --no-cache
docker-compose up -d
```

Миграции применяются автоматически при старте контейнера `api`.

### Загрузка стартовых данных

```bash
docker-compose exec api python seed.py
```

Будут загружены: 3 локации, 10 товаров, ~15 партий, ~900 движений за 90 дней.

### Проверка

```bash
curl http://localhost:8000/health
# → {"status":"ok"}

curl http://localhost:8000/api/stock | python3 -m json.tool | head
curl http://localhost:8000/api/alerts | python3 -m json.tool | head
```

**Swagger UI:** http://localhost:8000/docs  
**Веб-интерфейс:** http://localhost:8000/ui

---

## Запуск с нуля на новой машине

### Шаг 1. Установи Docker

**Ubuntu/Debian:**

```bash
# Удалить старые версии
sudo apt remove docker docker-engine docker.io containerd runc -y

# Установить зависимости
sudo apt update
sudo apt install ca-certificates curl gnupg lsb-release -y

# Добавить репозиторий Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установить Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Проверить
docker --version
docker-compose version
```

**Windows/Mac:** установи [Docker Desktop](https://www.docker.com/products/docker-desktop/).

### Шаг 2. Клонируй репозиторий

```bash
git clone <URL_РЕПОЗИТОРИЯ> app_spa
cd app_spa
```

### Шаг 3. Настрой `.env`

```bash
cp .env.example .env
nano .env
```

Заполни:

```env
POSTGRES_USER=abs_user
POSTGRES_PASSWORD=abs_password
POSTGRES_DB=abs_inventory
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg2://abs_user:abs_password@db:5432/abs_inventory
API_PORT=8000

# Yandex AI Studio
LLM_API_KEY=<твой_API-ключ>
LLM_BASE_URL=https://ai.api.cloud.yandex.net/v1
LLM_MODEL=gpt://<FOLDER_ID>/yandexgpt-5.1
LLM_FOLDER_ID=<FOLDER_ID>
```

**Важно:** `FOLDER_ID` в `LLM_MODEL` и `LLM_FOLDER_ID` должны **совпадать** и указывать на каталог сервисного аккаунта.

### Шаг 4. Запусти

```bash
docker-compose up -d --build
docker-compose ps
docker-compose logs api | tail -20
```

Должно быть:
```
INFO  [alembic.runtime.migration] Running upgrade -> ..., initial
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Шаг 5. Загрузи данные

```bash
docker-compose exec api python seed.py
```

### Шаг 6. Проверь

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/stock | python3 -m json.tool | head -20
```

### Шаг 7. Прогони тесты

```bash
docker-compose exec api pytest -v
```

Ожидаемо: **16+ тестов зелёные**.

---

## Переменные окружения

| Переменная | Назначение | Пример |
|---|---|---|
| `POSTGRES_USER` | Пользователь PostgreSQL | `abs_user` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `abs_password` |
| `POSTGRES_DB` | Имя БД | `abs_inventory` |
| `POSTGRES_HOST` | Хост БД (в Docker — имя сервиса) | `db` |
| `POSTGRES_PORT` | Порт БД | `5432` |
| `DATABASE_URL` | Полная строка подключения | `postgresql+psycopg2://...` |
| `API_PORT` | Порт API на хосте | `8000` |
| `LLM_API_KEY` | API-ключ Yandex AI Studio | `AQ...` |
| `LLM_BASE_URL` | Базовый URL LLM | `https://ai.api.cloud.yandex.net/v1` |
| `LLM_MODEL` | Модель LLM | `gpt://<folder>/yandexgpt-5.1` |
| `LLM_FOLDER_ID` | ID каталога Yandex Cloud | `b1g...` |

---

## API

### Движения

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/movements` | Создать движение, вернуть ID и остаток |
| GET | `/api/movements` | Список движений с фильтрами и пагинацией |

**Пример:**

```bash
curl -X POST http://localhost:8000/api/movements \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-09-26",
    "sku": "OIL-MASS-01",
    "location_code": "WH-01",
    "type": "receipt",
    "quantity": 50,
    "document_number": "INV-001"
  }'
```

### Остатки

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/stock` | Текущие остатки по позициям и объектам |
| GET | `/api/stock/{sku}` | Детализация по партиям |

### Прогноз

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/forecast` | Прогноз, точка заказа, рекомендуемый объём |

**Пример:**

```bash
curl -X POST http://localhost:8000/api/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "OIL-MASS-01",
    "location_code": "WH-01",
    "horizon_days": 30,
    "safety_stock_days": 7
  }' | jq .
```

### Предупреждения

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/alerts` | Дефицит, излишек, срок годности, нет движения |

### Товары и партии

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/products` | Создать товар |
| GET | `/api/products` | Список товаров |
| GET | `/api/products/{sku}` | Получить товар |
| POST | `/api/batches` | Создать партию (приход) |
| GET | `/api/batches` | Список партий |

### AI-помощник

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/chat` | Задать вопрос агенту |

**Пример:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Какие товары в дефиците?"}' | jq .
```

### Коды ошибок

| Код | Когда |
|---|---|
| 404 | Неизвестный SKU или объект |
| 409 | Повторный номер документа или накладной |
| 422 | Дата в будущем, количество ≤ 0, расход > остатка |

---

## AI-помощник

### Как работает

1. Пользователь отправляет вопрос.
2. Агент определяет **интент** (намерение) по ключевым словам.
3. Выполняет **инструмент** (запрос к БД, расчёт).
4. Формирует **контекст** с данными.
5. Отправляет в **LLM** (Yandex AI Studio) с системным промптом.
6. Возвращает ответ с исходными данными, логикой и предупреждениями.

**При ошибке LLM** — используется **fallback** (шаблонный ответ по данным).

### Поддерживаемые запросы

| Запрос | Что делает |
|---|---|
| «Какие остатки на складе?» | Список остатков |
| «Какие товары в дефиците?» | Алерты типа deficit |
| «Что скоро истекает?» | Алерты типа expiry |
| «Сколько закупить масла на месяц?» | Прогноз по SKU |
| «Какой бюджет на закупки?» | Сумма по прогнозам |
| «Добавь товар: масло кедровое, SKU OIL-CEDAR-11, цена 950» | Создание товара |
| «Приход масла кедрового 100 штук, партия INV-001» | Создание партии |

### Настройка LLM

Агент использует **Yandex AI Studio** через OpenAI-совместимый API.

**Как получить ключ:**

1. Зарегистрируйся в [Yandex Cloud](https://console.cloud.yandex.ru).
2. Создай **сервисный аккаунт** с ролью `ai.languageModels.user`.
3. Создай **API-ключ** для сервисного аккаунта.
4. Скопируй **Folder ID** каталога.
5. Заполни `.env`.

**Проверка LLM:**

```bash
docker-compose exec api python -c "
import httpx
from openai import OpenAI
import os
http_client = httpx.Client(headers={'OpenAI-Project': os.environ['LLM_FOLDER_ID']})
client = OpenAI(
    api_key=os.environ['LLM_API_KEY'],
    base_url=os.environ['LLM_BASE_URL'],
    http_client=http_client,
)
r = client.chat.completions.create(
    model=os.environ['LLM_MODEL'],
    messages=[{'role':'user','content':'Привет'}],
    max_tokens=50,
)
print(r.choices[0].message.content)
"
```

---

## Тесты

```bash
docker-compose exec api pytest -v
```

Ожидаемо: **16+ тестов**.

**Структура тестов:**

- `tests/test_calculations.py` — расчёты (5 тестов).
- `tests/test_fefo.py` — FEFO (3 теста).
- `tests/test_api.py` — API (8 тестов).

**Запуск конкретного файла:**

```bash
docker-compose exec api pytest tests/test_calculations.py -v
```

---

## Разработка

### Обновить код

Код монтируется в контейнер через `volumes: .:/app`. Uvicorn запущен с `--reload` — изменения подхватываются автоматически.

### Применить миграции

```bash
docker-compose exec api alembic upgrade head
```

### Создать новую миграцию

```bash
docker-compose exec api alembic revision --autogenerate -m "описание"
```

### Зайти в контейнер

```bash
docker-compose exec api bash
```

### Посмотреть логи

```bash
docker-ompose logs api -f
docker-compose logs db -f
```

### Остановить

```bash
docker-compose stop           # остановить
docker-compose down -v        # остановить и удалить данные БД
```

---

## Ограничения MVP

- Поставки в пути (`incoming`) не учитываются — упрощение.
- Прогноз — линейный на основе среднего расхода за 90 дней.
- Срок поставки фиксирован для товара.
- AI-агент использует rule-based intent detection + LLM.
- Синтетический датасет, реальных интеграций с 1С/ERP нет.

---

## План развития

1. Учёт поставок в пути.
2. ML-прогноз (Prophet, ARIMA).
3. Интеграция с 1С/ERP.
4. RAG для FAQ.
5. Веб-интерфейс (React/Vue).
6. Роли и права доступа.
7. Уведомления (email, Telegram).

---

## Структура репозитория

```
.
├── app/                 # исходный код
├── tests/               # pytest-тесты
├── alembic/             # миграции
├── scripts/             # вспомогательные скрипты
├── seed.py              # загрузка стартовых данных
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---
