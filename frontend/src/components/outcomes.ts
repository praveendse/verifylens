/** Search outcome categories, shared by the history donut and the admin charts. */
export type OutcomeKey = 'match' | 'no_match' | 'error' | 'other';
export type OutcomeCounts = Partial<Record<OutcomeKey | 'total' | 'completed', number>>;

/** Fixed order and colours: colour follows the category, never its rank. */
export const CATEGORIES: ReadonlyArray<{
  key: OutcomeKey;
  label: string;
  color: string;
  optional?: boolean;
}> = [
  { key: 'match', label: 'Match verified', color: 'var(--viz-match)' },
  { key: 'no_match', label: 'No match', color: 'var(--viz-no-match)' },
  { key: 'error', label: 'Failed', color: 'var(--viz-error)' },
  { key: 'other', label: 'Not finished', color: 'var(--viz-other)', optional: true }, // hidden when 0
];
