import { useEffect, useState } from 'react';

export function useLocation() {
  const [location, setLocation] = useState(
    () => localStorage.getItem('location') || 'MS-01'
  );

  useEffect(() => {
    const handler = () => setLocation(localStorage.getItem('location') || 'MS-01');
    window.addEventListener('location-change', handler);
    return () => window.removeEventListener('location-change', handler);
  }, []);

  return location;
}
