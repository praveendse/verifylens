import { ArrowRight, FileSearch2, Info, Search, Sparkles, X } from 'lucide-react';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import type { SearchMode } from '@/api/types';
import { ErrorAlert } from '@/components/Feedback';
import { PageHeading } from '@/components/PageHeading';
import { errorText } from '@/lib/format';
import { useLastResult, useSearch } from './queries';
import { ResultView } from './ResultView';

const MODE_INFO = [
  {
    name: 'Standard',
    badge: 'Default · switch off',
    points: [
      'Standard · 1 AI call · faster, lower cost',
      'Gemini describes the image and decides in the same request, with the article in view',
    ],
  },
  {
    name: 'Super mode',
    badge: 'Switch on · ≈ 2× time and cost',
    points: [
      '2 AI calls · independent image description',
      'Call 1 describes the image alone, before Gemini sees the article',
      'Call 2 decides, using that independent description as a second view',
      'Label check: compares Wikipedia’s caption, alt text and file name with the article title',
    ],
  },
];

function ModeInfo({ id, onClose }: { id: string; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.parentElement?.contains(e.target as Node)) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [onClose]);
  return (
    <div ref={ref} id={id} className="mode-info" role="dialog" aria-label="Verification modes">
      <div className="mode-info-head">
        <strong>Verification modes</strong>
        <button type="button" className="mode-info-close" aria-label="Close" onClick={onClose}>
          <X size={15} />
        </button>
      </div>
      {MODE_INFO.map(m => (
        <section key={m.name} className="mode-info-item">
          <div className="mode-info-title">
            <span>{m.name}</span>
            <small>{m.badge}</small>
          </div>
          <ul>
            {m.points.map(p => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </section>
      ))}
      <p className="mode-info-foot">
        In Super mode, if the label check disagrees with Gemini&rsquo;s verdict, the result is marked{' '}
        <strong>Needs review</strong>. The verdict itself always comes from Gemini.
      </p>
    </div>
  );
}

function ModeSwitch({
  mode,
  setMode,
  disabled,
}: {
  mode: SearchMode;
  setMode: (m: SearchMode) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const infoId = useId();
  const superOn = mode === 'thorough';
  return (
    <div className="mode-row">
      <button
        type="button"
        role="switch"
        aria-checked={superOn}
        className="mode-toggle"
        disabled={disabled}
        onClick={() => setMode(superOn ? 'standard' : 'thorough')}
      >
        <span className="mode-toggle-track" aria-hidden="true">
          <span className="mode-toggle-thumb" />
        </span>
        <span className="mode-toggle-label">Super mode</span>
      </button>
      <div className="mode-info-anchor">
        <button
          type="button"
          className="mode-info-button"
          aria-label="About verification modes"
          aria-expanded={open}
          aria-controls={open ? infoId : undefined}
          onClick={() => setOpen(v => !v)}
        >
          <Info size={16} />
        </button>
        {open && <ModeInfo id={infoId} onClose={() => setOpen(false)} />}
      </div>
    </div>
  );
}

const FlowArrow = () => (
  <li className="flow-arrow" aria-hidden="true">
    <svg
      width="100%"
      height="24"
      overflow="visible"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="2" y1="12" x2="100%" y2="12" />
      <svg x="100%" y="0" overflow="visible">
        <polyline points="-9,3 0,12 -9,21" />
      </svg>
    </svg>
  </li>
);

function HowItWorks() {
  return (
    <div className="how-works">
      <div className="how-works-heading">
        <span className="overline">HOW IT WORKS</span>
        <h2>From search to evidence, in one workflow.</h2>
      </div>
      <ol className="steps-flow">
        <li className="flow-step">
          <span className="step-icon" aria-hidden="true">
            <Search strokeWidth={2.4} />
          </span>
          <h3>Search an article</h3>
        </li>
        <FlowArrow />
        <li className="flow-step">
          <span className="step-icon" aria-hidden="true">
            <Sparkles strokeWidth={2.4} />
          </span>
          <h3>Check image relevance</h3>
        </li>
        <FlowArrow />
        <li className="flow-step">
          <span className="step-icon" aria-hidden="true">
            <FileSearch2 strokeWidth={2.4} />
          </span>
          <h3>Save the result</h3>
        </li>
      </ol>
    </div>
  );
}

/** Route /verify */
export function VerifyPage() {
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState<SearchMode>('standard');
  const inputRef = useRef<HTMLInputElement>(null);
  const search = useSearch();
  const result = useLastResult();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (topic.trim()) search.mutate({ topic: topic.trim(), mode });
  }

  // Back to the start screen: empty box, result hidden, cursor ready to type.
  function newSearch() {
    setTopic('');
    search.clear();
    inputRef.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <div className="page-container">
      <PageHeading
        title="Verify with"
        accent="confidence."
        description="Search any Wikipedia topic. We extract article details, analyze its image with Gemini, and generate a downloadable verification report."
      />
      <div className="search-surface">
        <form onSubmit={submit} role="search">
          <div className="search-input-container">
            <Search size={21} aria-hidden="true" />
            <input
              ref={inputRef}
              aria-label="Wikipedia topic"
              placeholder="Search a Wikipedia topic..."
              value={topic}
              onChange={e => setTopic(e.target.value)}
              maxLength={200}
            />
            <button
              className="primary-button search-submit"
              disabled={search.isPending || !topic.trim()}
              type="submit"
            >
              {search.isPending ? 'Verifying…' : 'Search & verify'}{' '}
              <ArrowRight size={17} aria-hidden="true" />
            </button>
          </div>
        </form>
        <ModeSwitch mode={mode} setMode={setMode} disabled={search.isPending} />
      </div>
      <ErrorAlert>{search.error && errorText(search.error)}</ErrorAlert>
      {search.isPending && (
        <div className="progress-panel" role="status">
          <span className="spinner" aria-hidden="true" />
          <div>
            <strong>Running verification pipeline…</strong>
            <p>
              Retrieving the article, analyzing the image and generating your report. This can take a little
              while.
            </p>
          </div>
        </div>
      )}
      {!result && !search.isPending && <HowItWorks />}
      {result && !search.isPending && <ResultView key={result.id} result={result} onNewSearch={newSearch} />}
    </div>
  );
}
