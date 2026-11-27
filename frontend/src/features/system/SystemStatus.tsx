import { ChevronDown, RefreshCw } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { describeStatus } from './describeStatus';
import { SYSTEM_POLL_MS, useSystemStatus } from './queries';
import '@/styles/system-status.css';

const STAMP = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' });

function ago(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  return `${Math.round(s / 60)} min ago`;
}

/**
 * Live status light in the top bar. Never green without a successful check.
 * Admins (detailed) can open a panel with each dependency; the backend leaves
 * the per-part list out for other users anyway.
 */
export function SystemStatus({ detailed = false }: { detailed?: boolean }) {
  const status = useSystemStatus();
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const rootRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const view = describeStatus(status.data, status.error, status.isPending);

  // Tick every second while the panel is open, for "Xs ago".
  useEffect(() => {
    if (!open) return undefined;
    const tick = setInterval(() => setNow(Date.now()), 1_000);
    return () => clearInterval(tick);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: PointerEvent) => !rootRef.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!detailed) {
    return (
      <div className="sys-status">
        <span className={`sys-status-trigger is-static tone-${view.tone}`}>
          <span className="sys-led" aria-hidden="true" />
          <span className="sys-status-label" role="status" aria-live="polite">
            {view.label}
          </span>
        </span>
      </div>
    );
  }

  const checkedAt = status.data?.checked_at ? new Date(status.data.checked_at).getTime() : null;
  const busy = status.isFetching;

  return (
    <div className="sys-status" ref={rootRef}>
      <button
        type="button"
        className={`sys-status-trigger tone-${view.tone}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => {
          setNow(Date.now());
          setOpen(o => !o);
        }}
      >
        <span className="sys-led" aria-hidden="true" />
        <span className="sys-status-label" role="status" aria-live="polite">
          {view.label}
        </span>
        <ChevronDown size={14} className="sys-status-chevron" aria-hidden="true" />
      </button>

      {open && (
        <div className="sys-status-panel" id={panelId}>
          {view.components.length > 0 ? (
            <ul>
              {view.components.map(c => (
                <li key={c.name} className={`tone-${c.status === 'ok' ? 'ok' : 'down'}`}>
                  <span className="sys-dot" aria-hidden="true" />
                  <span className="sys-name">{c.label}</span>
                  <span className="sys-meta">
                    {c.status === 'ok'
                      ? `Working · ${c.latency_ms} ms`
                      : `Not working${c.detail ? ` · ${c.detail}` : ''}`}
                  </span>
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
                <time dateTime={new Date(checkedAt).toISOString()}>{STAMP.format(checkedAt)}</time>
                <span className="sys-age">
                  {busy
                    ? 'Checking now…'
                    : `${ago(now - checkedAt)} · checks every ${SYSTEM_POLL_MS / 60_000} min`}
                </span>
              </span>
            ) : (
              <span>{busy ? 'Checking now…' : 'Not checked'}</span>
            )}
            <button
              type="button"
              onClick={() => status.refetch()}
              disabled={busy}
              aria-label="Check system status now"
            >
              <RefreshCw size={13} className={busy ? 'spin' : ''} aria-hidden="true" /> Recheck
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
