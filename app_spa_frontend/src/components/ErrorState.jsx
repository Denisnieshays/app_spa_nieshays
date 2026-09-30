export default function ErrorState({ message, onRetry }) {
  return (
    <div className="error" role="alert">
      <p>⚠️ {message}</p>
      {onRetry && <button onClick={onRetry}>Повторить</button>}
    </div>
  );
}
