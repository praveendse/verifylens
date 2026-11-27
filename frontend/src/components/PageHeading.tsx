import type { ReactNode } from 'react';

/** "Search <span>history.</span>" heading used at the top of every workspace page. */
export function PageHeading({
  title,
  accent,
  description,
  actions,
}: {
  title: string;
  accent: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-top-heading">
      <div>
        <h1>
          {title} <span>{accent}</span>
        </h1>
        <p>{description}</p>
      </div>
      {actions}
    </div>
  );
}
