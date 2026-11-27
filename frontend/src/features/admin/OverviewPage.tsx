import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Search,
  UserCheck,
  Users2,
  type LucideIcon,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import type { AdminOverview } from '@/api/types';
import { paths } from '@/app/paths';
import { ErrorAlert } from '@/components/Feedback';
import { PageHeading } from '@/components/PageHeading';
import { StatsDonut } from '@/components/StatsDonut';
import { displayName, errorText, initials, plural, timeAgo } from '@/lib/format';
import { ActivityChart } from './ActivityChart';
import { BarList, DetailList, MiniDonut, Sparkline, type Part } from './OverviewVisuals';
import { useAdminOverview } from './queries';
import '@/styles/admin-overview.css';

const FAILURES_SHOWN = 3;
const pct = (n: number, d: number) => (d ? Math.round((n / d) * 100) : null);
const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' });

function Delta({ now, before, days }: { now: number; before: number; days: number }) {
  if (!before)
    return (
      <span className="ov-delta">
        {now ? `None in the previous ${days} days` : `None in the previous ${days} days either`}
      </span>
    );
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return <span className="ov-delta">Same as the previous {days} days</span>;
  const up = change > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`ov-delta ${up ? 'is-up' : 'is-down'}`}>
      <Icon size={14} aria-hidden="true" />
      {up ? '+' : '−'}
      {Math.abs(change)}% vs previous {days} days
    </span>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className="ov-section" aria-labelledby={id}>
      <header className="ov-section-head">
        <h2 id={id}>{title}</h2>
      </header>
      {children}
    </section>
  );
}

interface TileProps {
  icon: LucideIcon;
  label: string;
  value: string;
  ring?: ReactNode;
  visual?: ReactNode;
  details?: ReactNode;
  children?: ReactNode;
}

function Tile({ icon: Icon, label, value, ring, visual, details, children }: TileProps) {
  return (
    <div className={`ov-tile${ring ? ' has-ring' : ''}`}>
      <span className="ov-tile-label">
        <Icon size={15} aria-hidden="true" />
        {label}
      </span>
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

/** Route /admin (lazy-loaded: only admins download this code). */
export function OverviewPage() {
  const overview = useAdminOverview();
  const refreshing = overview.isFetching;
  const heading = (
    <PageHeading
      title="Admin"
      accent="overview."
      description="How the platform is being used, and what needs your attention."
      actions={
        <button
          type="button"
          className="outline-button"
          onClick={() => overview.refetch()}
          disabled={refreshing}
        >
          <RefreshCw size={16} className={refreshing ? 'spin' : ''} aria-hidden="true" /> Refresh
        </button>
      }
    />
  );

  if (!overview.data) {
    return (
      <div className="page-container">
        {heading}
        {overview.error ? (
          <ErrorAlert>{errorText(overview.error)}</ErrorAlert>
        ) : (
          <div className="admin-card table-empty">Loading overview…</div>
        )}
      </div>
    );
  }

  return (
    <div className={`page-container ov ${refreshing ? 'is-refreshing' : ''}`} aria-busy={refreshing}>
      {heading}
      <p className="ov-updated">Updated {timeAgo(overview.data.generated_at)} · days are counted in UTC</p>
      <ErrorAlert>{overview.error && errorText(overview.error)}</ErrorAlert>
      <OverviewBody data={overview.data} />
    </div>
  );
}

/** Pure presentation of the numbers: easy to test with a fixture, no fetching. */
export function OverviewBody({ data }: { data: AdminOverview }) {
  const [allFailures, setAllFailures] = useState(false);
  const { users, last_period: last, previous_period: prev, kpi_days: kpiDays, trend_days: trendDays } = data;
  const completed = last.match + last.no_match;
  const successRate = pct(completed, last.total);
  const activeAccounts = users.total - users.inactive;
  const idle = data.idle_users;
  const attention = idle.count > 0 || users.inactive > 0;

  const outcome30 = data.daily.reduce(
    (acc, d) => ({
      match: acc.match + d.match,
      no_match: acc.no_match + d.no_match,
      error: acc.error + d.error,
      other: acc.other + d.other,
    }),
    { match: 0, no_match: 0, error: 0, other: 0 },
  );
  const outcomeStats = { ...outcome30, completed: outcome30.match + outcome30.no_match };
  const trendTotal = outcome30.match + outcome30.no_match + outcome30.error + outcome30.other;

  const week = data.daily.slice(-kpiDays);
  const weekTotals = week.map(d => d.match + d.no_match + d.error + d.other);
  const busiest = weekTotals.some(Boolean)
    ? week
        .map((d, i) => ({ date: d.date, total: weekTotals[i] ?? 0 }))
        .reduce((a, b) => (b.total > a.total ? b : a))
    : null;

  const accountParts: Part[] = [
    { key: 'user', label: 'Users', value: users.active_users, color: 'var(--viz-role-user)' },
    { key: 'admin', label: 'Admins', value: users.active_admins, color: 'var(--viz-role-admin)' },
    { key: 'inactive', label: 'Inactive', value: users.inactive, color: 'var(--viz-inactive)' },
  ];
  const successParts: Part[] = [
    {
      key: 'done',
      label: 'Completed',
      value: completed,
      color: 'var(--viz-match)',
      note: completed ? `${last.match} match · ${last.no_match} no match` : undefined,
    },
    { key: 'error', label: 'Failed', value: last.error, color: 'var(--viz-error)' },
    ...(last.other
      ? [{ key: 'other', label: 'Not finished', value: last.other, color: 'var(--viz-other)' }]
      : []),
  ];
  const activityParts: Part[] = [
    { key: 'searched', label: 'Searched', value: last.active_users, color: 'var(--viz-series)' },
    {
      key: 'quiet',
      label: "Didn't search",
      value: Math.max(0, activeAccounts - last.active_users),
      track: true,
    },
  ];
  const failures = allFailures ? data.recent_errors : data.recent_errors.slice(0, FAILURES_SHOWN);

  return (
    <>
      <Section id="ov-glance-title" title="At a glance">
        <div className="ov-tiles">
          <Tile
            icon={Users2}
            label="Team members"
            value={users.total.toLocaleString()}
            ring={<MiniDonut label="Accounts" parts={accountParts} />}
            details={<DetailList rows={accountParts} />}
          >
            {plural(users.total, 'account', 'accounts')}
          </Tile>
          <Tile
            icon={Search}
            label={`Searches · ${kpiDays} days`}
            value={last.total.toLocaleString()}
            visual={
              <Sparkline
                values={weekTotals}
                labels={week.map(d => shortDay(d.date))}
                label={`Searches per day, last ${kpiDays} days`}
              />
            }
            details={
              <DetailList
                rows={[
                  {
                    key: 'busiest',
                    label: busiest ? `Busiest · ${shortDay(busiest.date)}` : 'Busiest day',
                    value: busiest ? busiest.total : 0,
                  },
                  { key: 'avg', label: 'Daily average', value: Math.round((last.total / kpiDays) * 10) / 10 },
                ]}
              />
            }
          >
            <Delta now={last.total} before={prev.total} days={kpiDays} />
          </Tile>
          <Tile
            icon={CheckCircle2}
            label={`Success rate · ${kpiDays} days`}
            value={successRate == null ? '—' : `${successRate}%`}
            ring={<MiniDonut label="Searches" parts={successParts} />}
            details={<DetailList rows={successParts} />}
          >
            of {last.total.toLocaleString()} {plural(last.total, 'search', 'searches')}
          </Tile>
          <Tile
            icon={UserCheck}
            label={`Active users · ${kpiDays} days`}
            value={last.active_users.toLocaleString()}
            ring={<MiniDonut label="Active accounts" parts={activityParts} />}
            details={<DetailList rows={activityParts.map(p => (p.track ? { ...p, color: null } : p))} />}
          >
            of {activeAccounts} active {plural(activeAccounts, 'account', 'accounts')}
          </Tile>
        </div>
      </Section>

      <Section id="ov-attention-title" title="Needs attention">
        <div className="admin-card ov-attention">
          <div className="ov-attention-head">
            {attention ? (
              <ul className="ov-attention-list">
                {idle.count > 0 && (
                  <li>
                    <strong>{idle.count}</strong> active {plural(idle.count, 'account has', 'accounts have')}{' '}
                    no searches in {trendDays} days
                    <span className="ov-chips">
                      {idle.sample.map(u => (
                        <span key={u.id} className="ov-chip">
                          {displayName(u)}
                        </span>
                      ))}
                      {idle.count > idle.sample.length && (
                        <span className="ov-chip is-more">+{idle.count - idle.sample.length} more</span>
                      )}
                    </span>
                  </li>
                )}
                {users.inactive > 0 && (
                  <li>
                    <strong>{users.inactive}</strong> inactive {plural(users.inactive, 'account', 'accounts')}{' '}
                    (login blocked). Delete if no longer needed.
                  </li>
                )}
              </ul>
            ) : (
              <p>Every active account has searched in the last {trendDays} days.</p>
            )}
            {attention && (
              <Link className="outline-button" to={paths.users}>
                Manage access
              </Link>
            )}
          </div>
        </div>
      </Section>

      <Section id="ov-trend-title" title="Search activity">
        <div className="ov-split">
          <section className="admin-card ov-card" aria-labelledby="ov-activity-title">
            <div className="ov-card-head">
              <div>
                <h3 id="ov-activity-title">Searches per day</h3>
                <p>
                  {trendTotal.toLocaleString()} {plural(trendTotal, 'search', 'searches')} in the last{' '}
                  {trendDays} days, by outcome.
                </p>
              </div>
            </div>
            {trendTotal ? (
              <ActivityChart daily={data.daily} />
            ) : (
              <div className="table-empty">No searches in the last {trendDays} days.</div>
            )}
          </section>
          <StatsDonut stats={outcomeStats} title={`Outcomes · ${trendDays} days`} compact />
        </div>
      </Section>

      <Section id="ov-people-title" title="Users and failed searches">
        <div className="ov-pair">
          <section className="admin-card ov-card" aria-labelledby="ov-top-title">
            <div className="ov-card-head">
              <div>
                <h3 id="ov-top-title">Most active users</h3>
                <p>Searches in the last {trendDays} days.</p>
              </div>
            </div>
            <BarList
              unit="searches"
              emptyText={`No searches in the last ${trendDays} days.`}
              items={data.top_users.map(u => ({
                key: u.id,
                label: displayName(u),
                sub: `@${u.username}`,
                value: u.searches,
                lead: (
                  <span className="avatar user-avatar" aria-hidden="true">
                    {initials(displayName(u))}
                  </span>
                ),
              }))}
            />
          </section>

          <section className="admin-card ov-card" aria-labelledby="ov-errors-title">
            <div className="ov-card-head">
              <div>
                <h3 id="ov-errors-title">Failed searches</h3>
                <p>Most common reasons, then the latest failed searches.</p>
              </div>
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
                <h4 className="ov-subhead">Latest failed searches</h4>
                <ul className="ov-list" id="ov-failures">
                  {failures.map(e => (
                    <li key={e.id}>
                      <span className="ov-list-text">
                        <strong>{e.query}</strong>
                        <small>
                          {e.label} · {e.username ? `@${e.username}` : 'no owner'} · {timeAgo(e.created_at)}
                        </small>
                      </span>
                      <span className="ref-id">#{e.id}</span>
                    </li>
                  ))}
                </ul>
                {data.recent_errors.length > FAILURES_SHOWN && (
                  <div className="ov-more">
                    <span>
                      Showing {failures.length} of {data.recent_errors.length}
                    </span>
                    <button
                      type="button"
                      className="outline-button"
                      aria-controls="ov-failures"
                      aria-expanded={allFailures}
                      onClick={() => setAllFailures(v => !v)}
                    >
                      {allFailures ? (
                        <>
                          Show less <ChevronUp size={16} aria-hidden="true" />
                        </>
                      ) : (
                        <>
                          Show more <ChevronDown size={16} aria-hidden="true" />
                        </>
                      )}
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div className="table-empty">No failed searches.</div>
            )}
          </section>
        </div>
      </Section>
    </>
  );
}
