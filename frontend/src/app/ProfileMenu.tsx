import {
  ChevronsUpDown,
  Clock3,
  Image as ImageIcon,
  Info,
  KeyRound,
  LogOut,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { Modal } from '@/components/Modal';
import { useAuth, useCurrentUser } from '@/features/auth/AuthContext';
import { ChangePasswordDialog } from '@/features/auth/PasswordForms';
import { displayName, initials } from '@/lib/format';
import '@/styles/profile-menu.css';

const GAP = 10;
const MENU_W = 248;
const SIDE_QUERY = '(min-width: 761px)';

const FEATURES = [
  {
    icon: ShieldCheck,
    title: 'Authenticated access',
    text: 'Sign-in is required. Accounts are either administrators or standard users.',
  },
  {
    icon: Clock3,
    title: 'Saved search history',
    text: 'Verifications are saved and can be reopened from Search history.',
  },
  {
    icon: ImageIcon,
    title: 'Wikipedia + Gemini',
    text: 'Article content and image come from Wikipedia; Gemini assesses whether the image fits the article.',
  },
];

function AboutDialog({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  return (
    <Modal className="about-dialog" labelledBy={titleId} onClose={onClose} closeOnBackdrop>
      <div className="about-body">
        <div className="about-head">
          <div>
            <h2 id={titleId}>About VerifyLens</h2>
            <p>Wikipedia Image Verifier: checks whether an article&rsquo;s image fits its content.</p>
          </div>
          <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <ul className="about-features">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <li key={title}>
              <span className="step-icon" aria-hidden="true">
                <Icon size={18} />
              </span>
              <span>
                <strong>{title}</strong>
                <small>{text}</small>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Modal>
  );
}

/** Sidebar profile button + menu (ARIA menu pattern: arrows, Home/End, Esc). */
export function ProfileMenu({ collapsed }: { collapsed: boolean }) {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const name = displayName(user);
  const roleName = user.role === 'admin' ? 'Administrator' : 'Standard user';
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState<'about' | 'password' | null>(null);
  const [pos, setPos] = useState<{ left: number; bottom: number; width: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open) return undefined;
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
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      setPos(null);
    };
  }, [open, collapsed]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!triggerRef.current?.contains(t) && !menuRef.current?.contains(t)) close(false);
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [open, close]);

  useEffect(() => {
    if (open && pos) menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
  }, [open, pos]);

  function onMenuKey(e: KeyboardEvent) {
    const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
    const i = items.indexOf(document.activeElement as HTMLElement);
    const focusAt = (index: number) => items[(index + items.length) % items.length]?.focus();
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'Tab') close(false);
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusAt(i + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusAt(i - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      focusAt(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      focusAt(items.length - 1);
    }
  }

  function openDialog(which: 'about' | 'password') {
    close(false);
    setDialog(which);
  }

  function closeDialog() {
    setDialog(null);
    triggerRef.current?.focus();
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`profile-trigger ${open ? 'is-open' : ''}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${name}`}
        data-tip={collapsed && !open ? name : undefined}
        onClick={() => setOpen(o => !o)}
      >
        <span className="avatar">{initials(name)}</span>
        <span className="sidebar-profile-text sidebar-text">
          <strong>{name}</strong>
          <small>{roleName}</small>
        </span>
        <ChevronsUpDown className="profile-chevron sidebar-text" size={16} aria-hidden="true" />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={menuRef}
            className="profile-menu"
            role="menu"
            aria-label="Account"
            tabIndex={-1}
            style={{ left: pos.left, bottom: pos.bottom, width: pos.width }}
            onKeyDown={onMenuKey}
          >
            <div className="profile-menu-head">
              <span className="avatar">{initials(name)}</span>
              <span>
                <strong>{name}</strong>
                <small>{roleName}</small>
              </span>
            </div>
            <div className="profile-menu-sep" role="separator" />
            <button
              type="button"
              role="menuitem"
              className="profile-menu-item"
              onClick={() => openDialog('password')}
            >
              <KeyRound size={18} aria-hidden="true" /> Change password
            </button>
            <button
              type="button"
              role="menuitem"
              className="profile-menu-item"
              onClick={() => openDialog('about')}
            >
              <Info size={18} aria-hidden="true" /> About VerifyLens
            </button>
            <div className="profile-menu-sep" role="separator" />
            <button
              type="button"
              role="menuitem"
              className="profile-menu-item"
              onClick={() => {
                close(false);
                logout();
              }}
            >
              <LogOut size={18} aria-hidden="true" /> Log out
            </button>
          </div>,
          document.body,
        )}

      {dialog === 'about' && <AboutDialog onClose={closeDialog} />}
      {dialog === 'password' && <ChangePasswordDialog onClose={closeDialog} />}
    </>
  );
}
