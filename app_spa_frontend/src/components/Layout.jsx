import { NavLink, Outlet } from 'react-router-dom';
import LocationSwitcher from './LocationSwitcher';

const links = [
  { to: '/', label: 'Дашборд' },
  { to: '/forecast', label: 'Расчёт закупки' },
  { to: '/chat', label: 'Чат' },
];

export default function Layout() {
  return (
    <div className="app">
      <header className="header">
        <h1>SPA Inventory</h1>
        <LocationSwitcher />
      </header>
      <nav className="nav" aria-label="Основная навигация">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'}>{l.label}</NavLink>
        ))}
      </nav>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
