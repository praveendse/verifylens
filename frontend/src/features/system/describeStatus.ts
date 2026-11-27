import { ApiError } from '@/api/client';
import type { ComponentStatus, SystemStatus as Status } from '@/api/types';

type Tone = 'idle' | 'ok' | 'down';
export interface View {
  tone: Tone;
  label: string;
  components: ComponentStatus[];
  note?: string;
}

/** Pure function: query state in, what to show out. Easy to unit test. */
export function describeStatus(data: Status | undefined, error: unknown, pending: boolean): View {
  if (pending) return { tone: 'idle', label: 'Checking…', components: [], note: 'Running live checks…' };
  if (error) {
    const status = error instanceof ApiError ? error.status : 0;
    if (status === 0)
      return {
        tone: 'down',
        label: "Can't reach the server",
        components: [],
        note: 'The app server is not answering. Check your connection, then try again.',
      };
    if (status === 401 || status === 403)
      return {
        tone: 'idle',
        label: 'Status unavailable',
        components: [],
        note: 'Your session has expired. Sign in again to see live status.',
      };
    return {
      tone: 'down',
      label: "Couldn't check status",
      components: [],
      note: 'The status check did not finish. Try again in a minute.',
    };
  }
  const components = data?.components ?? [];
  const down = components.filter(c => c.status !== 'ok');
  if (data?.status === 'ok' && down.length === 0)
    return { tone: 'ok', label: 'Everything is working', components };
  if (data?.status !== 'degraded')
    return { tone: 'idle', label: 'Status unknown', components, note: 'No status to show yet.' };
  const names = down.map(c => c.label);
  const label =
    names.length === 0
      ? "Some features aren't working right now"
      : names.length === 1
        ? `${names[0]} isn't working`
        : `${names.slice(0, -1).join(', ')} and ${names.at(-1)} aren't working`;
  return { tone: 'down', label, components, note: 'Some features may not work right now.' };
}
