import {
  ChevronLeft,
  ChevronRight,
  History,
  LayoutDashboard,
  Menu,
  SearchCheck,
  ShieldCheck,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router';
import { Brand } from '@/components/Brand';
import { useCurrentUser } from '@/features/auth/AuthContext';
import { SystemStatus } from '@/features/system/SystemStatus';
import { paths } from './paths';
import { ProfileMenu } from './ProfileMenu';

interface NavItem {
  to: string;
  label: string;
  crumb: string;
  icon: LucideIcon;
  admin?: boolean;
  end?: boolean;
}

const NAV: NavItem[] = [
  {
    to: paths.overview,
    label: 'Overview',
    crumb: 'Admin overview',
    icon: LayoutDashboard,
    admin: true,
    end: true,
  },
  { to: paths.verify, label: 'Verify an image', crumb: 'Image verification', icon: SearchCheck },
  { to: paths.history, label: 'Search history', crumb: 'Search history', icon: History },
  { to: paths.users, label: 'User management', crumb: 'User management', icon: Users, admin: true },
];

/* Collapsed sidebar: remembered per browser (localStorage is fine for a UI
   preference; never for tokens). Default: collapsed on medium windows. */
const COLLAPSE_KEY = 'verifylens.sidebarCollapsed';
const MEDIUM_QUERY = '(max-width: 1100px)';

function readSavedCollapse(): boolean | null {
  try {
    const saved = localStorage.getItem(COLLAPSE_KEY);
    return saved === null ? null : saved === '1';
  } catch {
    return null;
  }
}

function useSidebarCollapse(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(
    () => readSavedCollapse() ?? window.matchMedia?.(MEDIUM_QUERY).matches ?? false,
  );
  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0');
    } catch {
      /* storage unavailable: keep in memory */
    }
  }
  return [collapsed, toggle];
}

/** Layout route: sidebar + top bar around every signed-in page (<Outlet/>). */
export function Shell() {
  const user = useCurrentUser();
  const admin = user.role === 'admin';
  const [collapsed, toggleCollapsed] = useSidebarCollapse();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const tip = (text: string) => (collapsed ? text : undefined);
  const items = NAV.filter(item => !item.admin || admin);
  const current = items.find(item =>
    item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
  );

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {menuOpen && (
        <button
          type="button"
          className="sidebar-overlay"
          aria-label="Close menu"
          onClick={() => setMenuOpen(false)}
        />
      )}
      <aside
        id="app-sidebar"
        className={`sidebar ${menuOpen ? 'sidebar-visible' : ''} ${collapsed ? 'is-collapsed' : ''}`}
      >
        <div className="sidebar-brand">
          <Brand />
          <button
            type="button"
            className="sidebar-toggle"
            onClick={toggleCollapsed}
            aria-controls="app-sidebar"
            aria-expanded={!collapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            data-tip={tip('Expand sidebar')}
          >
            {collapsed ? (
              <ChevronRight size={16} strokeWidth={2.4} />
            ) : (
              <ChevronLeft size={18} strokeWidth={2.2} />
            )}
          </button>
          <button
            type="button"
            className="mobile-menu-close"
            onClick={() => setMenuOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        <div className="sidebar-group-label">WORKSPACE</div>
        <nav className="sidebar-links" aria-label="Main navigation">
          {items.map(({ to, label, icon: Icon, end }) => (
            // NavLink knows if it matches the URL: it sets aria-current="page" for us.
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `sidebar-link ${isActive ? 'selected' : ''}`}
              aria-label={collapsed ? label : undefined}
              data-tip={tip(label)}
              onClick={() => setMenuOpen(false)}
            >
              <Icon size={18} strokeWidth={1.9} aria-hidden="true" />
              <span className="sidebar-text">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <div className="sidebar-note-icon" aria-hidden="true">
              <ShieldCheck size={17} />
            </div>
            <strong>Verification, with context.</strong>
            <p>Review article metadata, AI findings and saved reports in one place.</p>
          </div>
          <div className="sidebar-profile">
            <ProfileMenu collapsed={collapsed} />
          </div>
        </div>
      </aside>
      <div className="main-side">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="hamburger"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">Workspace</span>
            <span className="breadcrumb-sep" aria-hidden="true">
              /
            </span>
            <span className="breadcrumb-current">{current?.crumb ?? ''}</span>
          </div>
          <div className="topbar-right">
            <SystemStatus detailed={admin} />
          </div>
        </header>
        <main id="main" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>&copy; {new Date().getFullYear()} VerifyLens. All rights reserved.</span>
        </footer>
      </div>
    </div>
  );
}
