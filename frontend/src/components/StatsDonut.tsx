import { useId, useState } from 'react';
import { startOffsets } from '@/lib/math';
import { CATEGORIES, type OutcomeCounts, type OutcomeKey } from './outcomes';
import '@/styles/stats-donut.css';

const R = 54;
const STROKE = 16;
const C = 2 * Math.PI * R;
const GAP = 2.5;
const pct = (n: number, total: number) => (total ? Math.round((n / total) * 100) : 0);

interface StatsDonutProps {
  stats: OutcomeCounts | null | undefined;
  title?: string;
  subtitle?: string;
  compact?: boolean;
}

/** Outcome split as a donut + legend. The SVG has a text summary for screen readers. */
export function StatsDonut({ stats, title = 'Search outcomes', subtitle, compact = false }: StatsDonutProps) {
  const [active, setActive] = useState<OutcomeKey | null>(null);
  const titleId = useId();
  const loading = !stats;
  const rows = CATEGORIES.map(c => ({ ...c, count: Number(stats?.[c.key]) || 0 })).filter(
    c => !c.optional || c.count > 0,
  );
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  const completed = Number(stats?.completed) || 0;
  const visible = rows.filter(r => r.count > 0);
  const focus = rows.find(r => r.key === active && r.count > 0);

  const lengths = visible.map(row => (row.count / total) * C);
  const offsets = startOffsets(lengths);
  const segments = visible.map((row, i) => {
    const len = lengths[i] ?? 0;
    const gap = visible.length > 1 ? Math.min(GAP, len / 2) : 0;
    return { ...row, dash: Math.max(len - gap, 0.001), offset: offsets[i] ?? 0 };
  });

  const summary = total
    ? `${total} searches: ${rows.map(r => `${r.count} ${r.label.toLowerCase()}`).join(', ')}.`
    : 'No searches yet.';
  const defaultSubtitle = loading
    ? 'Loading…'
    : total
      ? `${completed} of ${total} searches completed (${pct(completed, total)}%)`
      : 'Results appear here after your first search.';

  return (
    <section className={`donut-card${compact ? ' is-compact' : ''}`} aria-labelledby={titleId}>
      <div className="donut-head">
        <h2 id={titleId}>{title}</h2>
        <p>{subtitle ?? defaultSubtitle}</p>
      </div>
      <div className="donut-body">
        <div className="donut-chart">
          <svg viewBox="0 0 140 140" role="img" aria-label={summary}>
            <circle className="donut-track" cx="70" cy="70" r={R} strokeWidth={STROKE} />
            <g transform="rotate(-90 70 70)">
              {segments.map(s => (
                <circle
                  key={s.key}
                  className={`donut-seg ${focus && focus.key !== s.key ? 'is-dim' : ''}`}
                  cx="70"
                  cy="70"
                  r={R}
                  stroke={s.color}
                  strokeWidth={STROKE}
                  strokeDasharray={`${s.dash} ${C}`}
                  strokeDashoffset={-s.offset}
                  onPointerEnter={() => setActive(s.key)}
                  onPointerLeave={() => setActive(null)}
                />
              ))}
            </g>
          </svg>
          <div className="donut-center" aria-hidden="true">
            <strong>{focus ? focus.count : total}</strong>
            <span>
              {focus ? `${focus.label} · ${pct(focus.count, total)}%` : total === 1 ? 'search' : 'searches'}
            </span>
          </div>
        </div>
        <ul className="donut-legend">
          {rows.map(row => (
            <li
              key={row.key}
              className={`${focus && focus.key !== row.key ? 'is-dim' : ''} ${row.count === 0 ? 'is-empty' : ''}`}
              // Focusable legend rows highlight their segment for keyboard users too.
              // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
              tabIndex={row.count ? 0 : undefined}
              onPointerEnter={() => setActive(row.key)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(row.key)}
              onBlur={() => setActive(null)}
            >
              <span className="donut-swatch" style={{ background: row.color }} />
              <span className="donut-label">{row.label}</span>
              <span className="donut-count">{row.count}</span>
              <span className="donut-pct">{pct(row.count, total)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
