import type { ReactNode } from 'react';

/** Small shared states: every async screen needs loading, error and success UI. */

export function Spinner({ label }: { label: string }) {
  return <span className="spinner" role="status" aria-label={label} />;
}

export function FullPageSpinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <Spinner label={label} />
    </div>
  );
}

export function ErrorAlert({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div className="alert alert-danger" role="alert">
      {children}
    </div>
  );
}

export function SuccessAlert({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <div className="alert alert-success" role="status">
      {children}
    </div>
  );
}
