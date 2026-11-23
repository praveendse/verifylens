import { useId, useState } from 'react';
import './stats-donut.css';

/* Status categories, in fixed order (colour follows the category, never its rank).
   Colours are the shared --viz-* chart tokens (styles.css); each row also has a text label,
   so identity never depends on colour alone. */
// `key` is the field name in the GET /history/stats response.
export const CATEGORIES = [
  { key: 'match', label: 'Match verified', color: 'var(--viz-match)' },
  { key: 'no_match', label: 'No match', color: 'var(--viz-no-match)' },
  { key: 'error', label: 'Failed', color: 'var(--viz-error)' },
  // Anything else (PENDING, SUCCESS without a verdict, unknown statuses). Hidden when 0.
  { key: 'other', label: 'Not finished', color: 'var(--viz-other)', optional: true },
];

const R = 54;            // ring radius (viewBox units)
const STROKE = 16;       // ring thickness
const C = 2 * Math.PI * R;
const GAP = 2.5;         // surface gap between segments (≈2px at the rendered size)

function summarise(stats) {
  return CATEGORIES
    .map(c => ({ ...c, count: Number(stats?.[c.key]) || 0 }))
    .filter(c => !c.optional || c.count > 0);
}

const pct = (n, total) => (total ? Math.round((n / total) * 100) : 0);

/* stats: server totals over the user's whole history (null while loading).
   title / subtitle override the History wording; compact stacks the legend
   under the ring for narrow columns (admin overview). */
export default function StatsDonut({ stats, title = 'Search outcomes', subtitle, compact = false }) {
  const [active, setActive] = useState(null);
  const titleId = useId();
  const loading = !stats;
  const rows = summarise(stats);
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  const completed = Number(stats?.completed) || 0;
  const visible = rows.filter(r => r.count > 0);
  const focus = rows.find(r => r.key === active && r.count > 0);

  // Segment geometry: arcs laid out clockwise from 12 o'clock, a gap between each.
  let offset = 0;
  const segments = visible.map(row => {
    const len = (row.count / total) * C;
    const gap = visible.length > 1 ? Math.min(GAP, len / 2) : 0;
    const seg = { ...row, dash: Math.max(len - gap, 0.001), offset };
    offset += len;
    return seg;
  });

  const summary = total
    ? `${total} searches: ${rows.map(r => `${r.count} ${r.label.toLowerCase()}`).join(', ')}.`
    : 'No searches yet.';

  return (
    <section className={`donut-card${compact ? ' is-compact' : ''}`} aria-labelledby={titleId}>
      <div className="donut-head">
        <h2 id={titleId}>{title}</h2>
        <p>{subtitle ?? (loading ? 'Loading…' : total ? `${completed} of ${total} searches completed (${pct(completed, total)}%)` : 'Results appear here after your first search.')}</p>
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
                  cx="70" cy="70" r={R}
                  stroke={s.color} strokeWidth={STROKE}
                  strokeDasharray={`${s.dash} ${C}`}
                  strokeDashoffset={-s.offset}
                  onPointerEnter={() => setActive(s.key)}
                  onPointerLeave={() => setActive(null)}
                />
              ))}
            </g>
          </svg>
          {/* Centre readout doubles as the hover tooltip: total by default, the hovered category otherwise */}
          <div className="donut-center" aria-hidden="true">
            <strong>{focus ? focus.count : total}</strong>
            <span>{focus ? `${focus.label} · ${pct(focus.count, total)}%` : total === 1 ? 'search' : 'searches'}</span>
          </div>
        </div>

        <ul className="donut-legend">
          {rows.map(row => {
            return (
              <li
                key={row.key}
                className={`${focus && focus.key !== row.key ? 'is-dim' : ''} ${row.count === 0 ? 'is-empty' : ''}`}
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
            );
          })}
        </ul>
      </div>
    </section>
  );
}
