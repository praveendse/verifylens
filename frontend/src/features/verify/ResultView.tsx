import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  Download,
  FileText,
  Image as ImageIcon,
  RotateCcw,
  XCircle,
} from 'lucide-react';
import { lazy, Suspense, useState } from 'react';
import type { VerificationResult } from '@/api/types';
import { StatusBadge } from '@/components/StatusBadge';

// Code splitting at component level: fetched the first time a report renders.
const MarkdownReport = lazy(() => import('./MarkdownReport'));

function downloadMarkdown(markdown: string, title: string) {
  const slug =
    title
      .replace(/[^a-z0-9-]+/gi, '_')
      .slice(0, 65)
      .toLowerCase() || 'report';
  const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `verification_${slug}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const modelLabel = (mode: VerificationResult['verification_mode']) =>
  mode === 'thorough' ? 'Gemini · Super mode' : mode === 'standard' ? 'Gemini · Standard' : 'Gemini';

/** onNewSearch is optional: the Verify page passes it; the saved-record dialog has its own close button. */
export function ResultView({
  result,
  onNewSearch,
}: {
  result: VerificationResult;
  onNewSearch?: () => void;
}) {
  const [showFields, setShowFields] = useState(false);
  const { article_title, query, status, matches, fields, report_markdown, image_url, source_url } = result;
  const title = article_title || query || 'Search result';
  const fieldEntries = Object.entries(fields ?? {});

  return (
    <section className="results-block" aria-live="polite">
      <div className="section-title-row">
        <div>
          <div className="overline">VERIFICATION OUTPUT</div>
          <h2>Analysis result</h2>
          <p>Source information, model verdict and the generated report.</p>
        </div>
        {onNewSearch && (
          <button type="button" className="outline-button" onClick={onNewSearch}>
            <RotateCcw size={16} aria-hidden="true" /> New search
          </button>
        )}
      </div>
      <div className="result-card">
        <div className="result-topline">
          <div>
            <span className="micro-label">WIKIPEDIA ARTICLE</span>
            <h3>{title}</h3>
            <p>Search query: {query}</p>
          </div>
          <StatusBadge status={status} matches={matches} />
        </div>
        {status !== 'SUCCESS' ? (
          <div className="alert alert-danger">
            <AlertTriangle size={17} aria-hidden="true" /> This search couldn&rsquo;t be completed.{' '}
            {result.error_message || 'Please try again.'}
          </div>
        ) : (
          <>
            <div className="result-grid">
              <div className="image-card">
                <div className="image-card-head">
                  <ImageIcon size={17} aria-hidden="true" />
                  <span>ARTICLE IMAGE</span>
                </div>
                {image_url ? (
                  <img
                    className="article-img"
                    src={image_url}
                    alt={`Illustration from Wikipedia article: ${title}`}
                    loading="lazy"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="no-image">
                    <ImageIcon size={29} aria-hidden="true" />
                    <span>No image URL available</span>
                  </div>
                )}
                {image_url && (
                  <a className="image-source" href={image_url} target="_blank" rel="noopener noreferrer">
                    View image source <ArrowUpRight size={14} aria-hidden="true" />
                  </a>
                )}
              </div>
              <div className="analysis-card">
                <div className="analysis-header">
                  <span className="micro-label">AI VERIFICATION</span>
                  <span className="model-label">{modelLabel(result.verification_mode)}</span>
                </div>
                <div className={`verdict ${matches ? 'verdict-pass' : 'verdict-fail'}`}>
                  <span className="verdict-icon" aria-hidden="true">
                    {matches ? <CheckCircle2 size={26} /> : <XCircle size={26} />}
                  </span>
                  <div>
                    <strong>{matches ? 'Image matches article' : 'Image does not match'}</strong>
                    <p>The verification pipeline returned a {matches ? 'positive' : 'negative'} match.</p>
                  </div>
                </div>
                {result.needs_review && (
                  <div className="review-note" role="note">
                    <AlertTriangle size={16} aria-hidden="true" />
                    <div>
                      <strong>Needs review</strong>
                      <p>
                        {result.review_reason ||
                          "The visual verdict and Wikipedia's image labels disagree. Check the image yourself."}
                      </p>
                    </div>
                  </div>
                )}
                <div className="infobox-preview">
                  <span className="micro-label">ARTICLE METADATA</span>
                  {fieldEntries.length ? (
                    fieldEntries.slice(0, 3).map(([key, value]) => (
                      <div className="infobox-row" key={key}>
                        <span>{key.replaceAll('_', ' ')}</span>
                        <strong>{String(value).replace(/\s+/g, ' ').slice(0, 160)}</strong>
                      </div>
                    ))
                  ) : (
                    <p className="muted" style={{ margin: '12px 0' }}>
                      No structured infobox fields were returned.
                    </p>
                  )}
                </div>
                {fieldEntries.length > 3 && (
                  <button
                    type="button"
                    className="text-link"
                    aria-expanded={showFields}
                    onClick={() => setShowFields(v => !v)}
                  >
                    {showFields ? 'Hide all fields' : `View all ${fieldEntries.length} infobox fields`}{' '}
                    <ChevronDown size={15} aria-hidden="true" />
                  </button>
                )}
                {source_url && (
                  <a className="text-link" href={source_url} target="_blank" rel="noopener noreferrer">
                    View Wikipedia article <ArrowUpRight size={15} aria-hidden="true" />
                  </a>
                )}
              </div>
            </div>
            {showFields && (
              <div className="all-fields">
                {fieldEntries.map(([key, value]) => (
                  <div key={key}>
                    <strong>{key.replaceAll('_', ' ')}</strong>
                    <p>{String(value)}</p>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
      {report_markdown && (
        <div className="report-section">
          <div className="report-head">
            <div>
              <span className="report-icon" aria-hidden="true">
                <FileText size={20} />
              </span>
              <div>
                <h3>Verification report</h3>
                <p>Generated Markdown document</p>
              </div>
            </div>
            <button
              type="button"
              className="outline-button"
              onClick={() => downloadMarkdown(report_markdown, title)}
            >
              <Download size={16} aria-hidden="true" /> Download .md
            </button>
          </div>
          <div className="report-markdown">
            <Suspense fallback={<p className="muted">Loading report…</p>}>
              <MarkdownReport markdown={report_markdown} />
            </Suspense>
          </div>
        </div>
      )}
    </section>
  );
}
