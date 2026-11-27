import { AlertTriangle } from 'lucide-react';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Modal } from './Modal';
import '@/styles/confirm-dialog.css';

interface ConfirmDialogProps {
  title: string;
  children: ReactNode;
  confirmLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  error?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Confirmation for destructive actions. Focus starts on Cancel, so pressing
 * Enter by reflex never deletes. While busy it can't be dismissed; a failure
 * shows inside so the user can retry or cancel.
 */
export function ConfirmDialog({
  title,
  children,
  confirmLabel = 'Delete',
  busyLabel = 'Deleting…',
  busy = false,
  error = '',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId(); // unique ids: safe even if two dialogs are mounted
  const bodyId = useId();

  useEffect(() => cancelRef.current?.focus(), []);

  return (
    <Modal
      className="confirm-dialog"
      role="alertdialog"
      labelledBy={titleId}
      describedBy={bodyId}
      onClose={onCancel}
      locked={busy}
    >
      <div className="confirm-icon" aria-hidden="true">
        <AlertTriangle size={20} />
      </div>
      <h2 id={titleId}>{title}</h2>
      <div id={bodyId} className="confirm-body">
        {children}
      </div>
      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}
      <div className="confirm-actions">
        <button ref={cancelRef} type="button" className="outline-button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="danger-button" onClick={onConfirm} disabled={busy}>
          {busy ? busyLabel : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
