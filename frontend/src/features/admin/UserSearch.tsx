import { Check, Search, X } from 'lucide-react';
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import type { User } from '@/api/types';
import { usePopover } from '@/components/usePopover';
import { displayName, errorText } from '@/lib/format';
import { useDebouncedValue } from '@/lib/useDebouncedValue';
import { useUserSearch } from './queries';
import '@/styles/select.css';

interface UserSearchProps {
  id: string;
  selected: User | null;
  onChange: (user: User | null) => void;
  renderUser: (user: User) => ReactNode;
  placeholder?: string;
  emptyText?: string;
}

/**
 * Account picker (ARIA combobox, list autocomplete). Matching runs on the
 * server via useUserSearch; debouncing + query keys replace the old manual
 * request counters, and TanStack Query cancels/ignores outdated answers.
 */
export function UserSearch({
  id,
  selected,
  onChange,
  renderUser,
  placeholder = 'Search…',
  emptyText = 'No matches',
}: UserSearchProps) {
  const selectedLabel = selected ? displayName(selected) : '';
  const [query, setQuery] = useState(selectedLabel);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const anchorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const listId = useId();

  // Keep the field in sync when the selection changes (or is renamed).
  // "Adjusting state on prop change" without an effect: compare during render.
  const [syncedLabel, setSyncedLabel] = useState(selectedLabel);
  if (syncedLabel !== selectedLabel) {
    setSyncedLabel(selectedLabel);
    setQuery(selectedLabel);
  }

  const term = query.trim();
  const searching = term !== '' && query !== selectedLabel;
  const debounced = useDebouncedValue(searching ? term : '', 300);
  const result = useUserSearch(debounced);
  const waiting = searching && (debounced !== term || result.isFetching);
  const results = searching && !result.error ? (result.data?.items ?? []) : [];
  const showPopup = open && searching;

  const revert = useCallback(() => {
    setOpen(false);
    setQuery(selectedLabel);
  }, [selectedLabel]);

  const pos = usePopover({
    open: showPopup,
    anchorRef,
    popupRef,
    onOutside: revert,
    maxHeight: 320,
    minHeight: 72,
  });

  useEffect(() => {
    if (pos && active >= 0) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' });
  }, [pos, active]);

  function choose(index: number) {
    const user = results[index];
    if (!user || waiting) return; // don't pick from a list that is being replaced
    onChange(user);
    setQuery(displayName(user));
    setOpen(false);
  }

  function clear() {
    onChange(null);
    setQuery('');
    setOpen(false);
    inputRef.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent) {
    const last = results.length - 1;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (!showPopup) {
          if (searching) setOpen(true);
          return;
        }
        setActive(i => Math.min(last, i + 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (showPopup) setActive(i => Math.max(0, i - 1));
        break;
      case 'Enter':
        event.preventDefault(); // never submit the surrounding form from the search box
        if (showPopup) choose(active);
        break;
      case 'Escape':
        if (showPopup || query !== selectedLabel) {
          event.preventDefault();
          revert();
        }
        break;
      case 'Tab':
        if (showPopup) revert();
        break;
      default:
    }
  }

  const activeId = showPopup && !waiting && results[active] ? `${listId}-${active}` : undefined;
  const status =
    (result.error && errorText(result.error, 'Search failed.')) ||
    (waiting && !results.length ? 'Searching…' : '') ||
    (!waiting && !results.length ? `${emptyText} “${term}”` : '') ||
    (result.data?.hasMore ? `Showing the first ${results.length}. Keep typing to narrow it down.` : '');

  return (
    <div className={`ui-search${showPopup ? ' is-open' : ''}`} ref={anchorRef}>
      <Search size={16} className="ui-search-icon" aria-hidden="true" />
      <input
        ref={inputRef}
        id={id}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={showPopup}
        aria-controls={listId}
        aria-activedescendant={activeId}
        aria-busy={waiting}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        maxLength={100}
        value={query}
        onChange={event => {
          const value = event.target.value;
          setQuery(value);
          setActive(0);
          setOpen(true);
          if (!value.trim() && selected) onChange(null); // emptying the field drops the selection
        }}
        onFocus={event => event.target.select()}
        onKeyDown={onKeyDown}
      />
      {(query || selected) && (
        <button
          type="button"
          className="ui-select-clear ui-search-clear"
          aria-label="Clear selection"
          onClick={clear}
        >
          <X size={15} />
        </button>
      )}

      {showPopup &&
        pos &&
        createPortal(
          <div
            ref={popupRef}
            className={`ui-select-popup${pos.up ? ' is-up' : ''}`}
            style={{
              left: pos.left,
              width: pos.width,
              top: pos.top,
              bottom: pos.bottom,
              maxHeight: pos.maxHeight,
            }}
          >
            <ul
              className={`ui-select-list${waiting ? ' is-refreshing' : ''}`}
              role="listbox"
              id={listId}
              ref={listRef}
              tabIndex={-1}
            >
              {results.map((user, index) => (
                // Keyboard handling is on the combobox input (ARIA pattern).
                // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                <li
                  key={user.id}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={user.id === selected?.id}
                  className={`ui-select-option${index === active ? ' is-active' : ''}${user.id === selected?.id ? ' is-selected' : ''}`}
                  onPointerEnter={() => setActive(index)}
                  onPointerDown={event => event.preventDefault()}
                  onClick={() => choose(index)}
                >
                  <span className="ui-select-option-body">{renderUser(user)}</span>
                  {user.id === selected?.id && (
                    <Check size={16} className="ui-select-check" aria-hidden="true" />
                  )}
                </li>
              ))}
            </ul>
            <p
              className={`ui-select-status${result.error ? ' is-error' : ''}`}
              role="status"
              aria-live="polite"
            >
              {status}
            </p>
          </div>,
          document.body,
        )}
    </div>
  );
}
