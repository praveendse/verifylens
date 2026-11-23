import { useState } from 'react';
import { AlertTriangle, ArrowUpRight, CheckCircle2, ChevronDown, ChevronRight, Download, FileText, Image as ImageIcon, Link2, RotateCcw, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function StatusBadge({ status, matches, compact = false }) {
  if (status === 'ERROR') return <span className={`status-badge status-error ${compact ? 'status-compact' : ''}`}><XCircle size={13}/> Error</span>;
  if (status === 'PENDING') return <span className={`status-badge status-pending ${compact ? 'status-compact' : ''}`}>Processing</span>;
  if (status === 'SUCCESS' && matches === false) return <span className={`status-badge status-error ${compact ? 'status-compact' : ''}`}><XCircle size={13}/> No match</span>;
  if (status === 'SUCCESS' && matches === true) return <span className={`status-badge status-success ${compact ? 'status-compact' : ''}`}><CheckCircle2 size={13}/> Match verified</span>;
  return <span className="status-badge status-pending">{status || 'Unknown'}</span>;
}

function downloadMarkdown(markdown, title) {
  const filename = `verification_${String(title || 'report').replace(/[^a-z0-9-]+/gi, '_').slice(0, 65).toLowerCase()}.md`;
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* onClear is optional: the Verify page passes it ("New search"); the history
   detail view does not, since it has its own close button. */
export default function ResultView({ result, isDemo = false, onClear }) {
  const [showFields, setShowFields] = useState(false);
  if (!result) return null;
  const { article_title, query, status, matches, fields, report_markdown, image_url, source_url } = result;
  const title = article_title || query || 'Search result';
  const fieldEntries = Object.entries(fields && typeof fields === 'object' ? fields : {});

  return (
    <section className="results-block" aria-live="polite">
      <div className="section-title-row"><div><div className="overline">VERIFICATION OUTPUT</div><h2>Analysis result</h2><p>Source information, model verdict and the generated report.</p></div>{onClear && <button type="button" className="outline-button" onClick={onClear}><RotateCcw size={16}/> New search</button>}</div>
      <div className="result-card">
        <div className="result-topline"><div><span className="micro-label">WIKIPEDIA ARTICLE</span><h3>{title}</h3><p>Search query: {query}</p></div><StatusBadge status={status} matches={matches}/></div>
        {status !== 'SUCCESS' ? (
          <div className="alert alert-danger"><AlertTriangle size={17}/> This attempt did not complete successfully. {result.error_message || 'Check the backend logs for details.'}</div>
        ) : (
          <>
            <div className="result-grid">
              <div className="image-card">
                <div className="image-card-head"><ImageIcon size={17}/><span>ARTICLE IMAGE</span></div>
                {image_url ? <img className="article-img" src={image_url} alt={`Illustration from Wikipedia article: ${title}`} loading="lazy" referrerPolicy="no-referrer" /> : <div className="no-image"><ImageIcon size={29}/><span>No image URL available</span></div>}
                {image_url && <a className="image-source" href={image_url} target="_blank" rel="noopener noreferrer">View image source <ArrowUpRight size={14}/></a>}
              </div>
              <div className="analysis-card">
                <div className="analysis-header"><span className="micro-label">AI VERIFICATION</span><span className="model-label">Gemini</span></div>
                <div className={`verdict ${matches ? 'verdict-pass' : 'verdict-fail'}`}><span className="verdict-icon">{matches ? <CheckCircle2 size={26}/> : <XCircle size={26}/>}</span><div><strong>{matches ? 'Image matches article' : 'Image does not match'}</strong><p>{matches ? 'The verification pipeline returned a positive match.' : 'The verification pipeline returned a negative match.'}</p></div></div>
                <div className="infobox-preview"><span className="micro-label">ARTICLE METADATA</span>{fieldEntries.length ? fieldEntries.slice(0, 3).map(([key, value]) => <div className="infobox-row" key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{String(value).replace(/\s+/g, ' ').slice(0, 160)}</strong></div>) : <p className="muted" style={{margin:'12px 0'}}>No structured infobox fields were returned.</p>}</div>
                {fieldEntries.length > 3 && <button type="button" className="text-link" onClick={() => setShowFields(v => !v)}>{showFields ? 'Hide all fields' : `View all ${fieldEntries.length} infobox fields`} <ChevronDown size={15}/></button>}
                {source_url && <a className="text-link" href={source_url} target="_blank" rel="noopener noreferrer">View Wikipedia article <ArrowUpRight size={15}/></a>}
              </div>
            </div>
            {showFields && <div className="all-fields">{fieldEntries.map(([key, value]) => <div key={key}><strong>{key.replaceAll('_', ' ')}</strong><p>{String(value)}</p></div>)}</div>}
          </>
        )}
      </div>
      {report_markdown && <div className="report-section"><div className="report-head"><div><span className="report-icon"><FileText size={20}/></span><div><h3>Verification report</h3><p>Generated Markdown document</p></div></div><button className="outline-button" onClick={() => downloadMarkdown(report_markdown, title)}><Download size={16}/> Download .md</button></div><div className="report-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]}>{report_markdown}</ReactMarkdown></div></div>}
      {isDemo && <p className="muted demo-hint">Demo results are illustrative and do not represent a real AI verdict.</p>}
    </section>
  );
}
