import { useEffect, useRef, useState } from 'react';
import api from '../api/client';
import { useLocation } from '../hooks/useLocation';

export default function Chat() {
  const location = useLocation();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [examples, setExamples] = useState([]);
  const [followUp, setFollowUp] = useState([]);
  const bottomRef = useRef(null);

  useEffect(() => {
    api.get('/api/chat').then((r) => {
      const list = r.data.messages || r.data.history || r.data || [];
      if (Array.isArray(list)) setMessages(list);
    }).catch(() => {});
    api.get('/api/chat/examples').then((r) => {
      const list = r.data.examples || r.data || [];
      if (Array.isArray(list)) setExamples(list);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const ask = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    setInput('');
    setFollowUp([]);
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setLoading(true);
    try {
      const r = await api.post('/api/chat', { message: question, location });
      setMessages((m) => [...m, { role: 'assistant', ...r.data }]);
      if (Array.isArray(r.data.follow_up)) setFollowUp(r.data.follow_up);
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: 'Ошибка: ' + (e.friendlyMessage || '') }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page chat">
      <h2>Чат с помощником</h2>

      {examples.length > 0 && (
        <div className="chips" aria-label="Примеры вопросов">
          <span className="chips-label">Примеры:</span>
          {examples.map((ex, i) => (
            <button key={i} className="chip" onClick={() => ask(ex.text || ex)}>
              {ex.text || ex}
            </button>
          ))}
        </div>
      )}

      <div className="chat-log" role="log" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            {m.text && <p>{m.text}</p>}
            {m.answer && <p>{m.answer}</p>}

            {m.table?.rows?.length > 0 && (
              <table>
                <thead><tr>{m.table.columns.map((c, ci) => <th key={ci}>{c}</th>)}</tr></thead>
                <tbody>
                  {m.table.rows.map((row, ri) => (
                    <tr key={ri}>{row.map((cell, ci) => <td key={ci}>{cell}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            )}

            {m.calculation && (
              <details><summary>Расчёт</summary><pre>{JSON.stringify(m.calculation, null, 2)}</pre></details>
            )}
            {m.explanation && (
              <details><summary>Обоснование</summary><pre>{JSON.stringify(m.explanation, null, 2)}</pre></details>
            )}
            {m.warnings?.length > 0 && (
              <div className="warnings">
                {m.warnings.map((w, wi) => (
                  <div key={wi} className={`warn warn-${w.level}`}>
                    <strong>[{w.level}]</strong> {w.message}
                  </div>
                ))}
              </div>
            )}
            {m.intent === 'help' && examples.length > 0 && (
              <div className="help">Попробуйте один из примеров выше.</div>
            )}
          </div>
        ))}
        {loading && <div className="msg msg-assistant">Помощник думает…</div>}
        <div ref={bottomRef} />
      </div>

      {followUp.length > 0 && (
        <div className="chips" aria-label="Подсказки">
          {followUp.map((f, i) => (
            <button key={i} className="chip" onClick={() => ask(f.text || f)}>
              {f.text || f}
            </button>
          ))}
        </div>
      )}

      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Спросите про закупку, остатки, риски…"
          aria-label="Вопрос помощнику"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>Отправить</button>
      </form>
    </div>
  );
}
