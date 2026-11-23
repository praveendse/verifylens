import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Search, X } from 'lucide-react';
import usePopover from './usePopover';
import './select.css';

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Search-only account picker (ARIA combobox with list autocomplete).
 * Matching happens on the server: the request is sent once typing pauses for
 * SEARCH_DEBOUNCE_MS, and answers to older queries are ignored.
 *
 * search(query) => Promise<{ items: Option[], hasMore: boolean }>
 *   Option = { value: string, label: string, render: () => ReactNode }
 * selected: the chosen Option, or null.  onChange(Option | null).
 */
export default function UserSearch({ id, search, selected, onChange, placeholder = 'Search…', emptyText = 'No matches', disabled = false }) {
  const selectedLabel = selected?.label ?? '';
  const [query, setQuery] = useState(selectedLabel);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [results, setResults] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const requestId = useRef(0);
  const anchorRef = useRef(null);
  const inputRef = useRef(null);
  const popupRef = useRef(null);
  const listRef = useRef(null);
  const listId = useId();

  // Show the chosen account's name in the field; also resync if it is renamed.
  useEffect(() => { setQuery(selectedLabel); }, [selected?.value, selectedLabel]);

  // Searching is active only when the text differs from the current selection.
  const term = query.trim();
  const searching = term !== '' && query !== selectedLabel;

  useEffect(() => {
    const req = ++requestId.current; // also cancels any answer still on its way
    if (!searching) { setResults([]); setHasMore(false); setLoading(false); setError(''); return undefined; }
    setLoading(true); setError('');
    const timer = setTimeout(async () => {
      try {
        const page = await search(term);
        if (req !== requestId.current) return;
        setResults(page.items); setHasMore(page.hasMore); setActive(0);
      } catch (err) {
        if (req !== requestId.current) return;
        setResults([]); setHasMore(false); setError(err?.message || 'Search failed.');
      } finally {
        if (req === requestId.current) setLoading(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [term, searching, search]);

  const showPopup = open && searching;

  // Leaving the field without picking restores the selected name (or empties it).
  const revert = useCallback(() => {
    setOpen(false);
    setQuery(selectedLabel);
  }, [selectedLabel]);

  const pos = usePopover({ open: showPopup, anchorRef, popupRef, onOutside: revert, maxHeight: 320, minHeight: 72 });

  useEffect(() => {
    if (pos && active >= 0) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' });
  }, [pos, active]);

  function choose(index) {
    const item = results[index];
    if (!item || loading) return; // don't pick from a list that is being replaced
    onChange(item);
    setQuery(item.label);
    setOpen(false);
  }

  function clear() {
    onChange(null);
    setQuery('');
    setOpen(false);
    inputRef.current?.focus();
  }

  function onKeyDown(event) {
    const last = results.length - 1;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (!showPopup) { if (searching) setOpen(true); return; }
        setActive(i => Math.min(last, i + 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (showPopup) setActive(i => Math.max(0, i - 1));
        break;
      case 'Enter':
        // Never submit the edit form from the search box.
        event.preventDefault();
        if (showPopup) choose(active);
        break;
      case 'Escape':
        if (showPopup || query !== selectedLabel) { event.preventDefault(); revert(); }
        break;
      case 'Tab':
        if (showPopup) revert();
        break;
      default:
    }
  }

  const activeId = showPopup && !loading && results[active] ? `${listId}-${active}` : undefined;
  const status = error
    || (loading && !results.length ? 'Searching…' : '')
    || (!loading && !results.length ? `${emptyText} “${term}”` : '')
    || (hasMore ? `Showing the first ${results.length}. Keep typing to narrow it down.` : '');

  return (
    <div className={`ui-search${disabled ? ' is-disabled' : ''}${showPopup ? ' is-open' : ''}`} ref={anchorRef}>
      <Search size={16} className="ui-search-icon" aria-hidden="true"/>
      <input
        ref={inputRef}
        id={id}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showPopup}
        aria-controls={listId}
        aria-activedescendant={activeId}
        aria-busy={loading}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        disabled={disabled}
        maxLength={100}
        value={query}
        onChange={event => { setQuery(event.target.value); setActive(0); setOpen(true); }}
        onFocus={event => event.target.select()}
        onKeyDown={onKeyDown}
      />
      {(query || selected) && !disabled && (
        <button type="button" className="ui-select-clear ui-search-clear" aria-label="Clear selection" onClick={clear}>
          <X size={15}/>
        </button>
      )}

      {showPopup && pos && createPortal(
        <div
          ref={popupRef}
          className={`ui-select-popup${pos.up ? ' is-up' : ''}`}
          style={{ left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom, maxHeight: pos.maxHeight }}
        >
          <ul className={`ui-select-list${loading ? ' is-refreshing' : ''}`} role="listbox" id={listId} ref={listRef} tabIndex={-1}>
            {results.map((item, index) => (
              <li
                key={item.value}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={item.value === selected?.value}
                className={`ui-select-option${index === active ? ' is-active' : ''}${item.value === selected?.value ? ' is-selected' : ''}`}
                onPointerEnter={() => setActive(index)}
                onPointerDown={event => event.preventDefault()}
                onClick={() => choose(index)}
              >
                <span className="ui-select-option-body">{item.render()}</span>
                {item.value === selected?.value && <Check size={16} className="ui-select-check" aria-hidden="true"/>}
              </li>
            ))}
          </ul>
          <p className={`ui-select-status${error ? ' is-error' : ''}`} role="status" aria-live="polite">{status}</p>
        </div>,
        document.body,
      )}
    </div>
  );
}
