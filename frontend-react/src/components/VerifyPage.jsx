import { useRef, useState } from 'react';
import { ArrowRight, FileSearch2, Search, Sparkles } from 'lucide-react';
import ResultView from './ResultView.jsx';

const suggestions = ['Albert Einstein', 'World War II', 'Sri Lanka', 'BMW'];
// Shown on phones too; the rest are hidden there to keep the chips on one row.
const MOBILE_SUGGESTIONS = new Set(['World War II', 'BMW']);

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
  const inputRef = useRef(null);
  const search = event => { event?.preventDefault(); if (topic.trim()) onSearch(topic.trim()); };
  // Back to the start screen: empty box, result hidden, cursor ready to type.
  const clear = () => { setTopic(''); onClear(); inputRef.current?.focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  return (
    <div className="page-container">
      <div className="page-top-heading"><div><h1>Verify with <span>confidence.</span></h1><p>Search any Wikipedia topic. We extract article details, analyze its image with Gemini, and generate a downloadable verification report.</p></div></div>
      <div className="search-surface"><form onSubmit={search}><div className="search-input-container"><Search size={21}/><input ref={inputRef} aria-label="Wikipedia topic" placeholder="Search a Wikipedia topic..." value={topic} onChange={e => setTopic(e.target.value)} maxLength={200} /><button className="primary-button search-submit" disabled={busy || !topic.trim()} type="submit">{busy ? 'Verifying…' : 'Search & verify'} <ArrowRight size={17}/></button></div></form><div className="search-suggestions"><span>TRY SEARCHING</span>{suggestions.map(q => <button key={q} className={MOBILE_SUGGESTIONS.has(q) ? undefined : 'suggest-extra'} onClick={() => setTopic(q)} disabled={busy}>{q} <ArrowRight size={12}/></button>)}</div></div>
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
