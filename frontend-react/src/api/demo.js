/** Explicitly fake, browser-memory-only preview. Never use for actual authorization. */
let nextId = 104;
let nextUserId = 5;
const records = [
  {
    id: 103, query: 'Albert Einstein', article_title: 'Albert Einstein', status: 'SUCCESS', matches: true,
    image_url: 'https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Albert_Einstein_Head.jpg/300px-Albert_Einstein_Head.jpg',
    fields: { Born: '14 March 1879', 'Known for': 'Theory of relativity', Field: 'Theoretical physics' },
    report_markdown: '# Albert Einstein\n\n## Verification summary\n\nThe article and illustrative portrait are related.\n\n**Match Status: PASS**\n\n> Demo content only. No Wikipedia or Gemini request was performed.',
    created_at: '2026-11-20T08:22:00+05:30', user_id: 2,
  },
  {
    id: 102, query: 'World War II', article_title: 'World War II', status: 'SUCCESS', matches: true,
    created_at: '2026-11-19T14:30:00+05:30', user_id: 2,
  },
  {
    id: 101, query: 'BMW', article_title: 'BMW', status: 'ERROR', matches: null,
    error_message: 'Demo processing error', created_at: '2026-11-19T09:12:00+05:30', user_id: 3,
  },
];
const users = [
  { id: 1, username: 'admin', full_name: 'System Administrator', role: 'admin', is_active: true },
  { id: 2, username: 'researcher', full_name: 'Alex Researcher', role: 'user', is_active: true },
  { id: 3, username: 'editor', full_name: 'Taylor Editor', role: 'user', is_active: true },
  { id: 4, username: 'reviewer', full_name: 'Morgan Reviewer', role: 'user', is_active: true },
];

const delay = (ms = 420) => new Promise(resolve => setTimeout(resolve, ms));

export const demo = {
  async login(username, password) {
    await delay();
    const user = users.find(u => u.username === username);
    if (!user || password !== 'demo123') throw new Error('Preview credentials: admin or researcher / demo123');
    return { token: `demo-${username}`, user };
  },
  async history(token) {
    await delay(190);
    const username = token.replace('demo-', '');
    const user = users.find(u => u.username === username);
    return user?.role === 'admin' ? [...records] : records.filter(r => r.user_id === user?.id);
  },
  // Same contract as api.historyPage / api.historyStats (see client.js).
  async historyPage(token, { pageSize = 5, before, q, status } = {}) {
    const needle = q?.trim().toLowerCase();
    const rows = (await this.history(token)).filter(r =>
      (!before || r.id < before) &&
      (!status || r.status === status) &&
      (!needle || `${r.query} ${r.article_title || ''}`.toLowerCase().includes(needle)));
    return { items: rows.slice(0, pageSize), hasMore: rows.length > pageSize };
  },
  async historyStats(token) {
    const rows = await this.history(token);
    const count = test => rows.filter(test).length;
    const match = count(r => r.status === 'SUCCESS' && r.matches === true);
    const noMatch = count(r => r.status === 'SUCCESS' && r.matches === false);
    const error = count(r => r.status === 'ERROR');
    return {
      total: rows.length, completed: count(r => r.status === 'SUCCESS'),
      match, no_match: noMatch, error, other: rows.length - match - noMatch - error,
    };
  },
  async historyDetail(token, id) {
    await delay(150);
    const entries = await this.history(token);
    const record = entries.find(r => r.id === Number(id));
    if (!record) throw new Error('Report not found or access denied.');
    return record;
  },
  async search(token, topic) {
    await delay(1000);
    const user = users.find(u => u.username === token.replace('demo-', ''));
    const record = {
      id: nextId++, query: topic, article_title: topic, status: 'SUCCESS', matches: true,
      image_url: '', fields: { Topic: topic, Source: 'Demo preview only' },
      report_markdown: `# ${topic}\n\n## Verification summary\n\n**Match Status: PASS (DEMO ONLY)**\n\nThis example was generated locally for a UI preview. No actual Wikipedia scraping or Gemini verification occurred.`,
      created_at: new Date().toISOString(), user_id: user?.id,
    };
    records.unshift(record);
    return record;
  },
  // Same contract as api.usersPage / api.userCount (see client.js).
  async usersPage(_token, { pageSize = 20, after, q } = {}) {
    await delay(180);
    const terms = (q || '').toLowerCase().split(/\s+/).filter(Boolean);
    const rows = users.filter(u =>
      (!after || u.id > after) &&
      terms.every(t => `${u.username} ${u.full_name || ''}`.toLowerCase().includes(t)));
    return { items: rows.slice(0, pageSize).map(u => ({ ...u })), hasMore: rows.length > pageSize };
  },
  async userCount() { await delay(120); return { total: users.length }; },
  // Same shape as GET /admin/overview, computed from the in-memory preview data.
  async adminOverview() {
    await delay(220);
    const DAY = 86400000;
    const today = new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00Z').getTime();
    const bucket = r => r.status === 'ERROR' ? 'error' : r.status === 'SUCCESS' && r.matches === true ? 'match'
      : r.status === 'SUCCESS' && r.matches === false ? 'no_match' : 'other';
    const at = r => new Date(r.created_at).getTime();
    const windowCounts = (from, to) => {
      const rows = records.filter(r => at(r) >= from && at(r) < to);
      const c = { total: rows.length, match: 0, no_match: 0, error: 0, other: 0 };
      rows.forEach(r => { c[bucket(r)] += 1; });
      c.active_users = new Set(rows.map(r => r.user_id).filter(Boolean)).size;
      return c;
    };
    const trendStart = today - 29 * DAY;
    const daily = Array.from({ length: 30 }, (_, i) => ({ date: new Date(trendStart + i * DAY).toISOString().slice(0, 10), match: 0, no_match: 0, error: 0, other: 0 }));
    records.forEach(r => { const d = daily.find(x => x.date === r.created_at.slice(0, 10)); if (d) d[bucket(r)] += 1; });
    const recent = records.filter(r => at(r) >= trendStart);
    const perUser = users.map(u => ({ id: u.id, username: u.username, full_name: u.full_name, searches: recent.filter(r => r.user_id === u.id).length }));
    const idle = users.filter(u => u.is_active && !perUser.find(p => p.id === u.id).searches);
    const errors = records.filter(r => r.status === 'ERROR');
    return {
      generated_at: new Date().toISOString(), trend_days: 30, kpi_days: 7,
      users: {
        total: users.length, admins: users.filter(u => u.role === 'admin').length, inactive: users.filter(u => !u.is_active).length,
        active_admins: users.filter(u => u.is_active && u.role === 'admin').length,
        active_users: users.filter(u => u.is_active && u.role !== 'admin').length,
      },
      last_period: windowCounts(today + DAY - 7 * DAY, today + DAY),
      previous_period: windowCounts(today + DAY - 14 * DAY, today + DAY - 7 * DAY),
      daily,
      top_users: perUser.filter(p => p.searches).sort((a, b) => b.searches - a.searches).slice(0, 5),
      idle_users: { count: idle.length, sample: idle.slice(0, 5).map(({ id, username, full_name }) => ({ id, username, full_name })) },
      recent_errors: errors.slice(0, 8).map(r => ({ id: r.id, query: r.query, code: 'DemoError', label: r.error_message || 'Demo error', created_at: r.created_at, username: users.find(u => u.id === r.user_id)?.username ?? null })),
      error_causes: errors.length ? [{ code: 'DemoError', label: 'Demo error', count: errors.length }] : [],
    };
  },
  async updateUser(token, userId, changes) {
    await delay();
    const requester = users.find(u => u.username === token.replace('demo-', ''));
    if (requester?.role !== 'admin') throw new Error('Administrator permissions required.');
    const user = users.find(u => u.id === Number(userId));
    if (!user) throw new Error('User not found.');
    if (user.id === requester.id && (changes.role && changes.role !== 'admin' || changes.is_active === false)) {
      throw new Error('You cannot demote or deactivate your own account.');
    }
    Object.assign(user, changes);
    return { ...user };
  },
  // Same rules as the backend DELETE endpoints.
  async deleteUser(token, userId) {
    await delay();
    const requester = users.find(u => u.username === token.replace('demo-', ''));
    if (requester?.role !== 'admin') throw new Error('Administrator permissions required.');
    const index = users.findIndex(u => u.id === Number(userId));
    if (index < 0) throw new Error('User not found.');
    if (users[index].id === requester.id) throw new Error('You cannot delete your own account.');
    for (const r of records) if (r.user_id === users[index].id) r.user_id = null; // keep, unlinked
    users.splice(index, 1);
  },
  // Preview only: nothing is stored, so demo123 keeps working afterwards.
  async changePassword(token, currentPassword) {
    await delay();
    if (currentPassword !== 'demo123') throw new Error('Current password is incorrect');
    return { access_token: token, token_type: 'bearer' };
  },
  async resetUserPassword(token, userId) {
    await delay();
    const requester = users.find(u => u.username === token.replace('demo-', ''));
    if (requester?.role !== 'admin') throw new Error('Administrator permissions required.');
    const user = users.find(u => u.id === Number(userId));
    if (!user) throw new Error('User not found.');
    if (user.id === requester.id) throw new Error("Use 'Change password' for your own account");
    return { ...user, must_change_password: true };
  },
  async deleteHistory(token, id) {
    await delay(200);
    const visible = await this.history(token);
    if (!visible.some(r => r.id === Number(id))) throw new Error('Search record not found');
    records.splice(records.findIndex(r => r.id === Number(id)), 1);
  },
  async createUser(_token, body) {
    await delay();
    if (users.some(u => u.username === body.username)) throw new Error('Username already exists.');
    const newUser = { id: nextUserId++, username: body.username, full_name: body.full_name, role: body.role, is_active: true, email: body.email ?? null };
    users.push(newUser);
    return newUser;
  },
  // Password reset needs real email, so it is off in preview mode.
  async passwordResetStatus() { return false; },
  async requestPasswordReset() { throw new Error('Password reset is not available in preview mode.'); },
  async confirmPasswordReset() { throw new Error('Password reset is not available in preview mode.'); },
  /** Preview mode has no backend, so nothing is actually checked: report that honestly. */
  async systemStatus() {
    await delay(150);
    return { status: 'demo', checked_at: new Date().toISOString(), components: [] };
  },
};
