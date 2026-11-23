import { useEffect, useLayoutEffect, useState } from 'react';

const GAP = 8;

/**
 * Positions a popup (rendered in a <body> portal with position: fixed) under
 * an anchor element, flipping above it when there is not enough room below.
 * Follows scroll/resize while open, and calls onOutside for pointer-downs
 * outside both the anchor and the popup.
 */
export default function usePopover({ open, anchorRef, popupRef, onOutside, maxHeight = 340, minHeight = 140 }) {
  const [pos, setPos] = useState(null);

  useLayoutEffect(() => {
    if (!open) { setPos(null); return undefined; }
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
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, anchorRef, maxHeight, minHeight]);

  useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = event => {
      if (!anchorRef.current?.contains(event.target) && !popupRef.current?.contains(event.target)) onOutside();
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open, anchorRef, popupRef, onOutside]);

  return pos;
}
