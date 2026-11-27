import { ChevronDown, ChevronRight, ChevronUp, Database, RefreshCw, Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import type { HistoryFilter, HistoryStatusFilter } from '@/api/types';
import { HISTORY_PAGE_SIZE } from '@/api/endpoints';
import { paths } from '@/app/paths';
import { ErrorAlert } from '@/components/Feedback';
import { PageHeading } from '@/components/PageHeading';
import { Select, type SelectOption } from '@/components/Select';
import { StatsDonut } from '@/components/StatsDonut';
import { StatusBadge } from '@/components/StatusBadge';
import { errorText, formatDateTime } from '@/lib/format';
import { useDebouncedValue } from '@/lib/useDebouncedValue';
import { useCollapseHistory, useHistoryList, useHistoryStats } from './queries';
import { RecordDialog } from './RecordDialog';

const STATUS_OPTIONS: ReadonlyArray<SelectOption<HistoryStatusFilter>> = [
  { value: '', label: 'All statuses' },
  { value: 'SUCCESS', label: 'Successful' },
  { value: 'ERROR', label: 'Failed' },
  { value: 'PENDING', label: 'Pending' },
];
const isStatus = (v: string | null): v is HistoryStatusFilter => STATUS_OPTIONS.some(o => o.value === v);

/**
 * Route /history and /history/:recordId.
 * The URL is the state: filters live in ?q=&status=, the open record in the
 * path. So refresh, back/forward and shared links all restore the same view.
 */
export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const { recordId } = useParams();
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement>(null);

  const status = isStatus(params.get('status')) ? (params.get('status') as HistoryStatusFilter) : '';
  const [query, setQuery] = useState(params.get('q') ?? '');
  const debouncedQuery = useDebouncedValue(query, 300);
  const filter: HistoryFilter = useMemo(
    () => ({ q: debouncedQuery.trim(), status }),
    [debouncedQuery, status],
  );

  // Mirror the debounced text into the URL (replace: typing shouldn't flood history).
  useEffect(() => {
    setParams(
      prev => {
        const next = new URLSearchParams(prev);
        if (filter.q) next.set('q', filter.q);
        else next.delete('q');
        return next;
      },
      { replace: true },
    );
  }, [filter.q, setParams]);

  const list = useHistoryList(filter);
  const stats = useHistoryStats();
  const collapse = useCollapseHistory();
  const records = list.data?.pages.flatMap(p => p.items) ?? [];
  const filtering = Boolean(filter.q || filter.status);
  const total = stats.data?.total;
  const showing =
    filtering || total == null ? `Showing ${records.length}` : `Showing ${records.length} of ${total}`;
  const openId = recordId ? Number(recordId) : null;
  const error = list.error ?? stats.error;

  function setStatus(value: HistoryStatusFilter) {
    setParams(prev => {
      const next = new URLSearchParams(prev);
      if (value) next.set('status', value);
      else next.delete('status');
      return next;
    });
  }

  function showLess() {
    collapse(filter);
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const refresh = () => Promise.all([list.refetch(), stats.refetch()]);
  const refreshing = list.isFetching && !list.isFetchingNextPage;

  return (
    <div className="page-container">
      <PageHeading
        title="Search"
        accent="history."
        description="Review previous verification attempts, statuses and saved reports."
        actions={
          <button type="button" onClick={refresh} className="outline-button" disabled={refreshing}>
            <RefreshCw size={16} className={refreshing ? 'spin' : ''} aria-hidden="true" /> Refresh
          </button>
        }
      />
      <StatsDonut stats={stats.data} />
      <div className="history-panel" ref={panelRef} tabIndex={-1}>
        <div className="history-panel-top">
          <div>
            <h2>Verification log</h2>
            <p>Every request is recorded, including unsuccessful attempts.</p>
          </div>
          <div className="history-tools">
            <div className="history-search">
              <Search size={16} aria-hidden="true" />
              <input
                placeholder="Filter by topic"
                aria-label="Filter history by topic"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            <Select
              aria-label="Filter by status"
              value={status}
              onChange={setStatus}
              options={STATUS_OPTIONS}
            />
          </div>
        </div>

        <ErrorAlert>{error && errorText(error)}</ErrorAlert>

        {list.isPending ? (
          <div className="table-empty">Loading history…</div>
        ) : !records.length ? (
          <div className="table-empty">
            <Database size={25} aria-hidden="true" />
            {filtering ? (
              <>
                <strong>No matching searches</strong>
                <p>Try a different topic or status.</p>
              </>
            ) : (
              <>
                <strong>No searches yet</strong>
                <p>Your verifications will appear here.</p>
              </>
            )}
          </div>
        ) : (
          <div
            className={`history-table-wrap ${list.isPlaceholderData ? 'is-refreshing' : ''}`}
            aria-busy={list.isFetching}
          >
            <table className="history-table">
              <thead>
                <tr>
                  <th scope="col">ARTICLE / QUERY</th>
                  <th scope="col">STATUS</th>
                  <th scope="col">CREATED</th>
                  <th scope="col">REFERENCE</th>
                  <th scope="col">
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {records.map(item => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.article_title || item.query}</strong>
                      <small>
                        {item.article_title && item.article_title !== item.query
                          ? item.query
                          : 'Wikipedia search'}
                      </small>
                    </td>
                    <td>
                      <StatusBadge status={item.status} matches={item.matches} compact />
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>
                      <span className="ref-id">#{item.id}</span>
                    </td>
                    <td>
                      {/* A link, not a button: it changes the URL, so it can be opened in a new tab. */}
                      <Link
                        className="row-open"
                        to={{ pathname: paths.historyRecord(item.id), search: params.toString() }}
                        aria-label={`Open record ${item.id}`}
                        title="Open record"
                      >
                        <ChevronRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {records.length > 0 && (
          <div className="history-more">
            <span>{showing}</span>
            <div className="history-more-actions">
              {records.length > HISTORY_PAGE_SIZE && (
                <button
                  type="button"
                  className="outline-button"
                  onClick={showLess}
                  disabled={list.isFetching}
                >
                  Show less <ChevronUp size={16} aria-hidden="true" />
                </button>
              )}
              {list.hasNextPage && (
                <button
                  type="button"
                  className="outline-button"
                  onClick={() => list.fetchNextPage()}
                  disabled={list.isFetching}
                >
                  {list.isFetchingNextPage ? (
                    'Loading…'
                  ) : (
                    <>
                      Show more <ChevronDown size={16} aria-hidden="true" />
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {openId != null && Number.isInteger(openId) && (
        <RecordDialog
          key={openId}
          recordId={openId}
          onClose={() => navigate({ pathname: paths.history, search: params.toString() })}
        />
      )}
    </div>
  );
}
