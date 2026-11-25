import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronsUpDown, Clock3, Image as ImageIcon, Info, KeyRound, LogOut, ShieldCheck, X } from 'lucide-react';
import { ChangePasswordDialog } from './PasswordForms.jsx';
import './profile-menu.css';

const GAP = 10;
const MENU_W = 248;
// Collapsed (icon-only) sidebar exists only on desktop/tablet; phones use the drawer.
const SIDE_QUERY = '(min-width: 761px)';

const FEATURES = [
  { icon: ShieldCheck, title: 'Authenticated access', text: 'Sign-in is required. Accounts are either administrators or standard users.' },
  { icon: Clock3, title: 'Saved search history', text: 'Verifications are saved and can be reopened from Search history.' },
  { icon: ImageIcon, title: 'Wikipedia + Gemini', text: 'Article content and image come from Wikipedia; Gemini assesses whether the image fits the article.' },
];

/**
 * Sidebar profile button + menu (Info, Log out).
 * Expanded sidebar: menu opens above the button, same width.
 * Collapsed sidebar: menu opens to the right of the avatar.
 * Menu and dialog are portalled to <body> so they use the light theme tokens,
 * not the white-on-forest tokens the sidebar redefines.
 */
export default function ProfileMenu({ displayName, username, initials, roleName, collapsed, onLogout, onChangePassword }) {
  const [open, setOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [pos, setPos] = useState(null);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }, []);

  // Position (and follow resize/scroll while open)
  useLayoutEffect(() => {
    if (!open) { setPos(null); return undefined; }
    function place() {
      const r = triggerRef.current?.getBoundingClientRect();
      if (!r) return;
      const side = collapsed && window.matchMedia(SIDE_QUERY).matches;
      const width = side ? MENU_W : Math.max(r.width, MENU_W);
      const left = side ? r.right + GAP + 4 : r.left;
      setPos({
        width,
        left: Math.max(8, Math.min(left, window.innerWidth - width - 8)),
        bottom: side ? Math.max(8, window.innerHeight - r.bottom) : window.innerHeight - r.top + GAP,
      });
    }
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, collapsed]);

  // Outside click closes without stealing focus; focus first item on open
  useEffect(() => {
    if (!open) return undefined;
    const onDown = e => {
      if (!triggerRef.current?.contains(e.target) && !menuRef.current?.contains(e.target)) close(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open, close]);

  useEffect(() => {
    if (open && pos) menuRef.current?.querySelector('[role="menuitem"]')?.focus();
  }, [open, pos]);

  function onMenuKey(e) {
    const items = [...menuRef.current.querySelectorAll('[role="menuitem"]')];
    const i = items.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'Tab') close(false);
    else if (e.key === 'ArrowDown') { e.preventDefault(); items[(i + 1) % items.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); items[(i - 1 + items.length) % items.length]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); items[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); items[items.length - 1]?.focus(); }
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`profile-trigger ${open ? 'is-open' : ''}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${displayName}`}
        data-tip={collapsed && !open ? displayName : undefined}
        onClick={() => setOpen(o => !o)}
      >
        <span className="avatar">{initials}</span>
        <span className="sidebar-profile-text sidebar-text"><strong>{displayName}</strong><small>{roleName}</small></span>
        <ChevronsUpDown className="profile-chevron sidebar-text" size={16} aria-hidden="true" />
      </button>

      {open && pos && createPortal(
        <div
          ref={menuRef}
          className="profile-menu"
          role="menu"
          aria-label="Account"
          style={{ left: pos.left, bottom: pos.bottom, width: pos.width }}
          onKeyDown={onMenuKey}
        >
          <div className="profile-menu-head">
            <span className="avatar">{initials}</span>
            <span><strong>{displayName}</strong><small>{roleName}</small></span>
          </div>
          <div className="profile-menu-sep" role="separator" />
          <button type="button" role="menuitem" className="profile-menu-item" onClick={() => { close(false); setPasswordOpen(true); }}>
            <KeyRound size={18} /> Change password
          </button>
          <button type="button" role="menuitem" className="profile-menu-item" onClick={() => { close(false); setAboutOpen(true); }}>
            <Info size={18} /> About VerifyLens
          </button>
          <div className="profile-menu-sep" role="separator" />
          <button type="button" role="menuitem" className="profile-menu-item" onClick={() => { close(false); onLogout(); }}>
            <LogOut size={18} /> Log out
          </button>
        </div>,
        document.body,
      )}

      {aboutOpen && <AboutDialog onClose={() => { setAboutOpen(false); triggerRef.current?.focus(); }} />}
      {passwordOpen && <ChangePasswordDialog username={username} onSubmit={onChangePassword} onClose={() => { setPasswordOpen(false); triggerRef.current?.focus(); }} />}
    </>
  );
}

/* Native <dialog> + showModal(): focus trap, Esc to close and inert page for free. */
function AboutDialog({ onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return createPortal(
    <dialog
      ref={ref}
      className="about-dialog"
      aria-labelledby="about-title"
      onClose={onClose}
      onClick={e => { if (e.target === ref.current) ref.current.close(); }}
    >
      <div className="about-body">
        <div className="about-head">
          <div>
            <h2 id="about-title">About VerifyLens</h2>
            <p>Wikipedia Image Verifier: checks whether an article&rsquo;s image fits its content.</p>
          </div>
          <button type="button" className="icon-button" aria-label="Close" onClick={() => ref.current?.close()}><X size={18} /></button>
        </div>
        <ul className="about-features">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li key={title}>
              <span className="step-icon"><Icon size={18} /></span>
              <span><strong>{title}</strong><small>{text}</small></span>
            </li>
          ))}
        </ul>
      </div>
    </dialog>,
    document.body,
  );
}
