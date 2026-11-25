import { AlertTriangle } from 'lucide-react';
import { isRouteErrorResponse, Link, useRouteError } from 'react-router';

function ErrorCard({
  title,
  message,
  canReload = true,
}: {
  title: string;
  message: string;
  canReload?: boolean;
}) {
  return (
    <main className="login-wrap force-password">
      <div className="login-right">
        <div className="login-form-card" role="alert">
          <div className="login-icon">
            <AlertTriangle size={26} aria-hidden="true" />
          </div>
          <h1 className="h2-like">{title}</h1>
          <p className="muted">{message}</p>
          <div className="password-actions recovery-actions">
            <Link className="primary-button" to="/">
              Go to the start page
            </Link>
            {canReload && (
              <button type="button" className="outline-button" onClick={() => window.location.reload()}>
                Reload
              </button>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

/**
 * Error boundary for the router: any render error or failed lazy import in a
 * route lands here instead of blanking the whole app.
 */
export function RouteError() {
  const error = useRouteError();
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;
  console.error(error); // keep the details in the console for debugging
  return (
    <ErrorCard
      title="Something went wrong"
      message="This page hit an unexpected error. Reloading usually fixes it; if not, tell an administrator what you were doing."
    />
  );
}

export function NotFound() {
  return (
    <ErrorCard
      title="Page not found"
      message="There is no page at this address. Check the link, or go to the start page."
      canReload={false}
    />
  );
}
