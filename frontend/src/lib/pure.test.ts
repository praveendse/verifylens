import { ApiError } from '@/api/client';
import { generatePassword, passwordProblem } from '@/features/auth/passwordPolicy';
import { readResetToken } from '@/features/auth/resetToken';
import { describeStatus } from '@/features/system/describeStatus';
import { initials, timeAgo } from './format';
import { niceTicks, startOffsets } from './math';

/* Pure functions: no rendering, no network. The cheapest tests to write and run. */

describe('format', () => {
  it('builds initials from up to two words', () => {
    expect(initials('Alex Researcher')).toBe('AR');
    expect(initials('  madonna  ')).toBe('M');
    expect(initials('Ada Lovelace King')).toBe('AL');
  });

  it('describes relative time', () => {
    const now = Date.parse('2026-11-25T12:00:00Z');
    expect(timeAgo('2026-11-25T11:59:30Z', now)).toBe('just now');
    expect(timeAgo('2026-11-25T09:00:00Z', now)).toMatch(/3 hours ago/);
    expect(timeAgo(null, now)).toBe('');
  });
});

describe('math', () => {
  it('computes running offsets', () => expect(startOffsets([3, 5, 2])).toEqual([0, 3, 8]));
  it('makes nice ticks', () => {
    expect(niceTicks(0)).toEqual([0, 1]);
    expect(niceTicks(7)).toEqual([0, 5, 10]);
  });
});

describe('password policy', () => {
  it('mirrors the backend rules', () => {
    expect(passwordProblem('alex', 'short')).toMatch(/12 characters/);
    expect(passwordProblem('alex', ' '.repeat(12))).toMatch(/only spaces/);
    expect(passwordProblem('alex', 'my-ALEX-password')).toMatch(/username/);
    expect(passwordProblem('alex', 'a-good-long-password')).toBe('');
  });

  it('generates passwords that pass the policy and avoid look-alikes', () => {
    const pw = generatePassword();
    expect(pw).toHaveLength(16);
    expect(pw).not.toMatch(/[0O1lI]/);
    expect(passwordProblem('someone', pw)).toBe('');
  });
});

describe('reset link', () => {
  it('reads the token from the fragment only', () => {
    expect(readResetToken('#token=abc123')).toBe('abc123');
    expect(readResetToken('')).toBeNull();
  });
});

describe('system status', () => {
  it('is never green without a successful check', () => {
    expect(describeStatus(undefined, null, true).tone).toBe('idle');
    expect(describeStatus(undefined, new ApiError('down', 0), false)).toMatchObject({
      tone: 'down',
      label: "Can't reach the server",
    });
    const degraded = describeStatus(
      {
        status: 'degraded',
        checked_at: '',
        components: [
          { name: 'gemini', label: 'Gemini', status: 'down', latency_ms: 0 },
          { name: 'db', label: 'Database', status: 'ok', latency_ms: 2 },
        ],
      },
      null,
      false,
    );
    expect(degraded).toMatchObject({ tone: 'down', label: "Gemini isn't working" });
  });
});
