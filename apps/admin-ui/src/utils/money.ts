/**
 * Money formatting — Stream Z3.
 *
 * Backend billing amounts are integer *micro-USD* (1 USD = 1_000_000 micros)
 * so costs round-trip without floating-point drift. The UI renders them as
 * USD with fixed 4-decimal precision: agent token costs are frequently tiny
 * fractions of a cent, and a flat 4dp keeps small and large values visually
 * aligned in a column. Thousands separators come from ``toLocaleString``.
 *
 * Pure + side-effect free so it is trivially unit-testable.
 */

const MICROS_PER_USD = 1_000_000;
const DISPLAY_DECIMALS = 4;

/** Render an integer micro-USD amount as a ``$``-prefixed USD string with
 *  fixed 4-decimal precision and thousands separators, e.g.
 *  ``formatMicros(1_200_000) === "$1.2000"`` and
 *  ``formatMicros(0) === "$0.0000"``. Non-finite input falls back to
 *  ``"$0.0000"`` so a malformed payload never throws in render. */
export function formatMicros(micros: number): string {
  if (!Number.isFinite(micros)) {
    return `$${(0).toFixed(DISPLAY_DECIMALS)}`;
  }
  // ``+ 0`` normalizes ``-0`` (e.g. ``micros === -0``) to ``0`` so it never
  // renders as ``"$-0.0000"``.
  const usd = micros / MICROS_PER_USD + 0;
  return `$${usd.toLocaleString("en-US", {
    minimumFractionDigits: DISPLAY_DECIMALS,
    maximumFractionDigits: DISPLAY_DECIMALS,
  })}`;
}
