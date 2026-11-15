/**
 * Elevation profile of the route with a "you are here" marker.
 * Hand-rolled SVG: one area path, no chart library needed.
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Route } from "../api/types";
import { formatClimb, formatDistance } from "../domain/format";
import "./ElevationProfile.css";

const WIDTH = 600;
const HEIGHT = 120;
const MAX_SAMPLES = 240;

interface Props {
  route: Route;
  /** Distance covered so far, or null before the runner starts. */
  progressM: number | null;
}

export function ElevationProfile({ route, progressM }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const { areaPath, linePath, yAt, min, max } = useMemo(() => {
    const stride = Math.max(1, Math.ceil(route.points.length / MAX_SAMPLES));
    const samples = route.points.filter(
      (_, index) => index % stride === 0 || index === route.points.length - 1,
    );
    const elevations = samples.map((point) => point[2]);
    const lowest = Math.min(...elevations);
    const highest = Math.max(...elevations);
    // Leave headroom so the line never touches the top edge, and give flat
    // routes a sensible minimum span.
    const span = Math.max(highest - lowest, 40);
    const x = (distance: number) => (distance / route.distance_m) * WIDTH;
    const y = (elevation: number) => HEIGHT - 6 - ((elevation - lowest) / span) * (HEIGHT - 22);
    const outline = samples
      .map((point, index) => `${index ? "L" : "M"}${x(point[3]).toFixed(1)},${y(point[2]).toFixed(1)}`)
      .join(" ");

    const elevationAt = (distance: number) => {
      let i = 1;
      while (i < samples.length - 1 && samples[i][3] < distance) i++;
      const [a, b] = [samples[i - 1], samples[i]];
      const f = Math.min(1, Math.max(0, (distance - a[3]) / (b[3] - a[3] || 1)));
      return a[2] + f * (b[2] - a[2]);
    };

    return {
      linePath: outline,
      areaPath: `${outline} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`,
      yAt: (distance: number) => y(elevationAt(distance)),
      min: lowest,
      max: highest,
    };
  }, [route]);

  const fraction = progressM === null ? null : Math.min(1, Math.max(0, progressM / route.distance_m));
  const markerY = fraction === null ? null : yAt(fraction * route.distance_m);

  return (
    <figure className="de-profile" aria-label={t("profile.label")}>
      <div className="de-profile__chart">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="de-profile-ahead" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--de-accent)" stopOpacity="0.5" />
              <stop offset="1" stopColor="var(--de-accent)" stopOpacity="0.04" />
            </linearGradient>
            <clipPath id="de-profile-done">
              <rect x="0" y="0" width={(fraction ?? 0) * WIDTH} height={HEIGHT} />
            </clipPath>
          </defs>
          {/* What is left: accent. What is done: muted, drawn on top. */}
          <path d={areaPath} fill="url(#de-profile-ahead)" />
          <path d={linePath} className="de-profile__line" />
          <g clipPath="url(#de-profile-done)">
            <path d={areaPath} className="de-profile__done-area" />
            <path d={linePath} className="de-profile__done-line" />
          </g>
        </svg>
        {fraction !== null && markerY !== null && (
          <span
            className="de-profile__marker"
            style={{ left: `${fraction * 100}%`, top: `${(markerY / HEIGHT) * 100}%` }}
          />
        )}
      </div>
      <figcaption className="de-profile__caption">
        <span>
          {formatClimb(min, locale)} – {formatClimb(max, locale)}
        </span>
        <span>{formatDistance(route.distance_m, locale)}</span>
      </figcaption>
    </figure>
  );
}
