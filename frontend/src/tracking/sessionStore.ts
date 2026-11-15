/**
 * The runner's active session, remembered on this device so that reloading
 * the page (or the browser killing the tab) does not end the sharing.
 */
export interface StoredSession {
  id: string;
  /** Secret: lets this device post positions and stop the session. */
  runnerToken: string;
  viewToken: string;
  /** Share link as built by the server (fallback for native builds). */
  shareUrl: string;
  /** Positions come from the built-in simulator instead of the GPS. */
  demo: boolean;
}

const KEY = "de.session";
const NAME_KEY = "de.runnerName";

export const sessionStore = {
  load(): StoredSession | null {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? (JSON.parse(raw) as StoredSession) : null;
    } catch {
      return null;
    }
  },
  save(session: StoredSession): void {
    localStorage.setItem(KEY, JSON.stringify(session));
  },
  clear(): void {
    localStorage.removeItem(KEY);
    localStorage.removeItem(bufferKey());
  },
  /** Last name typed, to prefill the form next time. */
  loadName(): string {
    try {
      return localStorage.getItem(NAME_KEY) ?? "";
    } catch {
      return "";
    }
  },
  saveName(name: string): void {
    localStorage.setItem(NAME_KEY, name);
  },
};

/** localStorage key of the offline position buffer. */
export function bufferKey(): string {
  return "de.buffer";
}

/** The link to share. On the web it is this very origin. */
export function shareLink(session: StoredSession): string {
  return window.location.protocol.startsWith("http")
    ? `${window.location.origin}/s/${session.viewToken}`
    : session.shareUrl;
}
