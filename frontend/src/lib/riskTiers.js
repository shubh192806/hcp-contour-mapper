/**
 * Generalized N-tier corrosion risk classification.
 *
 * A scheme is an array of tiers ordered from WORST to BEST, e.g. the default
 * 4-tier scheme (Severe / High / Uncertain / Low) reproduces the extended
 * classification table (Severe <-500mV, High -500 to -350mV, Uncertain -350
 * to -200mV, Low >-200mV, CSE electrode) on top of the plain 3-tier ASTM
 * C876 scheme (High / Uncertain / Low at -350/-200mV) we started with.
 *
 * Each tier has a `boundary`: the mV value below which this tier applies.
 * The last (best) tier's boundary is null — it's whatever's left over once
 * every worse tier's threshold is passed, i.e. "greater than the previous
 * tier's boundary." This is what makes the scheme generalize to any number
 * of tiers: adding one is just inserting another boundary into the ladder,
 * not redefining a fixed set of named buckets.
 */

export const DEFAULT_TIERS_4 = [
  { id: "severe", label: "Severe corrosion", color: "#6b0f14", boundary: -500 },
  { id: "high", label: "High risk", color: "#b3261e", boundary: -350 },
  { id: "uncertain", label: "Uncertain", color: "#c77800", boundary: -200 },
  { id: "low", label: "Low risk", color: "#2e7d32", boundary: null },
];

export const DEFAULT_TIERS_3 = [
  { id: "high", label: "High risk", color: "#b3261e", boundary: -350 },
  { id: "uncertain", label: "Uncertain", color: "#c77800", boundary: -200 },
  { id: "low", label: "Low risk", color: "#2e7d32", boundary: null },
];

/** Returns the tier object a value falls into, given tiers ordered worst->best. */
export function classify(value, tiers) {
  for (let i = 0; i < tiers.length - 1; i++) {
    if (value < tiers[i].boundary) return tiers[i];
  }
  return tiers[tiers.length - 1];
}

/**
 * Builds an explicit Plotly colorscale with hard transitions at each tier
 * boundary, positioned against the SAME [zmin, zmax] domain Plotly will
 * actually render the contour against (the rounded contour-line range, not
 * the raw data min/max — using the wrong domain here is what caused the
 * thresholds to render in the wrong place previously).
 *
 * Boundary positions are clamped into a monotonically non-decreasing
 * sequence rather than re-sorting the tiers themselves, so a tier keeps its
 * assigned color even if its boundary is temporarily out of order mid-edit
 * (Plotly throws on out-of-order colorscale stops otherwise).
 */
export function buildRiskColorscale(zmin, zmax, tiers) {
  const span = zmax - zmin || 1;
  const clamp = (v) => Math.min(1, Math.max(0, v));

  const positions = [];
  let prev = 0;
  for (let i = 0; i < tiers.length - 1; i++) {
    const pos = Math.max(clamp((tiers[i].boundary - zmin) / span), prev);
    positions.push(pos);
    prev = pos;
  }

  const stops = [[0, tiers[0].color]];
  for (let i = 0; i < positions.length; i++) {
    stops.push([positions[i], tiers[i].color]);
    stops.push([positions[i], tiers[i + 1].color]);
  }
  stops.push([1, tiers[tiers.length - 1].color]);
  return stops;
}

/** Human-readable range text for tier `i` in an ordered worst->best array. */
export function tierRangeText(tiers, i) {
  const prevBoundary = i > 0 ? tiers[i - 1].boundary : null;
  const boundary = tiers[i].boundary;
  if (prevBoundary === null && boundary !== null) return `< ${boundary} mV`;
  if (boundary === null) return `> ${prevBoundary} mV`;
  return `${prevBoundary} to ${boundary} mV`;
}

const NEUTRAL_COLORS = ["#6b6b6b", "#7d5ba6", "#1b6e6e", "#8a5a2b"];

/** Adds a new worst-case tier beyond the current worst, mirroring how the
 * reference table extends plain ASTM C876 with an additional "Severe" band. */
export function addWorstTier(tiers) {
  const currentWorst = tiers[0];
  const newBoundary = (currentWorst.boundary ?? 0) - 100;
  const color = NEUTRAL_COLORS[tiers.length % NEUTRAL_COLORS.length];
  const newTier = { id: `tier-${Date.now()}`, label: "New tier", color, boundary: newBoundary };
  return [newTier, ...tiers];
}

/** Removes a tier by id. If the removed tier was the last (best) one, the
 * new last tier becomes the catch-all (boundary -> null). No-op below 2 tiers. */
export function removeTier(tiers, id) {
  if (tiers.length <= 2) return tiers;
  const idx = tiers.findIndex((t) => t.id === id);
  if (idx === -1) return tiers;
  const next = tiers.filter((t) => t.id !== id);
  if (idx === tiers.length - 1) {
    next[next.length - 1] = { ...next[next.length - 1], boundary: null };
  }
  return next;
}
