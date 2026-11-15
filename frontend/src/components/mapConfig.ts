/**
 * Map tiles.
 *
 * Default: OpenTopoMap — beautiful topographic tiles, free for moderate use
 * and requiring the attribution below (https://opentopomap.org/about).
 * Deployments with real traffic should point VITE_TILE_URL at their own
 * tile provider and set VITE_TILE_ATTRIBUTION accordingly.
 */
const template: string =
  import.meta.env.VITE_TILE_URL || "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png";

export const TILE_URLS = template.includes("{s}")
  ? ["a", "b", "c"].map((subdomain) => template.replace("{s}", subdomain))
  : [template];

export const TILE_MAX_ZOOM = Number(import.meta.env.VITE_TILE_MAX_ZOOM || 17);

export const TILE_ATTRIBUTION: string =
  import.meta.env.VITE_TILE_ATTRIBUTION ||
  'Map data: © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors, SRTM | ' +
    'Map style: © <a href="https://opentopomap.org" target="_blank" rel="noopener">OpenTopoMap</a> ' +
    '(<a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener">CC-BY-SA</a>)';

/** Where the map opens before it knows anything (the Pyrenees). */
export const DEFAULT_CENTER = { lat: 42.4, lon: 1.6 };
export const DEFAULT_ZOOM = 7;
