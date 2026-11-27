import { Check, ChevronDown } from 'lucide-react';
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { usePopover } from './usePopover';
import '@/styles/select.css';

export interface SelectOption<V extends string = string> {
  value: V;
  label: string;
  render?: () => ReactNode;
}

interface SelectProps<V extends string> {
  id?: string;
  value: V;
  onChange: (value: V) => void;
  options: ReadonlyArray<SelectOption<V>>;
  placeholder?: string;
  disabled?: boolean;
  'aria-label'?: string;
}

/**
 * Themed dropdown (ARIA combobox + listbox pattern). Generic over V, so
 * <Select<Role>> only accepts and returns valid roles: types flow through.
 * Keys: Enter/Space/Arrows open; Arrows/Home/End move; Enter picks; Esc/Tab close;
 * typing jumps to a matching option.
 */
export function Select<V extends string>({
  id,
  value,
  onChange,
  options,
  placeholder = 'Select…',
  disabled = false,
  'aria-label': ariaLabel,
}: SelectProps<V>) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typeahead = useRef({ text: '', timer: 0 });
  const listId = useId();
  const selectedIndex = options.findIndex(option => option.value === value);
  const selected = options[selectedIndex];

  const dismiss = useCallback(() => setOpen(false), []);
  const pos = usePopover({
    open,
    anchorRef: rootRef,
    popupRef,
    onOutside: dismiss,
    maxHeight: 300,
    minHeight: 120,
  });

  useEffect(() => {
    if (pos && active >= 0) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' });
  }, [pos, active]);

  useEffect(() => () => clearTimeout(typeahead.current.timer), []);

  function openList() {
    if (disabled || !options.length) return;
    setActive(Math.max(0, selectedIndex));
    setOpen(true);
  }

  function close() {
    setOpen(false);
    triggerRef.current?.focus({ preventScroll: true });
  }

  function choose(index: number) {
    const option = options[index];
    if (option) onChange(option.value);
    close();
  }

  function onKeyDown(event: KeyboardEvent) {
    if (disabled) return;
    const last = options.length - 1;
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        if (!open) openList();
        else setActive(i => Math.min(last, i + 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        if (!open) openList();
        else setActive(i => Math.max(0, i - 1));
        break;
      case 'Home':
        if (open) {
          event.preventDefault();
          setActive(0);
        }
        break;
      case 'End':
        if (open) {
          event.preventDefault();
          setActive(last);
        }
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        if (open) choose(active);
        else openList();
        break;
      case 'Escape':
        if (open) {
          event.preventDefault();
          close();
        }
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          const state = typeahead.current;
          clearTimeout(state.timer);
          state.text += event.key.toLowerCase();
          state.timer = window.setTimeout(() => {
            state.text = '';
          }, 600);
          const match = options.findIndex(option => option.label.toLowerCase().startsWith(state.text));
          if (match >= 0) {
            if (!open) openList();
            setActive(match);
          }
        }
    }
  }

  return (
    <div className={`ui-select${open ? ' is-open' : ''}${disabled ? ' is-disabled' : ''}`} ref={rootRef}>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        className="ui-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label={ariaLabel}
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        disabled={disabled}
        onClick={() => (open ? close() : openList())}
        onKeyDown={onKeyDown}
      >
        <span className={`ui-select-value${selected ? '' : ' is-placeholder'}`}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown size={16} className="ui-select-chevron" aria-hidden="true" />
      </button>

      {open &&
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
            <ul className="ui-select-list" role="listbox" id={listId} ref={listRef} tabIndex={-1}>
              {options.map((option, index) => (
                // Keyboard handling lives on the combobox trigger (ARIA pattern), not on each option.
                // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                <li
                  key={option.value}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === selectedIndex}
                  className={`ui-select-option${index === active ? ' is-active' : ''}${index === selectedIndex ? ' is-selected' : ''}`}
                  onPointerEnter={() => setActive(index)}
                  onPointerDown={event => event.preventDefault()}
                  onClick={() => choose(index)}
                >
                  <span className="ui-select-option-body">
                    {option.render ? option.render() : option.label}
                  </span>
                  {index === selectedIndex && (
                    <Check size={16} className="ui-select-check" aria-hidden="true" />
                  )}
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}
    </div>
  );
}
