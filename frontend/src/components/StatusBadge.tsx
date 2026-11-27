import { CheckCircle2, XCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  matches: boolean | null | undefined;
  compact?: boolean;
}

/** Outcome pill. Icon + text, so meaning never depends on colour alone. */
export function StatusBadge({ status, matches, compact = false }: StatusBadgeProps) {
  const size = compact ? ' status-compact' : '';
  if (status === 'ERROR')
    return (
      <span className={`status-badge status-error${size}`}>
        <XCircle size={13} aria-hidden="true" /> Failed
      </span>
    );
  if (status === 'PENDING') return <span className={`status-badge status-pending${size}`}>Processing</span>;
  if (status === 'SUCCESS' && matches === false)
    return (
      <span className={`status-badge status-error${size}`}>
        <XCircle size={13} aria-hidden="true" /> No match
      </span>
    );
  if (status === 'SUCCESS' && matches === true)
    return (
      <span className={`status-badge status-success${size}`}>
        <CheckCircle2 size={13} aria-hidden="true" /> Match verified
      </span>
    );
  return <span className={`status-badge status-pending${size}`}>{status || 'Unknown'}</span>;
}
