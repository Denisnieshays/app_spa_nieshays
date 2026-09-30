import { useEffect, useState } from 'react';
import api from '../api/client';

export default function LocationSwitcher() {
  const [locations, setLocations] = useState([]);
  const [current, setCurrent] = useState(localStorage.getItem('location') || '');

  useEffect(() => {
    api.get('/api/meta').then((r) => {
      const locs = r.data.locations || r.data || [];
      setLocations(locs);
      if (!current && locs[0]) {
        const code = locs[0].code || locs[0].id;
        setCurrent(code);
        localStorage.setItem('location', code);
      }
    }).catch(() => {});
  }, []);

  const onChange = (e) => {
    const value = e.target.value;
    setCurrent(value);
    localStorage.setItem('location', value);
    window.dispatchEvent(new Event('location-change'));
  };

  return (
    <label className="loc-switcher">
      <span>Объект:</span>
      <select value={current} onChange={onChange} aria-label="Выбор объекта">
        {locations.map((l) => {
          const code = l.code || l.id;
          return <option key={code} value={code}>{l.name || code} ({code})</option>;
        })}
      </select>
    </label>
  );
}
