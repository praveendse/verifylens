/** The token from "#token=..." (a URL fragment never reaches server logs). */
export function readResetToken(hash: string): string | null {
  return new URLSearchParams(hash.replace(/^#/, '')).get('token') || null;
}
