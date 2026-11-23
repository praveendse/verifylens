/* Small visuals for the admin overview. Each is chosen for one job:
   MiniDonut    - a few parts of one whole (accounts, outcomes, who searched)
   DetailList   - the exact counts printed beside a ring
   Sparkline    - a short trend under a headline number
   BarList      - ranking / comparing a handful of named values
   Colours come from the --viz-* tokens; text always uses text tokens, and
   every visual has an accessible text equivalent. */

/* Small ring for a tile: parts of one whole, read alongside the exact counts
   printed next to it (the ring gives the proportion, the text the detail).
   A part with track: true is drawn as the unfilled track (e.g. "didn't search"). */
const RING_R = 26;
const RING_C = 2 * Math.PI * RING_R;
export function MiniDonut({ parts, label }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  const filled = parts.filter(p => p.value > 0 && !p.track);
  const gap = filled.length > 1 || parts.some(p => p.track && p.value > 0) ? 2.5 : 0;
  let offset = 0;
  return (
    <svg className="ov-ring" viewBox="0 0 64 64" role="img"
      aria-label={`${label}: ${parts.map(p => `${p.value} ${p.label.toLowerCase()}`).join(', ')}`}>
      <circle cx="32" cy="32" r={RING_R} className="ov-ring-track"/>
      <g transform="rotate(-90 32 32)">
        {total > 0 && parts.map(p => {
          const len = (p.value / total) * RING_C;
          const start = offset;
          offset += len;
          if (p.track || !p.value) return null;
          return (
            <circle key={p.key} cx="32" cy="32" r={RING_R} stroke={p.color}
              strokeDasharray={`${Math.max(len - gap, 0.001)} ${RING_C}`} strokeDashoffset={-start}>
              <title>{`${p.label}: ${p.value}`}</title>
            </circle>
          );
        })}
      </g>
    </svg>
  );
}

/* Exact counts that go with a MiniDonut (or stand alone). */
export function DetailList({ rows }) {
  return (
    <ul className="ov-details">
      {rows.map(r => (
        <li key={r.key} className={r.value ? '' : 'is-empty'}>
          {/* colour = a ring part; track = the ring's unfilled part; neither = plain row */}
          {r.color ? <span className="activity-swatch" style={{ background: r.color }}/> : <span className={r.track ? 'activity-swatch is-blank' : ''}/>}
          <span>{r.label}</span>
          <b>{r.value.toLocaleString()}</b>
          {r.note && <small>{r.note}</small>}
        </li>
      ))}
    </ul>
  );
}

/* Columns, not a line: 7 daily counts read better as discrete days. The last
   column (today) is full strength, earlier days a lighter step. */
export function Sparkline({ values, labels, label }) {
  const max = Math.max(1, ...values);
  const W = 100, H = 30, gap = 3;
  const w = (W - gap * (values.length - 1)) / values.length;
  return (
    <svg className="ov-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
      aria-label={`${label}: ${values.map((v, i) => `${labels[i]} ${v}`).join(', ')}`}>
      {values.map((v, i) => {
        const h = v ? Math.max(2, (v / max) * H) : 1;
        return (
          <rect key={labels[i]} x={i * (w + gap)} y={H - h} width={w} height={h} rx={1.5}
            className={i === values.length - 1 ? 'is-current' : v ? '' : 'is-zero'}>
            <title>{`${labels[i]}: ${v}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

export function BarList({ items, color = 'var(--viz-series)', unit, emptyText }) {
  if (!items.length) return <div className="table-empty">{emptyText}</div>;
  const max = Math.max(...items.map(i => i.value));
  return (
    <ol className="ov-bars">
      {items.map(item => (
        <li key={item.key}>
          <span className="ov-bars-name">
            {item.lead}
            <span className="ov-list-text"><strong>{item.label}</strong>{item.sub && <small>{item.sub}</small>}</span>
          </span>
          <span className="ov-bars-track" aria-hidden="true">
            <span style={{ width: `${(item.value / max) * 100}%`, background: color }}/>
          </span>
          <span className="ov-bars-value">{item.value.toLocaleString()}<span className="sr-only"> {unit}</span></span>
        </li>
      ))}
    </ol>
  );
}
