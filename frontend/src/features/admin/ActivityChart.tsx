import { useLayoutEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react';
import type { DailyActivity } from '@/api/types';
import { CATEGORIES } from '@/components/outcomes';
import { niceTicks } from '@/lib/math';

/* Searches per day, stacked by outcome (same categories/colours as the donut).
   Hover or arrow keys show one day's breakdown; the data is also available as a table. */

const PLOT_H = 168;
const AXIS_W = 34;
const X_AXIS_H = 26;
const GAP = 2;
const MAX_BAR = 24;

const dayLabel = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

/** Element width that follows resizes (ResizeObserver). */
function useWidth(ref: RefObject<HTMLElement | null>) {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    setWidth(el.clientWidth);
    const ro = new ResizeObserver(([entry]) => entry && setWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

function topRounded(x: number, y: number, w: number, h: number, r: number) {
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export function ActivityChart({ daily }: { daily: DailyActivity[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const width = useWidth(wrapRef);
  const [active, setActive] = useState<number | null>(null);
  const days = daily.map(d => ({ ...d, total: CATEGORIES.reduce((s, c) => s + (d[c.key] || 0), 0) }));
  const ticks = niceTicks(Math.max(0, ...days.map(d => d.total)));
  const top = ticks[ticks.length - 1] ?? 1;

  const plotW = Math.max(0, width - AXIS_W);
  const slot = days.length ? plotW / days.length : 0;
  const barW = Math.max(3, Math.min(MAX_BAR, slot * 0.62));
  const y = (v: number) => PLOT_H - (v / top) * PLOT_H;
  const labelEvery = width < 520 ? 10 : 7;

  function onKeyDown(event: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const last = days.length - 1;
    setActive(i => {
      if (event.key === 'Home') return 0;
      if (event.key === 'End') return last;
      const from = i ?? last;
      return Math.max(0, Math.min(last, from + (event.key === 'ArrowLeft' ? -1 : 1)));
    });
  }

  const focus = active != null ? days[active] : undefined;
  const summary = `Searches per day for the last ${days.length} days: ${days.reduce((s, d) => s + d.total, 0)} in total. Use the arrow keys to read each day, or open the table below.`;

  return (
    <div className="activity-chart">
      <ul className="activity-legend">
        {CATEGORIES.filter(c => !c.optional || days.some(d => d[c.key])).map(c => (
          <li key={c.key}>
            <span className="activity-swatch" style={{ background: c.color }} />
            {c.label}
          </li>
        ))}
      </ul>

      {/* Focusable chart: arrow keys move between days (keyboard equivalent of hover). */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div
        className="activity-plot"
        ref={wrapRef}
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        role="img"
        aria-label={summary}
        onKeyDown={onKeyDown}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
      >
        {width > 0 && (
          <svg width={width} height={PLOT_H + X_AXIS_H} aria-hidden="true">
            {ticks.map(t => (
              <g key={t}>
                <line className="activity-grid" x1={AXIS_W} x2={width} y1={y(t) + 0.5} y2={y(t) + 0.5} />
                <text className="activity-tick" x={AXIS_W - 8} y={y(t)} dy="0.32em" textAnchor="end">
                  {t.toLocaleString()}
                </text>
              </g>
            ))}
            {days.map((d, i) => {
              const x = AXIS_W + i * slot + (slot - barW) / 2;
              const parts = CATEGORIES.filter(c => d[c.key] > 0);
              let base = PLOT_H;
              return (
                <g key={d.date} className={active != null && active !== i ? 'is-dim' : ''}>
                  {active === i && (
                    <rect
                      className="activity-band"
                      x={AXIS_W + i * slot}
                      y={0}
                      width={slot}
                      height={PLOT_H}
                      rx={6}
                    />
                  )}
                  {parts.map((c, k) => {
                    const h = (d[c.key] / top) * PLOT_H;
                    const isTop = k === parts.length - 1;
                    const drawH = Math.max(1, h - (isTop ? 0 : GAP));
                    const yTop = base - h + (isTop ? 0 : GAP);
                    base -= h;
                    return isTop ? (
                      <path key={c.key} d={topRounded(x, yTop, barW, drawH, 4)} fill={c.color} />
                    ) : (
                      <rect key={c.key} x={x} y={yTop} width={barW} height={drawH} fill={c.color} />
                    );
                  })}
                  {(days.length - 1 - i) % labelEvery === 0 && (
                    <text
                      className="activity-tick"
                      x={AXIS_W + i * slot + slot / 2}
                      y={PLOT_H + 18}
                      textAnchor="middle"
                    >
                      {dayLabel(d.date)}
                    </text>
                  )}
                  <rect
                    x={AXIS_W + i * slot}
                    y={0}
                    width={slot}
                    height={PLOT_H}
                    fill="transparent"
                    onPointerEnter={() => setActive(i)}
                  />
                </g>
              );
            })}
            <line className="activity-baseline" x1={AXIS_W} x2={width} y1={PLOT_H + 0.5} y2={PLOT_H + 0.5} />
          </svg>
        )}

        {focus && active != null && (
          <div
            className="activity-tip"
            style={{ left: Math.min(Math.max(AXIS_W + active * slot + slot / 2, 90), width - 90) }}
            aria-live="polite"
          >
            <strong>{dayLabel(focus.date)}</strong>
            <span className="activity-tip-total">
              {focus.total} {focus.total === 1 ? 'search' : 'searches'}
            </span>
            {CATEGORIES.filter(c => !c.optional || focus[c.key]).map(c => (
              <span key={c.key} className="activity-tip-row">
                <span className="activity-swatch" style={{ background: c.color }} />
                {c.label}
                <b>{focus[c.key] || 0}</b>
              </span>
            ))}
          </div>
        )}
      </div>

      <details className="activity-table">
        <summary>View as table</summary>
        <div className="activity-table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                {CATEGORIES.map(c => (
                  <th scope="col" key={c.key}>
                    {c.label}
                  </th>
                ))}
                <th scope="col">Total</th>
              </tr>
            </thead>
            <tbody>
              {[...days].reverse().map(d => (
                <tr key={d.date}>
                  <td>{dayLabel(d.date)}</td>
                  {CATEGORIES.map(c => (
                    <td key={c.key}>{d[c.key] || 0}</td>
                  ))}
                  <td>{d.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
