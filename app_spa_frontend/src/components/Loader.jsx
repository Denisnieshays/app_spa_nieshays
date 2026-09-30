export default function Loader({ text = 'Загрузка…' }) {
  return <div className="loader" role="status" aria-live="polite">{text}</div>;
}
