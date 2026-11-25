import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AlertTriangle } from 'lucide-react';
import './confirm-dialog.css';

/**
 * Confirmation for destructive actions. Native <dialog> + showModal() gives the
 * focus trap, Esc and an inert page. Focus starts on Cancel, so pressing Enter
 * by reflex never deletes. While busy it can't be dismissed, so the user sees
 * the result; on failure the error shows inside and they can retry or cancel.
 * It stacks above other dialogs (e.g. the saved-record popup) because each
 * showModal() call goes on top.
 */
export default function ConfirmDialog({ title, children, confirmLabel = 'Delete', busy = false, error = '', onConfirm, onCancel }) {
  const ref = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
    cancelRef.current?.focus();
  }, []);

  return createPortal(
    <dialog
      ref={ref}
      className="confirm-dialog"
      role="alertdialog"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-body"
      onCancel={e => { e.preventDefault(); if (!busy) onCancel(); }} // Esc
    >
      <div className="confirm-icon" aria-hidden="true"><AlertTriangle size={20} /></div>
      <h2 id="confirm-title">{title}</h2>
      <div id="confirm-body" className="confirm-body">{children}</div>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      <div className="confirm-actions">
        <button ref={cancelRef} type="button" className="outline-button" onClick={onCancel} disabled={busy}>Cancel</button>
        <button type="button" className="danger-button" onClick={onConfirm} disabled={busy}>{busy ? 'Deleting…' : confirmLabel}</button>
      </div>
    </dialog>,
    document.body,
  );
}
