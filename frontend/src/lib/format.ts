/** Small pure helpers. Pure = same input, same output: trivial to unit test. */

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map(part => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function displayName(user: { full_name?: string | null; username: string }): string {
  return user.full_name || user.username;
}

const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

/** "3 hours ago", "yesterday", "just now". */
export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '';
  const seconds = (new Date(iso).getTime() - now) / 1000;
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return 'just now';
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString() : '—';
}

/** A readable message from anything that was thrown. */
export function errorText(err: unknown, fallback = 'An unexpected error occurred.'): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

export const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);
