import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { PositionIn, Snapshot } from "../api/types";
import { snapshot } from "../domain/testing";
import { BATCH_SIZE, MAX_BUFFERED, PositionUploader } from "./uploader";

const fix = (n: number): PositionIn => ({ lat: 42 + n / 1e5, lon: 1.5, ts: new Date(1e12 + n * 5000).toISOString() });

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
    data,
  };
}

function setup(send: (batch: PositionIn[]) => Promise<{ snapshot: Snapshot }>) {
  const storage = memoryStorage();
  const onSnapshot = vi.fn();
  const onGone = vi.fn();
  const make = () =>
    new PositionUploader({ send, storage, storageKey: "buffer", onSnapshot, onGone });
  return { storage, onSnapshot, onGone, make, uploader: make() };
}

describe("PositionUploader", () => {
  let sent: PositionIn[][];
  const ok = async (batch: PositionIn[]) => {
    sent.push(batch);
    return { snapshot: snapshot() };
  };
  beforeEach(() => {
    sent = [];
  });

  it("sends queued fixes in order and empties the queue", async () => {
    const { uploader, onSnapshot } = setup(ok);
    [1, 2, 3].forEach((n) => uploader.enqueue(fix(n)));
    expect(await uploader.flush()).toBe("sent");
    expect(sent).toEqual([[fix(1), fix(2), fix(3)]]);
    expect(uploader.pending).toBe(0);
    expect(onSnapshot).toHaveBeenCalledOnce();
    expect(await uploader.flush()).toBe("empty");
  });

  it("keeps everything while offline and delivers it, in order, once back", async () => {
    let online = false;
    const { uploader } = setup(async (batch) => {
      if (!online) throw new TypeError("Failed to fetch");
      return ok(batch);
    });
    uploader.enqueue(fix(1));
    expect(await uploader.flush()).toBe("offline");
    uploader.enqueue(fix(2));
    expect(await uploader.flush()).toBe("offline");
    expect(uploader.pending).toBe(2);

    online = true;
    expect(await uploader.flush()).toBe("sent");
    expect(sent).toEqual([[fix(1), fix(2)]]);
  });

  it("treats server errors like being offline", async () => {
    const { uploader } = setup(async () => {
      throw new ApiError(503, "unavailable");
    });
    uploader.enqueue(fix(1));
    expect(await uploader.flush()).toBe("offline");
    expect(uploader.pending).toBe(1);
  });

  it("survives a page reload: the buffer is persisted", async () => {
    const { uploader, make } = setup(ok);
    uploader.enqueue(fix(1));
    uploader.enqueue(fix(2));
    const afterReload = make();
    expect(afterReload.pending).toBe(2);
    await afterReload.flush();
    expect(sent).toEqual([[fix(1), fix(2)]]);
    expect(make().pending).toBe(0);
  });

  it("splits a long backlog into batches", async () => {
    const { uploader } = setup(ok);
    for (let n = 0; n < BATCH_SIZE * 2 + 10; n++) uploader.enqueue(fix(n));
    await uploader.flush();
    expect(sent.map((batch) => batch.length)).toEqual([BATCH_SIZE, BATCH_SIZE, 10]);
    expect(sent[2][9]).toEqual(fix(BATCH_SIZE * 2 + 9));
  });

  it("stops and clears when the session is gone", async () => {
    for (const status of [404, 410]) {
      const { uploader, onGone, storage } = setup(async () => {
        throw new ApiError(status, "session_not_found");
      });
      uploader.enqueue(fix(1));
      expect(await uploader.flush()).toBe("gone");
      expect(onGone).toHaveBeenCalledOnce();
      expect(uploader.pending).toBe(0);
      expect(storage.data.has("buffer")).toBe(false);
    }
  });

  it("drops a batch the server rejects for good, then carries on", async () => {
    let first = true;
    const { uploader } = setup(async (batch) => {
      if (first) {
        first = false;
        throw new ApiError(422, "invalid_request");
      }
      return ok(batch);
    });
    for (let n = 0; n < BATCH_SIZE + 1; n++) uploader.enqueue(fix(n));
    expect(await uploader.flush()).toBe("sent");
    expect(sent).toEqual([[fix(BATCH_SIZE)]]);
  });

  it("does not run two flushes at once", async () => {
    let release!: () => void;
    const { uploader } = setup(async (batch) => {
      await new Promise<void>((resolve) => (release = resolve));
      return ok(batch);
    });
    uploader.enqueue(fix(1));
    const running = uploader.flush();
    expect(await uploader.flush()).toBe("busy");
    release();
    expect(await running).toBe("sent");
    expect(sent).toHaveLength(1);
  });

  it("caps the buffer by dropping the oldest fixes", () => {
    const { uploader } = setup(ok);
    for (let n = 0; n < MAX_BUFFERED + 5; n++) uploader.enqueue(fix(n));
    expect(uploader.pending).toBe(MAX_BUFFERED);
  });

  it("ignores a corrupted saved buffer", () => {
    const { storage, make } = setup(ok);
    storage.setItem("buffer", "{not json");
    expect(make().pending).toBe(0);
  });
});
