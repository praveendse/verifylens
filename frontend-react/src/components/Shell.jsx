import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, History, LayoutDashboard, SearchCheck, Shield, ShieldCheck, Users, X } from 'lucide-react';
import Brand from './Brand.jsx';
import ProfileMenu from './ProfileMenu.jsx';
import SystemStatus from './SystemStatus.jsx';

const COPYRIGHT_YEAR = 2026;

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, admin: true },
  { id: 'verify', label: 'Verify an image', icon: SearchCheck },
  { id: 'history', label: 'Search history', icon: History },
  { id: 'admin', label: 'User management', icon: Users, admin: true },
];

/* Collapse preference: the user's explicit choice is remembered per browser.
   With no saved choice, the sidebar is expanded on large windows and
   collapsed on medium ones. On phones (≤760px) it is an off-canvas drawer
   and the collapsed state does not apply (see styles.css). */
const COLLAPSE_KEY = 'verifylens.sidebarCollapsed';
const MEDIUM_QUERY = '(max-width: 1100px)';

function readSavedCollapse() {
  try {
    const saved = localStorage.getItem(COLLAPSE_KEY);
    return saved === null ? null : saved === '1';
  } catch { return null; }
}

function useSidebarCollapse() {
  const [saved, setSaved] = useState(readSavedCollapse);
  const [isMedium, setIsMedium] = useState(() => window.matchMedia?.(MEDIUM_QUERY).matches ?? false);

  useEffect(() => {
    const query = window.matchMedia?.(MEDIUM_QUERY);
    if (!query) return undefined;
    const onChange = event => setIsMedium(event.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  const collapsed = saved ?? isMedium;
  function toggle() {
    const next = !collapsed;
    setSaved(next);
    try { localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0'); } catch { /* storage unavailable: keep in memory */ }
  }
  return [collapsed, toggle];
}

export default function Shell({ user, section, setSection, onLogout, onChangePassword, isDemo, children, isMenuOpen, setMenuOpen, checkSystems }) {
  const admin = user?.role === 'admin';
  const displayName = user?.full_name || user?.username || 'User';
  const initials = displayName.split(/\s+/).map(s => s[0]).slice(0, 2).join('').toUpperCase();
  const roleName = admin ? 'Administrator' : 'Standard user';
  const [collapsed, toggleCollapsed] = useSidebarCollapse();
  // Tooltips only make sense while the labels are hidden.
  const tip = text => (collapsed ? text : undefined);

  return (
    <div className="app-frame">
      {isMenuOpen && <button type="button" className="sidebar-overlay" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}
      <aside id="app-sidebar" className={`sidebar ${isMenuOpen ? 'sidebar-visible' : ''} ${collapsed ? 'is-collapsed' : ''}`}>
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
            {collapsed ? <ChevronRight size={16} strokeWidth={2.4}/> : <ChevronLeft size={18} strokeWidth={2.2}/>}
          </button>
          <button className="mobile-menu-close" onClick={() => setMenuOpen(false)} aria-label="Close menu"><X size={20}/></button>
        </div>

        <div className="sidebar-group-label">WORKSPACE</div>
        <nav className="sidebar-links" aria-label="Main navigation">
          {NAV.filter(item => !item.admin || admin).map(item => {
            const Icon = item.icon;
            const current = section === item.id;
            return (
              <button
                key={item.id}
                className={`sidebar-link ${current ? 'selected' : ''}`}
                aria-current={current ? 'page' : undefined}
                aria-label={collapsed ? item.label : undefined}
                data-tip={tip(item.label)}
                onClick={() => { setSection(item.id); setMenuOpen(false); }}
              >
                <Icon size={18} strokeWidth={1.9}/>
                <span className="sidebar-text">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-note"><div className="sidebar-note-icon"><ShieldCheck size={17}/></div><strong>Verification, with context.</strong><p>Review article metadata, AI findings and saved reports in one place.</p></div>
          <div className="sidebar-profile">
            <ProfileMenu displayName={displayName} username={user?.username} initials={initials} roleName={roleName} collapsed={collapsed} onLogout={onLogout} onChangePassword={onChangePassword} />
          </div>
        </div>
      </aside>
      <div className="main-side">
        <header className="topbar"><div className="topbar-left"><button className="hamburger" onClick={() => setMenuOpen(true)} aria-label="Open menu">☰</button><span className="breadcrumb">Workspace</span><span className="breadcrumb-sep">/</span><span className="breadcrumb-current">{section === 'verify' ? 'Image verification' : section === 'history' ? 'Search history' : section === 'overview' ? 'Admin overview' : 'User management'}</span></div><div className="topbar-right">{isDemo && <span className="preview-badge">PREVIEW ONLY</span>}{checkSystems && <SystemStatus check={checkSystems}/>}</div></header>
        {isDemo && <div className="demo-banner"><Shield size={16}/><span><strong>Demo mode:</strong> This interface uses sample accounts and browser-memory data only. Real login, authorization and persistence require the FastAPI backend.</span></div>}
        <main className="main-content">{children}</main>
        <footer className="workspace-footer"><span>&copy; {COPYRIGHT_YEAR} VerifyLens. All rights reserved.</span></footer>
      </div>
    </div>
  );
}
