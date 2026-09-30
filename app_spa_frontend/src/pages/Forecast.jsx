import { useCallback, useEffect, useState } from 'react';
import api from '../api/client';
import Loader from '../components/Loader';
import ErrorState from '../components/ErrorState';
import { useLocation } from '../hooks/useLocation';

export default function Forecast() {
  const location = useLocation();
  const [sku, setSku] = useState('OIL-001');
  const [horizon, setHorizon] = useState(3);
  const [safety, setSafety] = useState(7);
  const [budget, setBudget] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.post('/api/forecast', {
      sku,
      location,
      horizon_months: horizon,
      safety_stock_days: safety,
      ...(budget ? { budget_limit: Number(budget) } : {}),
    })
      .then((r) => setData(r.data))
      .catch((e) => setError(e.friendlyMessage))
      .finally(() => setLoading(false));
  }, [sku, location, horizon, safety, budget]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="page">
      <h2>Расчёт закупки</h2>

      <div className="filters">
        <label>SKU: <input value={sku} onChange={(e) => setSku(e.target.value)} /></label>
        <label>Период (мес):
          <select value={horizon} onChange={(e) => setHorizon(+e.target.value)}>
            <option value={1}>1</option><option value={3}>3</option>
            <option value={6}>6</option><option value={12}>12</option>
          </select>
        </label>
        <label>Страховой запас (дн):
          <input type="number" value={safety} min={0} onChange={(e) => setSafety(+e.target.value)} />
        </label>
        <label>Бюджет (₽):
          <input type="number" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </label>
      </div>

      {loading && <Loader text="Считаем…" />}
      {error && <ErrorState message={error} onRetry={load} />}

      {data && (
        <>
          <div className="num-grid">
            <Num label="Прогнозный расход" value={data.forecast_consumption} />
            <Num label="Текущий остаток" value={data.current_stock} />
            <Num label="Поставки в пути" value={data.incoming_qty} />
            <Num label="Остаток без закупки" value={data.expected_stock_without_purchase} />
            <Num label="Страховой запас" value={data.safety_stock} />
            <Num label="Точка заказа" value={data.reorder_point} />
            <Num label="Рекомендуемый объём" value={data.recommended_purchase_qty} tone="accent" />
            <Num label="Цена" value={data.unit_price} unit="₽" />
            <Num label="Стоимость" value={data.estimated_cost} unit="₽" tone="accent" />
            <Num label="Заказать до" value={data.recommended_order_date} />
            <Num label="Исчерпание" value={data.stockout_date} tone="warning" />
          </div>

          {data.explanation && (
            <details open className="explain">
              <summary>Обоснование расчёта</summary>
              <div className="explain-grid">
                {data.explanation.data_used && (
                  <div><strong>Данные:</strong><ul>{data.explanation.data_used.map((d, i) => <li key={i}>{d}</li>)}</ul></div>
                )}
                {data.explanation.period && (
                  <div><strong>Период:</strong> {typeof data.explanation.period === 'string' ? data.explanation.period : JSON.stringify(data.explanation.period)}</div>
                )}
                {data.explanation.formulas && (
                  <div><strong>Формулы:</strong><ul>{data.explanation.formulas.map((f, i) => <li key={i}>{f}</li>)}</ul></div>
                )}
                {data.explanation.assumptions && (
                  <div><strong>Допущения:</strong><ul>{data.explanation.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul></div>
                )}
                {data.explanation.as_of && <div><strong>На дату:</strong> {data.explanation.as_of}</div>}
              </div>
            </details>
          )}

          {data.warnings?.length > 0 && (
            <div className="warnings">
              {data.warnings.map((w, i) => (
                <div key={i} className={`warn warn-${w.level}`}>
                  <strong>[{w.level}]</strong> {w.message}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Num({ label, value, unit, tone }) {
  return (
    <div className={`num ${tone ? 'num-' + tone : ''}`}>
      <div className="num-label">{label}</div>
      <div className="num-value">{value ?? '—'}{unit && <small> {unit}</small>}</div>
    </div>
  );
}
