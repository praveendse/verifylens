import { useState } from 'react';
import { ArrowRight, CheckCircle2, Fingerprint, LockKeyhole, SearchCheck, ShieldCheck, Users2 } from 'lucide-react';
import Brand from './Brand.jsx';

export default function LoginPage({ onLogin, busy, error, isDemo, resetEnabled = false, onForgot, notice }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const submit = event => {
    event.preventDefault();
    if (!username.trim() || !password) return;
    onLogin(username.trim(), password);
  };

  return (
    <div className="login-wrap">
      <div className="login-left">
        <header className="login-brand">
          <Brand large />
          {/* <span className="small-tag">WIKIPEDIA IMAGE VERIFICATION</span> */}
        </header>
        <div className="login-message">
          {/* <div className="eyebrow"><span className="eyebrow-dot" /> IMAGE INTELLIGENCE PLATFORM</div> */}
          <h1>Verify what<br />you <span className="serif-highlight">see.</span></h1>
          <p>A focused workspace for Wikipedia image verification, evidence reporting, and secure team access.</p>
          {/* <div className="login-features">
            <div><span><SearchCheck size={19} /></span><div><strong>Source-aware verification</strong><small>Wikipedia article data and AI image analysis</small></div></div>
            <div><span><ShieldCheck size={19} /></span><div><strong>Role-based permissions</strong><small>Separate access for administrators and users</small></div></div>
            <div><span><Users2 size={19} /></span><div><strong>Search audit trail</strong><small>Tracked searches and saved verification reports</small></div></div>
          </div> */}
        </div>
        <footer className="login-footer">Built for careful verification <span>·</span> Powered by FastAPI &amp; Gemini</footer>
      </div>
      <div className="login-right">
        <div className="login-form-card">
          <div className="login-icon"><Fingerprint size={26} /></div>
          <span className="form-eyebrow">SECURE ACCESS</span>
          <h2>Welcome back</h2>
          <p className="muted">Sign in to continue to your workspace.</p>
          {isDemo && <div className="demo-callout"><CheckCircle2 size={16} /><span><strong>Preview mode</strong> — use admin or researcher with password <code>demo123</code>. No real authentication or persistence.</span></div>}
          {notice && <div className="alert alert-success" role="status">{notice}</div>}
          {error && <div className="alert alert-danger" role="alert">{error}</div>}
          <form onSubmit={submit} className="login-form">
            <label htmlFor="login-user">Username</label>
            <input id="login-user" autoComplete="username" placeholder="Enter your username" value={username} onChange={e => setUsername(e.target.value)} required />
            <div className="label-between"><label htmlFor="login-password">Password</label>{resetEnabled ? <button type="button" className="link-button" onClick={onForgot}>Forgot password?</button> : <LockKeyhole size={14} />}</div>
            <div className="password-field"><input id="login-password" autoComplete="current-password" type={showPassword ? 'text' : 'password'} placeholder="Enter your password" value={password} onChange={e => setPassword(e.target.value)} required /><button type="button" onClick={() => setShowPassword(v => !v)}>{showPassword ? 'Hide' : 'Show'}</button></div>
            <button className="primary-button login-submit" disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} /></button>
          </form>
          <div className="login-bottom-note"><LockKeyhole size={14} /> Accounts are created by an administrator only.</div>
        </div>
        <p className="login-copyright">VerifyLens · Internal verification workspace</p>
      </div>
    </div>
  );
}
