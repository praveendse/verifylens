import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronRight, ChevronUp, Database, RefreshCw, Search, Trash2, X } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog.jsx';
import ResultView, { StatusBadge } from './ResultView.jsx';
import StatsDonut from './StatsDonut.jsx';

const TOPIC_DEBOUNCE_MS = 300;

/* Rows are paged and filtered on the server (see App.jsx): the table shows
   the loaded pages, "Show more" fetches the next older page. */
export default function HistoryPage({ records, stats, hasMore, moreBusy, onLoadMore, onShowLess, pageSize, filter, onFilterChange, loading, error, onRefresh, onDeleteRecord, onOpen, selected, detailBusy, detailError, clearSelected, isDemo }) {
  const [query, setQuery] = useState(filter.q);
  const openerRef = useRef(null); // row button that opened the popup, gets focus back on close
  const panelRef = useRef(null);
  const [pendingDelete, setPendingDelete] = useState(null); // record awaiting confirmation
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  function askDelete(record) { setDeleteError(''); setPendingDelete(record); }

  async function confirmDelete() {
    setDeleteBusy(true); setDeleteError('');
    const problem = await onDeleteRecord(pendingDelete.id);
    setDeleteBusy(false);
    if (problem) { setDeleteError(problem); return; }
    setPendingDelete(null);
    // The row that opened the popup no longer exists; keep focus on the table.
    panelRef.current?.focus({ preventScroll: true });
  }

  function showLess() {
    onShowLess();
    // The page just got much shorter; bring the table's top back into view.
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // Wait until typing pauses before asking the server, instead of one request per key.
  useEffect(() => {
    if (query === filter.q) return undefined;
    const timer = setTimeout(() => onFilterChange(f => ({ ...f, q: query })), TOPIC_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, filter.q, onFilterChange]);

  const filtering = Boolean(filter.q.trim() || filter.status);
  const showing = filtering || !stats ? `Showing ${records.length}` : `Showing ${records.length} of ${stats.total}`;

  return <div className="page-container">
    <div className="page-top-heading"><div><h1>Search <span>history.</span></h1><p>Review previous verification attempts, statuses and saved reports.</p></div><button onClick={onRefresh} className="outline-button" disabled={loading}><RefreshCw size={16} className={loading ? 'spin' : ''}/> Refresh</button></div>
    <StatsDonut stats={stats} />
    <div className="history-panel" ref={panelRef} tabIndex={-1}><div className="history-panel-top"><div><h2>Verification log</h2><p>Every request is recorded, including unsuccessful attempts.</p></div><div className="history-tools"><div className="history-search"><Search size={16}/><input placeholder="Filter by topic" aria-label="Filter history by topic" value={query} onChange={e => setQuery(e.target.value)}/></div><select aria-label="Filter by status" value={filter.status} onChange={e => { const status = e.target.value; onFilterChange(f => ({ ...f, status })); }}><option value="">All statuses</option><option value="SUCCESS">Successful</option><option value="ERROR">Failed</option><option value="PENDING">Pending</option></select></div></div>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {loading && !records.length ? <div className="table-empty">Loading history…</div> : !records.length ? <div className="table-empty"><Database size={25}/>{filtering ? <><strong>No matching searches</strong><p>Try a different topic or status.</p></> : <><strong>No searches yet</strong><p>Your verifications will appear here.</p></>}</div> : <div className={`history-table-wrap ${loading ? 'is-refreshing' : ''}`} aria-busy={loading}><table className="history-table"><thead><tr><th>ARTICLE / QUERY</th><th>STATUS</th><th>CREATED</th><th>REFERENCE</th><th/></tr></thead><tbody>{records.map(item => <tr key={item.id}><td><strong>{item.article_title || item.query}</strong><small>{item.article_title && item.article_title !== item.query ? item.query : 'Wikipedia search'}</small></td><td><StatusBadge status={item.status} matches={item.matches} compact /></td><td>{item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td><td><span className="ref-id">#{item.id}</span></td><td><button className="row-open" aria-label={`Open record ${item.id}`} title="Open record" onClick={e => { openerRef.current = e.currentTarget; onOpen(item.id); }}><ChevronRight size={17}/></button></td></tr>)}</tbody></table></div>}
      {records.length > 0 && (
        <div className="history-more">
          <span>{showing}</span>
          <div className="history-more-actions">
            {records.length > pageSize && <button type="button" className="outline-button" onClick={showLess} disabled={loading}>Show less <ChevronUp size={16}/></button>}
            {hasMore && <button type="button" className="outline-button" onClick={onLoadMore} disabled={moreBusy || loading}>{moreBusy ? 'Loading…' : <>Show more <ChevronDown size={16}/></>}</button>}
          </div>
        </div>
      )}
    </div>
    {(selected || detailBusy || detailError) && <RecordDialog selected={selected} busy={detailBusy} error={detailError} isDemo={isDemo} onDelete={askDelete} onClose={() => { clearSelected(); openerRef.current?.focus(); }} />}
    {/* Rendered here, not inside RecordDialog, so its events never reach the popup's close handlers. */}
    {pendingDelete && (
      <ConfirmDialog title="Delete this search?" busy={deleteBusy} error={deleteError} confirmLabel="Delete search" onConfirm={confirmDelete} onCancel={() => setPendingDelete(null)}>
        <p><strong>{pendingDelete.article_title || pendingDelete.query}</strong> (#{pendingDelete.id}) and its report will be permanently removed.</p>
        <p>This can&rsquo;t be undone.</p>
      </ConfirmDialog>
    )}
  </div>;
}

/* Saved record in a modal popup. Native <dialog> + showModal() gives the focus
   trap, Esc-to-close and an inert page behind it. Portalled to <body> so it sits
   above the sidebar and top bar. Closes via ✕, Esc or a click on the backdrop. */
function RecordDialog({ selected, busy, error, isDemo, onDelete, onClose }) {
  const ref = useRef(null);
  const downOnBackdrop = useRef(false);
  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return createPortal(
    <dialog
      ref={ref}
      className="record-dialog"
      aria-labelledby="record-dialog-title"
      onClose={onClose}
      // Backdrop click closes, but only if the press also started on the backdrop,
      // so selecting report text and releasing outside doesn't close it.
      onPointerDown={e => { downOnBackdrop.current = e.target === ref.current; }}
      onClick={e => { if (e.target === ref.current && downOnBackdrop.current) ref.current.close(); }}
    >
      <div className="record-dialog-bar">
        <div>
          <span className="overline">SAVED RECORD{selected?.id != null ? ` · #${selected.id}` : ''}</span>
          <h2 id="record-dialog-title">{selected?.article_title || selected?.query || 'Search details'}</h2>
        </div>
        <div className="record-dialog-actions">
          {selected && !busy && <button type="button" className="danger-outline-button" onClick={() => onDelete(selected)}><Trash2 size={16}/> Delete</button>}
          <button type="button" className="icon-button" aria-label="Close" onClick={() => ref.current?.close()}><X size={20}/></button>
        </div>
      </div>
      <div className="record-dialog-body">
        {busy && <div className="progress-panel" role="status"><span className="spinner"/> Loading the saved report…</div>}
        {error && <div className="alert alert-danger" role="alert">{error}</div>}
        {selected && !busy && <ResultView result={selected} isDemo={isDemo}/>}
      </div>
    </dialog>,
    document.body,
  );
}
