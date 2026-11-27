/**
 * Same rules as the backend (security/password_policy.py). The server is the
 * authority; checking here only gives faster feedback.
 */
export const MIN_PASSWORD_LENGTH = 12;

export function passwordProblem(username: string, password: string): string {
  if (password.length < MIN_PASSWORD_LENGTH) return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (!password.trim()) return 'Password must not be only spaces.';
  if (username && password.toLowerCase().includes(username.toLowerCase()))
    return 'Password must not contain the username.';
  return '';
}

/** Random password without look-alikes (0/O, 1/l/I), from the browser's CSPRNG, no modulo bias. */
export function generatePassword(length = 16): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789-_';
  const limit = Math.floor(2 ** 32 / chars.length) * chars.length;
  const out: string[] = [];
  const buf = new Uint32Array(1);
  while (out.length < length) {
    crypto.getRandomValues(buf);
    const n = buf[0] ?? 0;
    if (n < limit) out.push(chars[n % chars.length] as string);
  }
  return out.join('');
}
