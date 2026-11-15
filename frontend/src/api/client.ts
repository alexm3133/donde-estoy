/**
 * Thin, typed wrapper around the backend API.
 *
 * By default the API is same-origin (`/api/...`): Vite proxies it in
 * development and nginx in production. Native (Capacitor) builds have no
 * origin of their own, so they set `VITE_API_BASE=https://your.server`.
 */
import type {
  ParsedRoute,
  PositionIn,
  SessionCreate,
  SessionCreated,
  SessionView,
  Snapshot,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** An HTTP error from the API; `code` is the machine-readable `detail`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(`${status} ${code}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let code = "unknown_error";
    try {
      const body = await response.json();
      if (typeof body.detail === "string") code = body.detail;
      else if (response.status === 422) code = "invalid_request";
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code);
  }
  return (await response.json()) as T;
}

function json(body: unknown, token?: string): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  };
}

export const api = {
  parseGpx(file: File): Promise<ParsedRoute> {
    const form = new FormData();
    form.append("file", file);
    return request("/api/routes/parse", { method: "POST", body: form });
  },

  createSession(body: SessionCreate): Promise<SessionCreated> {
    return request("/api/sessions", json(body));
  },

  getOwnSession(id: string, runnerToken: string): Promise<SessionView> {
    return request(`/api/sessions/${id}`, { headers: { Authorization: `Bearer ${runnerToken}` } });
  },

  postPositions(
    id: string,
    runnerToken: string,
    positions: PositionIn[],
  ): Promise<{ accepted: number; snapshot: Snapshot }> {
    // `sent_at` lets the server cancel out a wrong device clock.
    return request(
      `/api/sessions/${id}/positions`,
      json({ positions, sent_at: new Date().toISOString() }, runnerToken),
    );
  },

  finish(id: string, runnerToken: string): Promise<Snapshot> {
    return request(`/api/sessions/${id}/finish`, json({}, runnerToken));
  },

  stop(id: string, runnerToken: string): Promise<Snapshot> {
    return request(`/api/sessions/${id}/stop`, json({}, runnerToken));
  },

  view(token: string): Promise<SessionView> {
    return request(`/api/view/${encodeURIComponent(token)}`);
  },

  /** WebSocket URL for live updates of a shared session. */
  liveUrl(token: string): string {
    const base = API_BASE || window.location.origin;
    return `${base.replace(/^http/, "ws")}/api/view/${encodeURIComponent(token)}/ws`;
  },
};
