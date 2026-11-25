import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface ModalProps {
  className: string;
  labelledBy: string;
  describedBy?: string;
  role?: 'dialog' | 'alertdialog';
  /** Esc, backdrop click (if allowed) or a close button. The parent unmounts the modal. */
  onClose: () => void;
  /** While true (e.g. a request is running) the modal can't be dismissed. */
  locked?: boolean;
  closeOnBackdrop?: boolean;
  children: ReactNode;
}

/**
 * One modal for the whole app, built on the native <dialog> + showModal():
 * the browser gives focus trapping, Esc handling, an inert page behind it and
 * correct stacking for free. Portalled to <body> so no parent can clip it.
 */
export function Modal({
  className,
  labelledBy,
  describedBy,
  role,
  onClose,
  locked = false,
  closeOnBackdrop = false,
  children,
}: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const pressedBackdrop = useRef(false);

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return createPortal(
    // The dialog element itself is the backdrop hit area; keyboard users close with Esc.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={ref}
      className={className}
      role={role}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onCancel={event => {
        event.preventDefault(); // we decide, so `locked` is respected
        if (!locked) onClose();
      }}
      // Close only if the press STARTED on the backdrop, so selecting text and releasing outside doesn't close.
      onPointerDown={event => {
        pressedBackdrop.current = event.target === ref.current;
      }}
      onClick={event => {
        if (closeOnBackdrop && !locked && pressedBackdrop.current && event.target === ref.current) onClose();
      }}
    >
      {children}
    </dialog>,
    document.body,
  );
}
