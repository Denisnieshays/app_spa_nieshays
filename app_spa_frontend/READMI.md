# SPA Inventory — Frontend

Веб-приложение управляющего спа-объектом.

## Запуск

```bash
cp .env.example .env
docker compose up --build
```

Открыть http://localhost:3000.

## Переменные окружения

| Переменная | Назначение | Пример |
|---|---|---|
| `VITE_API_URL` | Адрес mock API | `http://localhost:8000` |

## Экраны

- **Дашборд** — KPI, топ предупреждений, ближайшие заказы.
- **Расчёт закупки** — прогноз, объём, explanation, warnings.
- **Чат** — вопросы помощнику, подсказки, загрузка.

## Стек

React 18, Vite, React Router, Axios.