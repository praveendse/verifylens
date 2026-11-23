import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api/client.js';
import { demo } from './api/demo.js';
import LoginPage from './components/LoginPage.jsx';
import Shell from './components/Shell.jsx';
import VerifyPage from './components/VerifyPage.jsx';
import HistoryPage from './components/HistoryPage.jsx';
import AdminPage from './components/AdminPage.jsx';
import AdminOverview from './components/AdminOverview.jsx';
import { ForcePasswordChange } from './components/PasswordForms.jsx';
import { ForgotPasswordPage, ResetPasswordPage } from './components/PasswordRecovery.jsx';
import { clearResetToken, readResetToken } from './resetLink.js';

const isDemo = import.meta.env.VITE_DEMO_MODE === 'true';
const service = isDemo ? demo : api;

const HISTORY_PAGE_SIZE = 5;
const NO_FILTER = { q: '', status: '' };
const USERS_PAGE_SIZE = 20;

export default function App() {
  // Access token kept in memory only. After a page reload the sign-in is
  // restored from the HttpOnly refresh cookie (see api.restoreSession).
  const [session, setSession] = useState(null);
  const [restoring, setRestoring] = useState(() => !readResetToken() && typeof service.restoreSession === 'function');
  const [section, setSection] = useState('verify');
  const [menuOpen, setMenuOpen] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState('');
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [historyMoreBusy, setHistoryMoreBusy] = useState(false);
  const [historyFilter, setHistoryFilter] = useState(NO_FILTER);
  const [historyStats, setHistoryStats] = useState(null);
  const historyReq = useRef(0);
  const [historyDetail, setHistoryDetail] = useState(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [users, setUsers] = useState([]);
  const [userBusy, setUserBusy] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersHasMore, setUsersHasMore] = useState(false);
  const [usersMoreBusy, setUsersMoreBusy] = useState(false);
  const [usersTotal, setUsersTotal] = useState(null);
  const usersReq = useRef(0);
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState('');
  const [userError, setUserError] = useState('');
  const [userSuccess, setUserSuccess] = useState('');
  // Signed-out screens: sign in, "forgot password", or the reset page opened
  // from an email link. The link's token is kept in memory only.
  const [resetToken, setResetToken] = useState(() => readResetToken());
  const [authView, setAuthView] = useState(() => (readResetToken() ? 'reset' : 'login'));
  const [authNotice, setAuthNotice] = useState('');
  const [resetEnabled, setResetEnabled] = useState(false);

  // Take the token out of the address bar and history (spec PWR-17).
  useEffect(() => { if (readResetToken()) clearResetToken(); }, []);
  useEffect(() => {
    let live = true;
    service.passwordResetStatus().then(on => { if (live) setResetEnabled(on); });
    return () => { live = false; };
  }, []);

  // Silent refreshes inside the API client hand the new token back here. The
  // token is swapped on the current session object on purpose: a new object
  // would re-run every data effect and reset paging and open records.
  const sessionRef = useRef(null);
  sessionRef.current = session;
  useEffect(() => {
    service.onTokenRefreshed?.(token => { if (sessionRef.current) sessionRef.current.token = token; });
    return () => service.onTokenRefreshed?.(null);
  }, []);

  useEffect(() => {
    if (!restoring) return undefined;
    let live = true;
    service.restoreSession()
      .then(data => {
        if (!live || !data || !['admin', 'user'].includes(data.user?.role)) return;
        setSession(data); setSection(data.user.role === 'admin' ? 'overview' : 'verify');
      })
      .finally(() => { if (live) setRestoring(false); });
    return () => { live = false; };
  }, [restoring]);

  const logout = useCallback(() => {
    service.logout?.(); // revoke the refresh cookie; local sign-out doesn't wait
    setAuthView('login'); setAuthNotice('');
    setSession(null); setSection('verify'); setResult(null); setHistory([]); setUsers([]);
    setUsersHasMore(false); setUsersTotal(null); setOverview(null); setOverviewError('');
    setHistoryHasMore(false); setHistoryStats(null); setHistoryFilter(NO_FILTER);
    setHistoryDetail(null); setAuthError('');
  }, []);

  const errorMessage = useCallback((err) => {
    if (err instanceof ApiError && err.status === 401) {
      logout();
      return 'Session expired. Please sign in again.';
    }
    if (err instanceof ApiError && err.status === 403 && err.message === 'Password change required') {
      // An admin reset the password while this tab was open: show the change screen.
      // Return the same object when already flagged, or every 403 would
      // re-trigger the data-loading effects in a loop.
      setSession(s => (!s || s.user.must_change_password) ? s : { ...s, user: { ...s.user, must_change_password: true } });
      return err.message;
    }
    return err?.message || 'An unexpected error occurred.';
  }, [logout]);

  const login = async (username, password) => {
    setAuthBusy(true); setAuthError('');
    try {
      const data = await service.login(username, password);
      if (!['admin','user'].includes(data?.user?.role)) throw new Error('The backend returned an unsupported user role.');
      // Admins land on the overview; everyone else on Verify.
      setSession(data); setSection(data.user.role === 'admin' ? 'overview' : 'verify'); setAuthNotice('');
    } catch (err) { setAuthError(err.message || 'Could not sign in.'); }
    finally { setAuthBusy(false); }
  };

  const checkSystems = useCallback(() => service.systemStatus(session?.token), [session]);

  /* History is fetched a page at a time (newest first) with filters applied on
     the server. Each reset bumps historyReq, so a slow response for an old
     filter or a stale "Show more" can never overwrite newer results. */
  const loadHistory = useCallback(async () => {
    if (!session) return;
    const req = ++historyReq.current;
    setHistoryBusy(true); setHistoryError('');
    try {
      const page = await service.historyPage(session.token, { pageSize: HISTORY_PAGE_SIZE, ...historyFilter });
      if (req !== historyReq.current) return;
      setHistory(page.items); setHistoryHasMore(page.hasMore);
    } catch (err) { if (req === historyReq.current) setHistoryError(errorMessage(err)); }
    finally { if (req === historyReq.current) setHistoryBusy(false); }
  }, [session, historyFilter, errorMessage]);

  const loadMoreHistory = useCallback(async () => {
    const last = history[history.length - 1];
    if (!session || !last) return;
    const req = historyReq.current;
    setHistoryMoreBusy(true); setHistoryError('');
    try {
      const page = await service.historyPage(session.token, { pageSize: HISTORY_PAGE_SIZE, before: last.id, ...historyFilter });
      if (req !== historyReq.current) return;
      setHistory(prev => [...prev, ...page.items]); setHistoryHasMore(page.hasMore);
    } catch (err) { if (req === historyReq.current) setHistoryError(errorMessage(err)); }
    finally { setHistoryMoreBusy(false); }
  }, [session, history, historyFilter, errorMessage]);

  // Back to the newest page without a request: those rows are already loaded.
  // Bumping historyReq discards any "Show more" still in flight.
  const collapseHistory = useCallback(() => {
    historyReq.current += 1;
    setHistoryMoreBusy(false);
    setHistory(prev => prev.slice(0, HISTORY_PAGE_SIZE));
    setHistoryHasMore(true); // we had more than one page, so older rows exist
  }, []);

  // Donut totals: counted on the server over ALL records, not just loaded rows.
  const loadHistoryStats = useCallback(async () => {
    if (!session) return;
    try { setHistoryStats(await service.historyStats(session.token)); }
    catch (err) { setHistoryError(errorMessage(err)); }
  }, [session, errorMessage]);

  const refreshHistory = useCallback(() => Promise.all([loadHistory(), loadHistoryStats()]), [loadHistory, loadHistoryStats]);

  /* Team members: first page of USERS_PAGE_SIZE plus the total, same
     stale-response guard (usersReq) as history. */
  const loadUsers = useCallback(async () => {
    if (!session || session.user.role !== 'admin') return;
    const req = ++usersReq.current;
    setUsersLoading(true); setUserError('');
    try {
      const [page, count] = await Promise.all([
        service.usersPage(session.token, { pageSize: USERS_PAGE_SIZE }),
        service.userCount(session.token),
      ]);
      if (req !== usersReq.current) return;
      setUsers(page.items); setUsersHasMore(page.hasMore); setUsersTotal(count?.total ?? null);
    } catch (err) { if (req === usersReq.current) setUserError(errorMessage(err)); }
    finally { if (req === usersReq.current) setUsersLoading(false); }
  }, [session, errorMessage]);

  const loadMoreUsers = useCallback(async () => {
    const last = users[users.length - 1];
    if (!session || !last) return;
    const req = usersReq.current;
    setUsersMoreBusy(true); setUserError('');
    try {
      const page = await service.usersPage(session.token, { pageSize: USERS_PAGE_SIZE, after: last.id });
      if (req !== usersReq.current) return;
      setUsers(prev => [...prev, ...page.items]); setUsersHasMore(page.hasMore);
    } catch (err) { if (req === usersReq.current) setUserError(errorMessage(err)); }
    finally { setUsersMoreBusy(false); }
  }, [session, users, errorMessage]);

  const collapseUsers = useCallback(() => {
    usersReq.current += 1;
    setUsersMoreBusy(false);
    setUsers(prev => prev.slice(0, USERS_PAGE_SIZE));
    setUsersHasMore(true);
  }, []);

  const loadOverview = useCallback(async () => {
    if (!session || session.user.role !== 'admin') return;
    setOverviewLoading(true); setOverviewError('');
    try { setOverview(await service.adminOverview(session.token)); }
    catch (err) { setOverviewError(errorMessage(err)); }
    finally { setOverviewLoading(false); }
  }, [session, errorMessage]);

  useEffect(() => {
    if (session?.user.role === 'admin' && !session.user.must_change_password && section === 'overview') loadOverview();
  }, [session, section, loadOverview]);

  // "Find user" box: matched on the server, so it finds accounts on any page.
  // Throws on failure; the search box shows the message.
  const searchUsers = useCallback(async q => {
    try { return await service.usersPage(session.token, { pageSize: USERS_PAGE_SIZE, q }); }
    catch (err) { throw new Error(errorMessage(err)); }
  }, [session, errorMessage]);

  // Nothing loads until a temporary password has been replaced: the server
  // would refuse it (403) anyway.
  const ready = Boolean(session) && !session.user.must_change_password;
  useEffect(() => { if (ready) loadHistory(); }, [ready, loadHistory]); // also re-runs when filters change
  useEffect(() => { if (ready) loadHistoryStats(); }, [ready, loadHistoryStats]);
  useEffect(() => { if (ready && session.user.role === 'admin' && section === 'admin') loadUsers(); }, [ready, session, section, loadUsers]);

  const search = async topic => {
    setSearchBusy(true); setSearchError(''); setResult(null);
    try { const data = await service.search(session.token, topic); setResult(data); await refreshHistory(); }
    catch (err) { setSearchError(errorMessage(err)); await refreshHistory(); }
    finally { setSearchBusy(false); }
  };

  const openHistory = async id => {
    setHistoryDetail(null); setDetailError(''); setDetailBusy(true);
    try { setHistoryDetail(await service.historyDetail(session.token, id)); }
    catch (err) { setDetailError(errorMessage(err)); }
    finally { setDetailBusy(false); }
  };

  /* Deletes return '' on success or an error message, which the confirmation
     dialog shows so the user can retry or cancel. */
  const deleteHistoryRecord = async id => {
    try {
      await service.deleteHistory(session.token, id);
      setHistoryDetail(null); setDetailError('');
      if (result?.id === id) setResult(null); // don't keep showing a deleted result on the Verify page
      await refreshHistory();
      return '';
    } catch (err) { return errorMessage(err); }
  };

  const deleteUser = async (id, label) => {
    if (session?.user.role !== 'admin') return 'Administrator permissions required.';
    try {
      await service.deleteUser(session.token, id);
      setUserError(''); setUserSuccess(`Account “${label}” deleted. Their saved searches were kept.`);
      await loadUsers();
      return '';
    } catch (err) { return errorMessage(err); }
  };

  const createUser = async body => {
    if (session?.user.role !== 'admin') return false;
    setUserBusy(true); setUserError(''); setUserSuccess('');
    try { await service.createUser(session.token, body); setUserSuccess(`Account “${body.username}” created. They’ll choose their own password at first sign-in.`); await loadUsers(); return true; }
    catch (err) { setUserError(errorMessage(err)); return false; }
    finally { setUserBusy(false); }
  };

  const updateUser = async (id, changes) => {
    if (session?.user.role !== 'admin') return false;
    setUpdateBusy(true); setUserError(''); setUserSuccess('');
    try {
      const updated = await service.updateUser(session.token, id, changes);
      setUserSuccess('Account updated successfully.');
      await loadUsers();
      return updated || true; // the editor shows the saved account, which may not be on a loaded page
    } catch (err) {
      setUserError(errorMessage(err));
      return false;
    } finally {
      setUpdateBusy(false);
    }
  };

  /* Own password (profile menu, or the forced step after an admin reset).
     The server returns a new token and revokes the old one, so swap it in.
     Returns '' or an error message for the form to show. */
  const changePassword = async (current, next) => {
    try {
      const data = await service.changePassword(session.token, current, next);
      if (!data?.access_token) throw new Error('Password changed, but no new session was returned. Please sign in again.');
      setSession(s => ({ ...s, token: data.access_token, user: { ...s.user, must_change_password: false } }));
      return '';
    } catch (err) { return errorMessage(err); }
  };

  const resetUserPassword = async (id, password) => {
    if (session?.user.role !== 'admin') return 'Administrator permissions required.';
    try { await service.resetUserPassword(session.token, id, password); return ''; }
    catch (err) { return errorMessage(err); }
  };

  /* Password recovery. Both return '' or an error message for the form. */
  const requestReset = async identifier => {
    try { await service.requestPasswordReset(identifier); return ''; }
    catch (err) { return err?.message || 'Could not send the request.'; }
  };

  const confirmReset = async newPassword => {
    try {
      await service.confirmPasswordReset(resetToken, newPassword);
      setResetToken(null); setAuthError('');
      setAuthNotice('Password updated. Sign in with your new password.');
      setAuthView('login');
      return '';
    } catch (err) { return err?.message || 'Could not reset the password.'; }
  };

  const showLogin = () => { setResetToken(null); setAuthView('login'); };

  if (restoring) {
    return <div role="status" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <span className="spinner" aria-label="Restoring your session"/>
    </div>;
  }
  if (!session) {
    if (authView === 'forgot') return <ForgotPasswordPage onSubmit={requestReset} onBack={showLogin}/>;
    if (authView === 'reset' && resetToken) {
      return <ResetPasswordPage onSubmit={confirmReset} onBack={showLogin}
        onRequestNew={() => { setResetToken(null); setAuthView('forgot'); }}/>;
    }
    return <LoginPage onLogin={login} busy={authBusy} error={authError} isDemo={isDemo}
      resetEnabled={resetEnabled} notice={authNotice}
      onForgot={() => { setAuthNotice(''); setAuthError(''); setAuthView('forgot'); }}/>;
  }
  if (session.user.must_change_password) return <ForcePasswordChange user={session.user} onSubmit={changePassword} onLogout={logout}/>;
  const canAdmin = session.user.role === 'admin';
  const selected = ['admin', 'overview'].includes(section) && !canAdmin ? 'verify' : section;

  return <Shell user={session.user} section={selected} setSection={setSection} onLogout={logout} onChangePassword={changePassword} isDemo={isDemo} isMenuOpen={menuOpen} setMenuOpen={setMenuOpen} checkSystems={checkSystems}>
    {selected === 'verify' && <VerifyPage onSearch={search} onClear={() => { setResult(null); setSearchError(''); }} result={result} busy={searchBusy} error={searchError} isDemo={isDemo}/>}
    {selected === 'history' && <HistoryPage records={history} stats={historyStats} hasMore={historyHasMore} moreBusy={historyMoreBusy} onLoadMore={loadMoreHistory} onShowLess={collapseHistory} pageSize={HISTORY_PAGE_SIZE} filter={historyFilter} onFilterChange={setHistoryFilter} loading={historyBusy} error={historyError} onRefresh={refreshHistory} onDeleteRecord={deleteHistoryRecord} onOpen={openHistory} selected={historyDetail} detailBusy={detailBusy} detailError={detailError} clearSelected={() => { setHistoryDetail(null); setDetailError(''); }} isDemo={isDemo}/>}
    {selected === 'overview' && canAdmin && <AdminOverview data={overview} loading={overviewLoading} error={overviewError} onRefresh={loadOverview} onManageUsers={() => setSection('admin')}/>}
    {selected === 'admin' && canAdmin && <AdminPage users={users} usersTotal={usersTotal} usersHasMore={usersHasMore} usersMoreBusy={usersMoreBusy} onLoadMoreUsers={loadMoreUsers} onShowLessUsers={collapseUsers} usersPageSize={USERS_PAGE_SIZE} onSearchUsers={searchUsers} busy={userBusy} loading={usersLoading} error={userError} success={userSuccess} onCreate={createUser} onRefresh={loadUsers} onUpdate={updateUser} onDelete={deleteUser} onResetPassword={resetUserPassword} updateBusy={updateBusy} currentUserId={session.user.id}/>}
  </Shell>;
}
