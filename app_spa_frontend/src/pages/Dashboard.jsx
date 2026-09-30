import { useCallback, useEffect, useState } from 'react';
import api from '../api/client';
import KpiCard from '../components/KpiCard';
import AlertCard from '../components/AlertCard';
import Loader from '../components/Loader';
import ErrorState from '../components/ErrorState';
import EmptyState from '../components/EmptyState';
import { useLocation } from '../hooks/useLocation';

export default function Dashboard() {
  const location = useLocation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api.get('/api/dashboard', { params: { location } })
      .then((r) => setData(r.data))
      .catch((e) => setError(e.friendlyMessage))
      .finally(() => setLoading(false));
  }, [location]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loader text="Загрузка дашборда…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <EmptyState />;

  const kpi = data.kpi || data;
  return (
    <div className="page">
      <h2>Дашборд — {location}</h2>

      <section className="kpi-grid" aria-label="KPI объекта">
        <KpiCard label="Стоимость запаса" value={kpi.stock_value} unit="₽" />
        <KpiCard label="Ниже точки заказа" value={kpi.below_reorder} tone="warning" />
        <KpiCard label="Истекающий срок" value={kpi.expiring_batches} tone="critical" />
        <KpiCard label="Открытые заказы" value={kpi.open_orders} />
        <KpiCard label="Критичные предупреждения" value={kpi.critical_alerts} tone="critical" />
        <KpiCard label="План закупок на месяц" value={kpi.purchase_plan_month} unit="₽" />
        <KpiCard label="Процедур за 30 дней" value={kpi.procedures_30d} />
      </section>

      <section aria-label="Топ предупреждений">
        <h3>Топ предупреждений</h3>
        {(!data.alerts || data.alerts.length === 0)
          ? <EmptyState message="Предупреждений нет" />
          : data.alerts.slice(0, 5).map((a, i) => <AlertCard key={i} alert={a} />)}
      </section>

      <section aria-label="Ближайшие заказы">
        <h3>Ближайшие заказы</h3>
        {(!data.upcoming_orders || data.upcoming_orders.length === 0)
          ? <EmptyState message="Нет ближайших заказов" />
          : (
            <table>
              <thead>
                <tr><th>SKU</th><th>Название</th><th>Заказать до</th><th>Объём</th><th>Стоимость</th></tr>
              </thead>
              <tbody>
                {data.upcoming_orders.map((o, i) => (
                  <tr key={i}>
                    <td>{o.sku}</td><td>{o.name}</td>
                    <td>{o.order_by || o.order_date}</td>
                    <td>{o.qty || o.quantity}</td>
                    <td>{o.cost ?? '—'} ₽</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </div>
  );
}
