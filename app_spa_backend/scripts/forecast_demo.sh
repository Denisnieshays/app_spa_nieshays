#!/bin/bash
# Красивый вывод прогноза

SKU=${1:-OIL-MASS-01}
LOCATION=${2:-WH-01}
HORIZON=${3:-92}
SAFETY=${4:-7}

RESPONSE=$(curl -s -X POST http://localhost:8000/api/forecast \
  -H "Content-Type: application/json" \
  -d "{\"sku\":\"$SKU\",\"location_code\":\"$LOCATION\",\"horizon_days\":$HORIZON,\"safety_stock_days\":$SAFETY}")

echo "$RESPONSE" | jq -r '
  "╔══════════════════════════════════════════════════════════╗",
  "║  📈 ПРОГНОЗ ЗАКУПКИ                                      ║",
  "╚══════════════════════════════════════════════════════════╝",
  "",
  "📦 Товар:      \(.name)",
  "🔖 SKU:        \(.sku)",
  "📍 Объект:     \(.location)",
  "📅 Период:     \(.period.from) — \(.period.to) (\(.period.days) дн.)",
  "",
  "─────────────── ИСХОДНЫЕ ДАННЫЕ ───────────────",
  "📊 Средний расход:        \(.avg_daily_consumption) ед./день",
  "📦 Текущий остаток:       \(.current_stock) ед.",
  "🚚 Поставки в пути:       \(.incoming_qty) ед.",
  "🛡️  Страховой запас:       \(.safety_stock) ед.",
  "",
  "─────────────── РАСЧЁТ ───────────────",
  "📈 Прогноз спроса:        \(.forecast_demand) ед.",
  "🎯 Точка заказа:          \(.reorder_point) ед.",
  "🛒 Рекомендуемый объём:   \(.recommended_purchase_qty) ед.",
  "💰 Цена за единицу:       \(.unit_price) руб.",
  "💵 Стоимость закупки:     \(.estimated_cost) руб.",
  "",
  "─────────────── РЕКОМЕНДАЦИИ ───────────────",
  "📅 Дата заказа:           \(.recommended_order_date)",
  "⚠️  Дата стокаута:         \(.stockout_date)",
  "",
  "─────────────── ФОРМУЛЫ ───────────────",
  (.explanation.formulas | map("  • \(.)") | join("\n")),
  "",
  "─────────────── ДОПУЩЕНИЯ ───────────────",
  (.explanation.assumptions | map("  • \(.)") | join("\n")),
  "",
  "─────────────── ПРЕДУПРЕЖДЕНИЯ ───────────────",
  (if (.warnings | length) == 0 then "  ✅ Нет предупреждений"
   else (.warnings | map("  [\(.level | ascii_upcase)] \(.message)") | join("\n")) end)
'
