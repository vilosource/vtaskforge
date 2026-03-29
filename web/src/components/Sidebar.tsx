import { Link, useLocation } from 'react-router-dom';

interface NavItem {
  to: string;
  icon: string;
  label: string;
  /** If true, only exact path match counts as active. Otherwise prefix match. */
  exact?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', icon: 'dashboard', label: 'Home', exact: true },
  { to: '/projects', icon: 'folder_open', label: 'Projects' },
  { to: '/agents', icon: 'smart_toy', label: 'Agents' },
];

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = item.exact
    ? pathname === item.to
    : pathname === item.to || pathname.startsWith(item.to + '/');

  return (
    <Link
      to={item.to}
      className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 text-sm
        ${isActive
          ? 'text-blue-600 font-bold bg-white shadow-sm'
          : 'text-slate-500 hover:text-slate-900 hover:bg-slate-200 font-medium'
        }`}
    >
      <span
        className="material-symbols-outlined"
        style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}
      >
        {item.icon}
      </span>
      <span>{item.label}</span>
    </Link>
  );
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { pathname } = useLocation();

  if (collapsed) {
    return (
      <aside className="h-screen w-10 fixed left-0 top-0 flex flex-col items-center pt-4 bg-slate-100 z-50">
        <button
          className="flex items-center justify-center w-6 h-6 rounded text-on-surface-variant hover:bg-slate-200 hover:text-on-surface transition-colors"
          onClick={onToggle}
          title="Expand sidebar"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 flex flex-col bg-slate-100 z-50">
      <div className="flex flex-col h-full p-6 space-y-8">
        {/* Brand */}
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center text-on-primary">
              <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>deployed_code</span>
            </div>
            <div>
              <div className="text-2xl font-bold tracking-tight text-slate-900 font-headline">VTaskForge</div>
              <div className="text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Task Platform</div>
            </div>
          </Link>
          <button
            className="flex items-center justify-center w-6 h-6 rounded text-on-surface-variant hover:bg-slate-200 hover:text-on-surface transition-colors"
            onClick={onToggle}
            title="Collapse sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 3l-5 5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-on-surface-variant font-bold mb-4 px-4">Navigation</div>
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} item={item} pathname={pathname} />
          ))}
        </nav>

        {/* Settings */}
        <div className="pt-6 border-t border-slate-200 space-y-1">
          <Link
            to="#"
            className="flex items-center gap-3 px-4 py-3 text-slate-500 hover:text-slate-900 transition-colors rounded-lg text-sm font-medium"
          >
            <span className="material-symbols-outlined">settings</span>
            <span>Settings</span>
          </Link>
        </div>
      </div>
    </aside>
  );
}
