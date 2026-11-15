/**
 * Offline-tolerant delivery of GPS fixes to the server.
 *
 * Mountains have no coverage. Fixes go into a queue that is persisted (so a
 * page reload does not lose them) and flushed in batches whenever the network
 * allows. Order is preserved, and the server accepts late batches.
 */
import { ApiError } from "../api/client";
import type { PositionIn, Snapshot } from "../api/types";

/** Largest batch per request (the API accepts up to 500). */
export const BATCH_SIZE = 200;
/** Cap on buffered fixes (~7 h at one fix every 5 s); oldest are dropped. */
export const MAX_BUFFERED = 5000;

export type FlushResult = "sent" | "empty" | "offline" | "gone" | "busy";

export interface UploaderOptions {
  /** Sends one batch; rejects with ApiError or a network error. */
  send(batch: PositionIn[]): Promise<{ snapshot: Snapshot }>;
  storage: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  storageKey: string;
  /** Latest server state after a successful upload. */
  onSnapshot?(snapshot: Snapshot): void;
  /** The session no longer exists (expired or stopped elsewhere). */
  onGone?(): void;
  /** Queue length changed. */
  onPendingChange?(pending: number): void;
}

export class PositionUploader {
  private queue: PositionIn[];
  private flushing = false;

  constructor(private readonly options: UploaderOptions) {
    this.queue = this.restore();
  }

  get pending(): number {
    return this.queue.length;
  }

  enqueue(position: PositionIn): void {
    this.queue.push(position);
    if (this.queue.length > MAX_BUFFERED) this.queue.splice(0, this.queue.length - MAX_BUFFERED);
    this.persist();
  }

  /** Try to send everything queued. Never throws. */
  async flush(): Promise<FlushResult> {
    if (this.flushing) return "busy";
    if (this.queue.length === 0) return "empty";
    this.flushing = true;
    try {
      while (this.queue.length > 0) {
        const batch = this.queue.slice(0, BATCH_SIZE);
        try {
          const { snapshot } = await this.options.send(batch);
          this.queue.splice(0, batch.length);
          this.persist();
          this.options.onSnapshot?.(snapshot);
        } catch (error) {
          if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
            this.clear();
            this.options.onGone?.();
            return "gone";
          }
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            // The server will never accept this batch; retrying forever
            // would block everything behind it.
            this.queue.splice(0, batch.length);
            this.persist();
            continue;
          }
          return "offline"; // network down or server hiccup: keep and retry later
        }
      }
      return "sent";
    } finally {
      this.flushing = false;
    }
  }

  clear(): void {
    this.queue = [];
    this.options.storage.removeItem(this.options.storageKey);
    this.options.onPendingChange?.(0);
  }

  private persist(): void {
    try {
      this.options.storage.setItem(this.options.storageKey, JSON.stringify(this.queue));
    } catch {
      /* storage full or unavailable: keep the queue in memory */
    }
    this.options.onPendingChange?.(this.queue.length);
  }

  private restore(): PositionIn[] {
    try {
      const saved = JSON.parse(this.options.storage.getItem(this.options.storageKey) ?? "[]");
      return Array.isArray(saved) ? saved : [];
    } catch {
      return [];
    }
  }
}
