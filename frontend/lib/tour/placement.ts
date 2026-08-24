export interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface TooltipPosition {
  top: number;
  left: number;
  side: "top" | "bottom" | "left" | "right";
}

const GAP = 12;
const PADDING = 16;

/**
 * Picks where the tooltip card goes relative to the spotlighted rect: tries
 * bottom, then top, then right, then left — the first that actually fits the
 * viewport — and clamps the final position so the card never runs off-screen
 * even when nothing fits cleanly. Hand-rolled rather than a positioning
 * library: one target at a time, no scroll-parent/portal cases to handle,
 * and it's the only thing in this codebase that would have needed one.
 */
export function placeTooltip(
  target: Rect,
  tooltip: { width: number; height: number },
  viewport: { width: number; height: number }
): TooltipPosition {
  const spaceBottom = viewport.height - (target.top + target.height);
  const spaceTop = target.top;
  const spaceRight = viewport.width - (target.left + target.width);
  const spaceLeft = target.left;

  const fitsBottom = spaceBottom >= tooltip.height + GAP;
  const fitsTop = spaceTop >= tooltip.height + GAP;
  const fitsRight = spaceRight >= tooltip.width + GAP;
  const fitsLeft = spaceLeft >= tooltip.width + GAP;

  let side: TooltipPosition["side"];
  if (fitsBottom) side = "bottom";
  else if (fitsTop) side = "top";
  else if (fitsRight) side = "right";
  else if (fitsLeft) side = "left";
  // Nothing fits cleanly (a tiny viewport, or a target near a corner) — fall
  // back to whichever side has the most room rather than picking arbitrarily.
  else {
    const max = Math.max(spaceBottom, spaceTop, spaceRight, spaceLeft);
    side = max === spaceBottom ? "bottom" : max === spaceTop ? "top" : max === spaceRight ? "right" : "left";
  }

  let top: number;
  let left: number;
  const centerX = target.left + target.width / 2;
  const centerY = target.top + target.height / 2;

  switch (side) {
    case "bottom":
      top = target.top + target.height + GAP;
      left = centerX - tooltip.width / 2;
      break;
    case "top":
      top = target.top - tooltip.height - GAP;
      left = centerX - tooltip.width / 2;
      break;
    case "right":
      top = centerY - tooltip.height / 2;
      left = target.left + target.width + GAP;
      break;
    case "left":
      top = centerY - tooltip.height / 2;
      left = target.left - tooltip.width - GAP;
      break;
  }

  top = Math.min(Math.max(top, PADDING), viewport.height - tooltip.height - PADDING);
  left = Math.min(Math.max(left, PADDING), viewport.width - tooltip.width - PADDING);

  return { top, left, side };
}
