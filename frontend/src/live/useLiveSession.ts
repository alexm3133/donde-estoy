/**
 * Viewer-side live data: initial load over HTTP, then a WebSocket that
 * reconnects by itself (phones sleep, trains enter tunnels).
 */
import { useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import type { LiveMessage, SessionView, Snapshot } from "../api/types";

export type LinkState = "loading" | "live" | "reconnecting" | "not_found" | "error";

export interface LiveSession {
  link: LinkState;
  view: SessionView | null;
  /** Add to `Date.now()` to get server time (cancels a wrong device clock). */
  clockOffsetMs: number;
}

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 15_000;
const WS_CLOSE_NOT_FOUND = 4404;

/** Merge a pushed snapshot into the view, extending the track. */
function applySnapshot(view: SessionView, snapshot: Snapshot): SessionView {
  if (snapshot.state === "ended") {
    return { ...view, ...snapshot, route: null, track: [] }; // location data is gone
  }
  let track = view.track;
  const position = snapshot.position;
  const last = track[track.length - 1];
  if (position && (!last || last[0] !== position.lat || last[1] !== position.lon)) {
    track = [...track, [position.lat, position.lon]];
  }
  return { ...view, ...snapshot, track };
}

export function useLiveSession(token: string): LiveSession {
  const [state, setState] = useState<LiveSession>({
    link: "loading",
    view: null,
    clockOffsetMs: 0,
  });

  useEffect(() => {
    let closed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let retryDelay = RECONNECT_MIN_MS;

    const offsetOf = (snapshot: Snapshot) => new Date(snapshot.server_time).getTime() - Date.now();

    const scheduleReconnect = () => {
      if (closed) return;
      setState((current) => (current.view ? { ...current, link: "reconnecting" } : current));
      retryTimer = window.setTimeout(connect, retryDelay);
      retryDelay = Math.min(RECONNECT_MAX_MS, retryDelay * 2);
    };

    const openSocket = () => {
      socket = new WebSocket(api.liveUrl(token));
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as LiveMessage;
        if (message.type === "snapshot") {
          retryDelay = RECONNECT_MIN_MS;
          setState((current) =>
            current.view
              ? {
                  link: "live",
                  view: applySnapshot(current.view, message.data),
                  clockOffsetMs: offsetOf(message.data),
                }
              : current,
          );
        } else if (message.type === "expired") {
          closed = true;
          setState({ link: "not_found", view: null, clockOffsetMs: 0 });
        }
      };
      socket.onclose = (event) => {
        if (closed) return;
        if (event.code === WS_CLOSE_NOT_FOUND) {
          closed = true;
          setState({ link: "not_found", view: null, clockOffsetMs: 0 });
          return;
        }
        scheduleReconnect();
      };
    };

    // Every (re)connection starts with a full reload, so nothing that
    // happened while disconnected is missed.
    async function connect() {
      if (closed) return;
      try {
        const view = await api.view(token);
        if (closed) return;
        setState({ link: "live", view, clockOffsetMs: offsetOf(view) });
        openSocket();
      } catch (error) {
        if (closed) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ link: "not_found", view: null, clockOffsetMs: 0 });
          return;
        }
        setState((current) => (current.view ? current : { ...current, link: "error" }));
        scheduleReconnect();
      }
    }

    void connect();

    // Coming back to the tab: reconnect right away instead of waiting.
    const onVisible = () => {
      if (document.visibilityState !== "visible" || closed) return;
      if (!socket || socket.readyState === WebSocket.CLOSED) {
        window.clearTimeout(retryTimer);
        retryDelay = RECONNECT_MIN_MS;
        void connect();
      }
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      closed = true;
      window.clearTimeout(retryTimer);
      document.removeEventListener("visibilitychange", onVisible);
      socket?.close();
    };
  }, [token]);

  return state;
}
