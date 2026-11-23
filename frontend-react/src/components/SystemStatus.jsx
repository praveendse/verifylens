import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { ChevronDown, RefreshCw } from 'lucide-react';
import './system-status.css';

const POLL_MS = 60_000;
// Exact time of the last check, in the viewer's locale and time zone, e.g. "21 Nov 2026, 6:12:05 AM".
const STAMP = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' });

/**
 * Live system-status light, driven by GET /api/v1/health/systems.
 *   green (blinking) - every dependency check passed
 *   red              - a dependency is down, or the backend itself is unreachable
 *   grey             - checking, preview mode, or status unknown (e.g. session expired)
 * Never shows green without a successful check.
 * detailed (admins): the pill opens a panel with each part and the last check.
 * Otherwise only the plain-language pill is shown; the backend also leaves the
 * per-part list out for non-admins.
 */
export default function SystemStatus({ check, detailed = false }) {
  const [state, setState] = useState({ phase: 'checking' });
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(Date.now());
  const rootRef = useRef(null);
  const panelId = useId();
  const inFlight = useRef(false);
  const [busy, setBusy] = useState(false);
  const [nextAt, setNextAt] = useState(null);   // when the next automatic check is due

  const run = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const data = await check();
      setState({ phase: 'done', data });
    } catch (err) {
      setState({ phase: 'error', status: err?.status ?? 0, message: err?.message || 'Status check failed' });
    } finally {
      inFlight.current = false;
      setBusy(false);
      setNextAt(Date.now() + POLL_MS);       // next auto-check is timed from when this one finished
    }
  }, [check]);

  // First check, and re-check when the tab becomes visible again.
  useEffect(() => {
    run();
    const onVisible = () => { if (document.visibilityState === 'visible') run(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [run]);

  // Automatic check when due (skipped while the tab is hidden; the visibility handler catches up).
  useEffect(() => {
    if (!nextAt) return undefined;
    const timer = setTimeout(() => { if (document.visibilityState === 'visible') run(); }, Math.max(0, nextAt - Date.now()));
    return () => clearTimeout(timer);
  }, [nextAt, run]);

  // Tick every second while the panel is open, for "Xs ago" and the countdown.
  useEffect(() => {
    if (!open) return undefined;
    setNow(Date.now());
    const tick = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(tick);
  }, [open]);

  // Close the panel on outside click / Escape.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = e => { if (!rootRef.current?.contains(e.target)) setOpen(false); };
    const onKey = e => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const view = describe(state);

  if (!detailed) {
    return (
      <div className="sys-status">
        <span className={`sys-status-trigger is-static tone-${view.tone}`}>
          <span className="sys-led" aria-hidden="true"/>
          <span className="sys-status-label" role="status" aria-live="polite">{view.label}</span>
        </span>
      </div>
    );
  }
  const checkedAt = state.phase === 'done' && state.data?.checked_at ? new Date(state.data.checked_at).getTime() : null;

  return (
    <div className="sys-status" ref={rootRef}>
      <button
        type="button"
        className={`sys-status-trigger tone-${view.tone}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(o => !o)}
      >
        <span className="sys-led" aria-hidden="true"/>
        <span className="sys-status-label" role="status" aria-live="polite">{view.label}</span>
        <ChevronDown size={14} className="sys-status-chevron" aria-hidden="true"/>
      </button>

      {open && (
        <div className="sys-status-panel" id={panelId}>
          {view.components.length > 0 ? (
            <ul>
              {view.components.map(c => (
                <li key={c.name} className={`tone-${c.status === 'ok' ? 'ok' : 'down'}`}>
                  <span className="sys-dot" aria-hidden="true"/>
                  <span className="sys-name">{c.label}</span>
                  <span className="sys-meta">{c.status === 'ok' ? `Working · ${c.latency_ms} ms` : `Not working${c.detail ? ` · ${c.detail}` : ''}`}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sys-note">{view.note}</p>
          )}
          <div className="sys-foot">
            {checkedAt ? (
              <span className="sys-checked">
                <span className="sys-checked-label">Last check</span>
                {/* Fixed: the moment the backend ran the checks. Changes only when a new check runs. */}
                <time dateTime={new Date(checkedAt).toISOString()}>{STAMP.format(checkedAt)}</time>
                <span className="sys-age">
                  {busy ? 'Checking now…' : `${ago(now - checkedAt)}${nextAt ? ` · next check in ${countdown(nextAt - now)}` : ''}`}
                </span>
              </span>
            ) : <span>{busy ? 'Checking now…' : view.phaseNote}</span>}
            <button type="button" onClick={run} disabled={busy} aria-label="Check system status now">
              <RefreshCw size={13} className={busy ? 'spin' : ''}/> Recheck
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function describe(state) {
  if (state.phase === 'checking') {
    return { tone: 'idle', label: 'Checking…', components: [], note: 'Running live checks…', phaseNote: 'Checking…' };
  }
  if (state.phase === 'error') {
    if (state.status === 0) {
      return { tone: 'down', label: "Can't reach the server", components: [], note: 'The app server is not answering. Check your connection, then try again.', phaseNote: 'Last check failed' };
    }
    if (state.status === 401 || state.status === 403) {
      return { tone: 'idle', label: 'Status unavailable', components: [], note: 'Your session has expired. Sign in again to see live status.', phaseNote: 'Not checked' };
    }
    return { tone: 'down', label: "Couldn't check status", components: [], note: 'The status check did not finish. Try again in a minute.', phaseNote: 'Last check failed' };
  }
  const data = state.data || {};
  if (data.status === 'demo') {
    return { tone: 'idle', label: 'Preview mode · live checks off', components: [], note: 'Preview mode has no backend, so Gemini, Wikipedia and the database are not checked.', phaseNote: 'Not checked' };
  }
  // Admins get every part; other users only the overall status (empty list).
  const components = Array.isArray(data.components) ? data.components : [];
  const down = components.filter(c => c.status !== 'ok');
  if (data.status === 'ok' && down.length === 0) {
    return { tone: 'ok', label: 'Everything is working', components };
  }
  if (data.status !== 'degraded') {
    return { tone: 'idle', label: 'Status unknown', components, note: 'No status to show yet.' };
  }
  const names = down.map(c => c.label);
  const label = names.length === 0 ? "Some features aren't working right now"
    : names.length === 1 ? `${names[0]} isn't working`
    : `${names.slice(0, -1).join(', ')} and ${names.at(-1)} aren't working`;
  return { tone: 'down', label, components, note: 'Some features may not work right now.' };
}

function countdown(ms) {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

function ago(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  return `${Math.round(s / 60)} min ago`;
}
