import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Loaded lazily (see ResultView): the Markdown parser is the biggest library in
 * the app, and nobody needs it until a report is on screen.
 * react-markdown renders React elements, never raw HTML: report text can't inject scripts.
 */
export default function MarkdownReport({ markdown }: { markdown: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>;
}
