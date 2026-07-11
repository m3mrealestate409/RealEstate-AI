// PropX Estate brand assets — recreated as crisp SVG (gold wordmark + monogram).
// Gradient IDs are made UNIQUE per instance (useId) — the monogram renders twice
// on a page (mobile top bar + sidebar), and duplicate SVG gradient IDs make the
// browser resolve the wrong one, blanking out the logo.
import { useId } from "react";

const GOLD_STOPS = (
  <>
    <stop offset="0%" stopColor="#B87A1C" />
    <stop offset="45%" stopColor="#F7DE8B" />
    <stop offset="100%" stopColor="#C8901E" />
  </>
);

// Small square app-icon monogram (sidebar, login).
export function BrandMark({ size = 40 }) {
  const uid = useId().replace(/:/g, "");
  const gold = `pxGoldMark-${uid}`;
  const bg = `pxBgMark-${uid}`;
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="PropX Estate">
      <defs>
        <linearGradient id={gold} x1="0" y1="0" x2="1" y2="1">{GOLD_STOPS}</linearGradient>
        <linearGradient id={bg} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#20242f" />
          <stop offset="100%" stopColor="#12151d" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill={`url(#${bg})`} />
      <text x="24" y="32" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif"
        fontWeight="700" fontSize="21" letterSpacing="0.5" fill={`url(#${gold})`}>PX</text>
    </svg>
  );
}

// Full wordmark — "PROPX / ESTATE" stacked, matching the brand logo.
export function Wordmark({ height = 52 }) {
  const uid = useId().replace(/:/g, "");
  const gold = `pxGoldWord-${uid}`;
  return (
    <svg viewBox="0 0 240 74" height={height} fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="PropX Estate">
      <defs>
        <linearGradient id={gold} x1="0" y1="0" x2="1" y2="0.4">{GOLD_STOPS}</linearGradient>
      </defs>
      <text x="120" y="40" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif"
        fontWeight="700" fontSize="40" letterSpacing="1" fill={`url(#${gold})`}>PROPX</text>
      <text x="120" y="63" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif"
        fontWeight="600" fontSize="14" letterSpacing="10" fill={`url(#${gold})`}>ESTATE</text>
    </svg>
  );
}
