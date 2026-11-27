import type { ReactNode } from 'react';
import { startOffsets } from '@/lib/math';

/** Small visuals for the admin overview. Every visual has a text equivalent. */

export interface Part {
  key: string;
  label: string;
  value: number;
  color?: string | null;
  track?: boolean;
  note?: string;
}

const RING_R = 26;
const RING_C = 2 * Math.PI * RING_R;

/** Small ring: parts of one whole. A part with track: true is the unfilled track. */
export function MiniDonut({ parts, label }: { parts: Part[]; label: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const filled = parts.filter(p => p.value > 0 && !p.track);
  const gap = filled.length > 1 || parts.some(p => p.track && p.value > 0) ? 2.5 : 0;
  const lengths = parts.map(p => (total ? (p.value / total) * RING_C : 0));
  const offsets = startOffsets(lengths);
  return (
    <svg
      className="ov-ring"
      viewBox="0 0 64 64"
      role="img"
      aria-label={`${label}: ${parts.map(p => `${p.value} ${p.label.toLowerCase()}`).join(', ')}`}
    >
      <circle cx="32" cy="32" r={RING_R} className="ov-ring-track" />
      <g transform="rotate(-90 32 32)">
        {total > 0 &&
          parts.map((p, i) => {
            const len = lengths[i] ?? 0;
            const start = offsets[i] ?? 0;
            if (p.track || !p.value) return null;
            return (
              <circle
                key={p.key}
                cx="32"
                cy="32"
                r={RING_R}
                stroke={p.color ?? undefined}
                strokeDasharray={`${Math.max(len - gap, 0.001)} ${RING_C}`}
                strokeDashoffset={-start}
              >
                <title>{`${p.label}: ${p.value}`}</title>
              </circle>
            );
          })}
      </g>
    </svg>
  );
}

export function DetailList({ rows }: { rows: Part[] }) {
  return (
    <ul className="ov-details">
      {rows.map(r => (
        <li key={r.key} className={r.value ? '' : 'is-empty'}>
          {r.color ? (
            <span className="activity-swatch" style={{ background: r.color }} />
          ) : (
            <span className={r.track ? 'activity-swatch is-blank' : ''} />
          )}
          <span>{r.label}</span>
          <b>{r.value.toLocaleString()}</b>
          {r.note && <small>{r.note}</small>}
        </li>
      ))}
    </ul>
  );
}

/** Daily columns under a headline number; the last column (today) is full strength. */
export function Sparkline({ values, labels, label }: { values: number[]; labels: string[]; label: string }) {
  const max = Math.max(1, ...values);
  const W = 100;
  const H = 30;
  const gap = 3;
  const w = (W - gap * (values.length - 1)) / values.length;
  return (
    <svg
      className="ov-spark"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${label}: ${values.map((v, i) => `${labels[i]} ${v}`).join(', ')}`}
    >
      {values.map((v, i) => {
        const h = v ? Math.max(2, (v / max) * H) : 1;
        return (
          <rect
            key={`${labels[i]}-${i}`}
            x={i * (w + gap)}
            y={H - h}
            width={w}
            height={h}
            rx={1.5}
            className={i === values.length - 1 ? 'is-current' : v ? '' : 'is-zero'}
          >
            <title>{`${labels[i]}: ${v}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

export interface BarItem {
  key: string | number;
  label: string;
  sub?: string;
  value: number;
  lead?: ReactNode;
}

export function BarList({
  items,
  color = 'var(--viz-series)',
  unit,
  emptyText,
}: {
  items: BarItem[];
  color?: string;
  unit: string;
  emptyText?: string;
}) {
  if (!items.length) return <div className="table-empty">{emptyText}</div>;
  const max = Math.max(...items.map(i => i.value));
  return (
    <ol className="ov-bars">
      {items.map(item => (
        <li key={item.key}>
          <span className="ov-bars-name">
            {item.lead}
            <span className="ov-list-text">
              <strong>{item.label}</strong>
              {item.sub && <small>{item.sub}</small>}
            </span>
          </span>
          <span className="ov-bars-track" aria-hidden="true">
            <span style={{ width: `${(item.value / max) * 100}%`, background: color }} />
          </span>
          <span className="ov-bars-value">
            {item.value.toLocaleString()}
            <span className="sr-only"> {unit}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
