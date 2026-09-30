export default function KpiCard({ label, value, unit, tone }) {
  const risk = tone === 'critical' ? 'Критично' : tone === 'warning' ? 'Внимание' : '';
  return (
    <div className={`kpi kpi-${tone || 'default'}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {value ?? '—'}{unit && <small> {unit}</small>}
      </div>
      {risk && <div className="kpi-risk">{risk}</div>}
    </div>
  );
}
