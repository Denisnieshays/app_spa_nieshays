export default function EmptyState({ message = 'Ничего не найдено' }) {
  return <div className="empty" role="status">{message}</div>;
}
