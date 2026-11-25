import { useEffect, useLayoutEffect, useState, type RefObject } from 'react';

const GAP = 8;

export interface PopoverPosition {
  left: number;
  width: number;
  maxHeight: number;
  top?: number;
  bottom?: number;
  up: boolean;
}

interface Options {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  popupRef: RefObject<HTMLElement | null>;
  onOutside: () => void;
  maxHeight?: number;
  minHeight?: number;
}

/**
 * Places a fixed-position popup (portalled to <body>) under its anchor, or
 * above it when there's no room. Follows scroll/resize; reports outside clicks.
 * useLayoutEffect: measure and position BEFORE the browser paints, so no flicker.
 */
export function usePopover({
  open,
  anchorRef,
  popupRef,
  onOutside,
  maxHeight = 340,
  minHeight = 140,
}: Options) {
  const [pos, setPos] = useState<PopoverPosition | null>(null);

  useLayoutEffect(() => {
    if (!open) return undefined;
    function place() {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (!rect) return;
      const below = window.innerHeight - rect.bottom - GAP * 2;
      const above = rect.top - GAP * 2;
      const up = below < Math.min(maxHeight, 200) && above > below;
      setPos({
        left: rect.left,
        width: rect.width,
        maxHeight: Math.max(minHeight, Math.min(maxHeight, up ? above : below)),
        ...(up ? { bottom: window.innerHeight - rect.top + GAP } : { top: rect.bottom + GAP }),
        up,
      });
    }
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
      setPos(null);
    };
  }, [open, anchorRef, maxHeight, minHeight]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!anchorRef.current?.contains(target) && !popupRef.current?.contains(target)) onOutside();
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open, anchorRef, popupRef, onOutside]);

  return pos;
}
