/** Password-reset email links look like /reset-password#token=<token> (spec PWR-06).
 *  The token is in the fragment so it never reaches the server in a URL. */

/** The token from the current address, or null. Pure: safe in React initializers. */
export function readResetToken(loc = window.location) {
  if (!/\/reset-password\/?$/.test(loc.pathname)) return null;
  const token = new URLSearchParams((loc.hash || '').replace(/^#/, '')).get('token');
  return token || null;
}

/** Remove the token from the address bar and browser history. */
export function clearResetToken(win = window) {
  win.history.replaceState(null, '', '/');
}
