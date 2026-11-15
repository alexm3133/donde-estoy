import { useEffect, useState } from "react";
import type { MapPadding } from "../components/LiveMap";

const WIDE = "(min-width: 900px)";
const TOP_BAR = 76;

/**
 * Map padding matching the stage layout: the sheet covers the bottom on
 * phones and the left side on wide screens (see stage.css).
 */
export function useSheetPadding(sheet: { width: number; height: number }): MapPadding {
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  useEffect(() => {
    const query = window.matchMedia(WIDE);
    const onChange = () => setWide(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return wide
    ? { top: TOP_BAR, right: 0, bottom: 0, left: sheet.width + 24 }
    : { top: TOP_BAR, right: 0, bottom: sheet.height + 12, left: 0 };
}
