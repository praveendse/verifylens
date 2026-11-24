import { useEffect, useId, useRef, useState } from 'react';
import { ArrowRight, FileSearch2, Info, Search, Sparkles, X } from 'lucide-react';
import ResultView from './ResultView.jsx';

/* Verification modes (spec SRCH-15). The switch turns on Super mode, which the
   API calls "thorough": a second Gemini call describes the image without the
   article first. Super mode also adds the label check; Standard is unchanged. */
const MODE_INFO = [
  { name: 'Standard', badge: 'Default · switch off', points: ['Standard · 1 AI call · faster, lower cost', 'Gemini describes the image and decides in the same request, with the article in view'] },
  { name: 'Super mode', badge: 'Switch on · ≈ 2× time and cost', points: ['2 AI calls · independent image description', 'Call 1 describes the image alone, before Gemini sees the article', 'Call 2 decides, using that independent description as a second view', 'Label check: compares Wikipedia’s caption, alt text and file name with the article title'] },
];

function ModeInfo({ id, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose(); };
    const onDown = e => { if (ref.current && !ref.current.parentElement.contains(e.target)) onClose(); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDown); };
  }, [onClose]);
  return (
    <div ref={ref} id={id} className="mode-info" role="dialog" aria-label="Verification modes">
      <div className="mode-info-head"><strong>Verification modes</strong><button type="button" className="mode-info-close" aria-label="Close" onClick={onClose}><X size={15}/></button></div>
      {MODE_INFO.map(m => (
        <section key={m.name} className="mode-info-item">
          <div className="mode-info-title"><span>{m.name}</span><small>{m.badge}</small></div>
          <ul>{m.points.map(p => <li key={p}>{p}</li>)}</ul>
        </section>
      ))}
      <p className="mode-info-foot">In Super mode, if the label check disagrees with Gemini&rsquo;s verdict, the result is marked <strong>Needs review</strong>. The verdict itself always comes from Gemini.</p>
    </div>
  );
}

function ModeSwitch({ mode, setMode, disabled }) {
  const [open, setOpen] = useState(false);
  const infoId = useId();
  const superOn = mode === 'thorough';
  return (
    <div className="mode-row">
      <button type="button" role="switch" aria-checked={superOn} className="mode-toggle" disabled={disabled}
        onClick={() => setMode(superOn ? 'standard' : 'thorough')}>
        <span className="mode-toggle-track" aria-hidden="true"><span className="mode-toggle-thumb"/></span>
        <span className="mode-toggle-label">Super mode</span>
      </button>
      <div className="mode-info-anchor">
        <button type="button" className="mode-info-button" aria-label="About verification modes"
          aria-expanded={open} aria-controls={open ? infoId : undefined} onClick={() => setOpen(v => !v)}><Info size={16}/></button>
        {open && <ModeInfo id={infoId} onClose={() => setOpen(false)}/>}
      </div>
    </div>
  );
}

/* One-piece connector: the shaft stretches to any width, the head is pinned
   to the right end (nested svg at x=100%) so it never distorts. */
const FlowArrow = () => (
  <li className="flow-arrow" aria-hidden="true">
    <svg width="100%" height="24" overflow="visible" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <line x1="2" y1="12" x2="100%" y2="12" />
      <svg x="100%" y="0" overflow="visible"><polyline points="-9,3 0,12 -9,21" /></svg>
    </svg>
  </li>
);

export default function VerifyPage({ onSearch, onClear, result, busy, error, isDemo }) {
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState('standard');
  const inputRef = useRef(null);
  const search = event => { event?.preventDefault(); if (topic.trim()) onSearch(topic.trim(), mode); };
  // Back to the start screen: empty box, result hidden, cursor ready to type.
  const clear = () => { setTopic(''); onClear(); inputRef.current?.focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  return (
    <div className="page-container">
      <div className="page-top-heading"><div><h1>Verify with <span>confidence.</span></h1><p>Search any Wikipedia topic. We extract article details, analyze its image with Gemini, and generate a downloadable verification report.</p></div></div>
      <div className="search-surface"><form onSubmit={search}><div className="search-input-container"><Search size={21}/><input ref={inputRef} aria-label="Wikipedia topic" placeholder="Search a Wikipedia topic..." value={topic} onChange={e => setTopic(e.target.value)} maxLength={200} /><button className="primary-button search-submit" disabled={busy || !topic.trim()} type="submit">{busy ? 'Verifying…' : 'Search & verify'} <ArrowRight size={17}/></button></div></form><ModeSwitch mode={mode} setMode={setMode} disabled={busy}/></div>
      {error && <div className="alert alert-danger" role="alert">{error}</div>}
      {busy && <div className="progress-panel" role="status"><span className="spinner"/><div><strong>Running verification pipeline…</strong><p>Retrieving the article, analyzing the image and generating your report. This can take a little while.</p></div></div>}
      {!result && !busy && <div className="how-works"><div className="how-works-heading"><span className="overline">HOW IT WORKS</span><h2>From search to evidence, in one workflow.</h2></div><ol className="steps-flow">
        <li className="flow-step"><span className="step-icon"><Search strokeWidth={2.4}/></span><h3>Search an article</h3></li>
        <FlowArrow />
        <li className="flow-step"><span className="step-icon"><Sparkles strokeWidth={2.4}/></span><h3>Check image relevance</h3></li>
        <FlowArrow />
        <li className="flow-step"><span className="step-icon"><FileSearch2 strokeWidth={2.4}/></span><h3>Save the result</h3></li>
      </ol></div>}
      {result && !busy && <ResultView key={result.id || result.query} result={result} isDemo={isDemo} onClear={clear}/>}
    </div>
  );
}
