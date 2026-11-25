import { useState } from 'react';
import { ArrowDownRight, ArrowUpRight, CheckCircle2, ChevronDown, ChevronUp, RefreshCw, Search, UserCheck, Users2 } from 'lucide-react';
import ActivityChart from './ActivityChart.jsx';
import StatsDonut from './StatsDonut.jsx';
import { BarList, DetailList, MiniDonut, Sparkline } from './OverviewVisuals.jsx';
import './admin-overview.css';

/* Admin overview page. Numbers come from GET /admin/overview (aggregates only).
   Each visual matches its job: donut for the outcome split, columns for the
   30-day trend, bars for rankings, meters for single shares. Lists stay text
   where the detail matters (recent errors, accounts needing attention). */

const initials = u => (u.full_name || u.username).split(/\s+/).map(p => p[0]).slice(0, 2).join('').toUpperCase();
const pct = (n, d) => (d ? Math.round((n / d) * 100) : null);
const rtf = typeof Intl !== 'undefined' && Intl.RelativeTimeFormat ? new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }) : null;
const shortDay = iso => new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' });

function ago(iso) {
  if (!iso) return '';
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  for (const [unit, size] of [['day', 86400], ['hour', 3600], ['minute', 60]]) {
    if (Math.abs(seconds) >= size) return rtf ? rtf.format(Math.round(seconds / size), unit) : new Date(iso).toLocaleString();
  }
  return 'just now';
}

function Delta({ now, before, days }) {
  if (!before) return <span className="ov-delta">{now ? `None in the previous ${days} days` : `None in the previous ${days} days either`}</span>;
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return <span className="ov-delta">Same as the previous {days} days</span>;
  const up = change > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`ov-delta ${up ? 'is-up' : 'is-down'}`}>
      <Icon size={14} aria-hidden="true"/>{up ? '+' : '−'}{Math.abs(change)}% vs previous {days} days
    </span>
  );
}

const FAILURES_SHOWN = 3; // latest failed searches shown before "Show more"

/* Titled block of the page: heading, rule, then content. */
function Section({ id, title, children }) {
  return (
    <section className="ov-section" aria-labelledby={id}>
      <header className="ov-section-head">
        <h2 id={id}>{title}</h2>
      </header>
      {children}
    </section>
  );
}

/* ring: a MiniDonut shown left of the number; details: exact counts under it. */
function Tile({ icon: Icon, label, value, ring, visual, details, children }) {
  return (
    <div className={`ov-tile${ring ? ' has-ring' : ''}`}>
      <span className="ov-tile-label"><Icon size={15} aria-hidden="true"/>{label}</span>
      <div className="ov-tile-body">
        {ring}
        <div className="ov-tile-main">
          <strong className="ov-tile-value">{value}</strong>
          {children && <span className="ov-tile-sub">{children}</span>}
        </div>
      </div>
      {visual}
      {details}
    </div>
  );
}

export default function AdminOverview({ data, loading, error, onRefresh, onManageUsers }) {
  const [allFailures, setAllFailures] = useState(false);
  const heading = (
    <div className="page-top-heading">
      <div><h1>Admin <span>overview.</span></h1><p>How the platform is being used, and what needs your attention.</p></div>
      <button type="button" className="outline-button" onClick={onRefresh} disabled={loading}>
        <RefreshCw size={16} className={loading ? 'spin' : ''}/> Refresh
      </button>
    </div>
  );

  if (!data) {
    return (
      <div className="page-container">
        {heading}
        {error
          ? <div className="alert alert-danger" role="alert">{error}</div>
          : <div className="admin-card table-empty">Loading overview…</div>}
      </div>
    );
  }

  const { users, last_period: last, previous_period: prev, kpi_days: kpiDays, trend_days: trendDays } = data;
  const completed = last.match + last.no_match;
  const successRate = pct(completed, last.total);
  const activeAccounts = users.total - users.inactive;
  const idle = data.idle_users;
  const attention = idle.count > 0 || users.inactive > 0;

  const outcome30 = data.daily.reduce((acc, d) => {
    ['match', 'no_match', 'error', 'other'].forEach(k => { acc[k] += d[k]; });
    return acc;
  }, { match: 0, no_match: 0, error: 0, other: 0 });
  outcome30.completed = outcome30.match + outcome30.no_match;
  const trendTotal = outcome30.completed + outcome30.error + outcome30.other;

  const week = data.daily.slice(-kpiDays);
  const weekTotals = week.map(d => d.match + d.no_match + d.error + d.other);
  const busiest = weekTotals.some(Boolean)
    ? week.map((d, i) => ({ date: d.date, total: weekTotals[i] })).reduce((a, b) => (b.total > a.total ? b : a))
    : null;

  // Parts of a whole for the tile rings; the same rows print the exact counts.
  const accountParts = [
    { key: 'user', label: 'Users', value: users.active_users, color: 'var(--viz-role-user)' },
    { key: 'admin', label: 'Admins', value: users.active_admins, color: 'var(--viz-role-admin)' },
    { key: 'inactive', label: 'Inactive', value: users.inactive, color: 'var(--viz-inactive)' },
  ];
  const successParts = [
    { key: 'done', label: 'Completed', value: completed, color: 'var(--viz-match)',
      note: completed ? `${last.match} match · ${last.no_match} no match` : undefined },
    { key: 'error', label: 'Failed', value: last.error, color: 'var(--viz-error)' },
    ...(last.other ? [{ key: 'other', label: 'Not finished', value: last.other, color: 'var(--viz-other)' }] : []),
  ];
  const activityParts = [
    { key: 'searched', label: 'Searched', value: last.active_users, color: 'var(--viz-series)' },
    { key: 'quiet', label: "Didn't search", value: Math.max(0, activeAccounts - last.active_users), track: true },
  ];

  return (
    <div className={`page-container ov ${loading ? 'is-refreshing' : ''}`} aria-busy={loading}>
      {heading}
      <p className="ov-updated">Updated {ago(data.generated_at)} · days are counted in UTC</p>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}

      <Section id="ov-glance-title" title="At a glance">
      <div className="ov-tiles">
        <Tile icon={Users2} label="Team members" value={users.total.toLocaleString()}
          ring={<MiniDonut label="Accounts" parts={accountParts}/>}
          details={<DetailList rows={accountParts}/>}>
          {users.total === 1 ? 'account' : 'accounts'}
        </Tile>
        <Tile icon={Search} label={`Searches · ${kpiDays} days`} value={last.total.toLocaleString()}
          visual={<Sparkline values={weekTotals} labels={week.map(d => shortDay(d.date))} label={`Searches per day, last ${kpiDays} days`}/>}
          details={<DetailList rows={[
            { key: 'busiest', label: busiest ? `Busiest · ${shortDay(busiest.date)}` : 'Busiest day', value: busiest ? busiest.total : 0 },
            { key: 'avg', label: 'Daily average', value: Math.round((last.total / kpiDays) * 10) / 10 },
          ]}/>}>
          <Delta now={last.total} before={prev.total} days={kpiDays}/>
        </Tile>
        <Tile icon={CheckCircle2} label={`Success rate · ${kpiDays} days`} value={successRate == null ? '—' : `${successRate}%`}
          ring={<MiniDonut label="Searches" parts={successParts}/>}
          details={<DetailList rows={successParts}/>}>
          of {last.total.toLocaleString()} {last.total === 1 ? 'search' : 'searches'}
        </Tile>
        <Tile icon={UserCheck} label={`Active users · ${kpiDays} days`} value={last.active_users.toLocaleString()}
          ring={<MiniDonut label="Active accounts" parts={activityParts}/>}
          details={<DetailList rows={activityParts.map(p => (p.track ? { ...p, color: null } : p))}/>}>
          of {activeAccounts} active {activeAccounts === 1 ? 'account' : 'accounts'}
        </Tile>
      </div>
      </Section>

      <Section id="ov-attention-title" title="Needs attention">
        <div className={`admin-card ov-attention ${attention ? '' : 'is-clear'}`}>
          <div className="ov-attention-head">
            {attention ? (
              <ul className="ov-attention-list">
                {idle.count > 0 && (
                  <li>
                    <strong>{idle.count}</strong> active {idle.count === 1 ? 'account has' : 'accounts have'} no searches in {trendDays} days
                    <span className="ov-chips">
                      {idle.sample.map(u => <span key={u.id} className="ov-chip">{u.full_name || u.username}</span>)}
                      {idle.count > idle.sample.length && <span className="ov-chip is-more">+{idle.count - idle.sample.length} more</span>}
                    </span>
                  </li>
                )}
                {users.inactive > 0 && <li><strong>{users.inactive}</strong> inactive {users.inactive === 1 ? 'account' : 'accounts'} (login blocked). Delete if no longer needed.</li>}
              </ul>
            ) : <p>Every active account has searched in the last {trendDays} days.</p>}
            {attention && <button type="button" className="outline-button" onClick={onManageUsers}>Manage access</button>}
          </div>
        </div>
      </Section>

      <Section id="ov-trend-title" title="Search activity">
      <div className="ov-split">
        <section className="admin-card ov-card" aria-labelledby="ov-activity-title">
          <div className="ov-card-head">
            <div>
              <h2 id="ov-activity-title">Searches per day</h2>
              <p>{trendTotal.toLocaleString()} {trendTotal === 1 ? 'search' : 'searches'} in the last {trendDays} days, by outcome.</p>
            </div>
          </div>
          {trendTotal ? <ActivityChart daily={data.daily}/> : <div className="table-empty">No searches in the last {trendDays} days.</div>}
        </section>
        <StatsDonut stats={outcome30} title={`Outcomes · ${trendDays} days`} compact/>
      </div>
      </Section>

      <Section id="ov-people-title" title="Users and failed searches">
      <div className="ov-pair">
        <section className="admin-card ov-card" aria-labelledby="ov-top-title">
          <div className="ov-card-head">
            <div><h2 id="ov-top-title">Most active users</h2><p>Searches in the last {trendDays} days.</p></div>
          </div>
          <BarList
            unit="searches"
            emptyText={`No searches in the last ${trendDays} days.`}
            items={data.top_users.map(u => ({
              key: u.id, label: u.full_name || u.username, sub: `@${u.username}`, value: u.searches,
              lead: <span className="avatar user-avatar" aria-hidden="true">{initials(u)}</span>,
            }))}
          />
        </section>

        <section className="admin-card ov-card" aria-labelledby="ov-errors-title">
          <div className="ov-card-head">
            <div><h2 id="ov-errors-title">Failed searches</h2><p>Most common reasons, then the latest failed searches.</p></div>
          </div>
          {data.error_causes.length > 0 && (
            <BarList
              unit="failed searches"
              color="var(--viz-error)"
              items={data.error_causes.map(c => ({ key: c.code, label: c.label, value: c.count }))}
            />
          )}
          {data.recent_errors.length ? (
            <>
              <h3 className="ov-subhead">Latest failed searches</h3>
              <ul className="ov-list" id="ov-failures">
                {(allFailures ? data.recent_errors : data.recent_errors.slice(0, FAILURES_SHOWN)).map(e => (
                  <li key={e.id}>
                    <span className="ov-list-text">
                      <strong>{e.query}</strong>
                      <small>{e.label} · {e.username ? `@${e.username}` : 'no owner'} · {ago(e.created_at)}</small>
                    </span>
                    <span className="ref-id">#{e.id}</span>
                  </li>
                ))}
              </ul>
              {data.recent_errors.length > FAILURES_SHOWN && (
                <div className="ov-more">
                  <span>Showing {allFailures ? data.recent_errors.length : FAILURES_SHOWN} of {data.recent_errors.length}</span>
                  <button type="button" className="outline-button" aria-controls="ov-failures" aria-expanded={allFailures}
                    onClick={() => setAllFailures(v => !v)}>
                    {allFailures ? <>Show less <ChevronUp size={16}/></> : <>Show more <ChevronDown size={16}/></>}
                  </button>
                </div>
              )}
            </>
          ) : <div className="table-empty">No failed searches.</div>}
        </section>
      </div>
      </Section>
    </div>
  );
}
