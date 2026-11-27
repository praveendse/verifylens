import { Trash2, X } from 'lucide-react';
import { useId, useState } from 'react';
import type { HistoryDetail } from '@/api/types';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { ErrorAlert } from '@/components/Feedback';
import { Modal } from '@/components/Modal';
import { ResultView } from '@/features/verify/ResultView';
import { errorText } from '@/lib/format';
import { useDeleteHistory, useHistoryDetail } from './queries';

/** Saved record in a modal, driven by the URL (/history/:recordId). */
export function RecordDialog({ recordId, onClose }: { recordId: number; onClose: () => void }) {
  const detail = useHistoryDetail(recordId);
  const remove = useDeleteHistory();
  const [confirming, setConfirming] = useState(false);
  const titleId = useId();
  const record: HistoryDetail | undefined = detail.data;

  function confirmDelete() {
    remove.mutate(recordId, {
      onSuccess: () => {
        setConfirming(false);
        onClose(); // the record is gone: back to the list
      },
    });
  }

  return (
    <>
      <Modal
        className="record-dialog"
        labelledBy={titleId}
        onClose={onClose}
        closeOnBackdrop
        locked={confirming}
      >
        <div className="record-dialog-bar">
          <div>
            <span className="overline">SAVED RECORD · #{recordId}</span>
            <h2 id={titleId}>{record?.article_title || record?.query || 'Search details'}</h2>
          </div>
          <div className="record-dialog-actions">
            {record && (
              <button
                type="button"
                className="danger-outline-button"
                onClick={() => {
                  remove.reset();
                  setConfirming(true);
                }}
              >
                <Trash2 size={16} aria-hidden="true" /> Delete
              </button>
            )}
            <button type="button" className="icon-button" aria-label="Close" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
        </div>
        <div className="record-dialog-body">
          {detail.isPending && (
            <div className="progress-panel" role="status">
              <span className="spinner" aria-hidden="true" /> Loading the saved report…
            </div>
          )}
          <ErrorAlert>{detail.error && errorText(detail.error)}</ErrorAlert>
          {record && <ResultView result={{ ...record, review_reason: null }} />}
        </div>
      </Modal>
      {confirming && record && (
        <ConfirmDialog
          title="Delete this search?"
          confirmLabel="Delete search"
          busy={remove.isPending}
          error={remove.error ? errorText(remove.error) : ''}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          <p>
            <strong>{record.article_title || record.query}</strong> (#{record.id}) and its report will be
            permanently removed.
          </p>
          <p>This can&rsquo;t be undone.</p>
        </ConfirmDialog>
      )}
    </>
  );
}
