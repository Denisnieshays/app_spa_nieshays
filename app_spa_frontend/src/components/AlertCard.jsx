export default function AlertCard({ alert }) {
  const { severity, type, sku, message, metrics, recommendation } = alert;
  return (
    <div className={`alert alert-${severity || 'info'}`}>
      <div className="alert-head">
        <span className="alert-sev">[{severity || 'info'}]</span>
        <span className="alert-type">{type}</span>
        {sku && <span className="alert-sku">{sku}</span>}
      </div>
      {message && <p className="alert-msg">{message}</p>}
      {metrics && (
        <details>
          <summary>Показатели</summary>
          <pre>{JSON.stringify(metrics, null, 2)}</pre>
        </details>
      )}
      {recommendation && (
        <div className="alert-rec"><strong>Рекомендация:</strong> {recommendation}</div>
      )}
    </div>
  );
}
