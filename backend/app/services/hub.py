"""In-process publish/subscribe for live updates.

Each connected viewer owns a small queue; publishing a snapshot for a session
drops it into the queues of that session's viewers.

This lives in memory, so it works for a single API process. To scale to
several workers, replace this class with one backed by Redis pub/sub or
PostgreSQL LISTEN/NOTIFY — the interface (``subscribe`` / ``publish``) is all
the rest of the app relies on.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

#: Snapshots are full state, so if a slow viewer falls behind we can simply
#: drop the oldest ones — only the latest matters.
QUEUE_SIZE = 16


class Hub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, session_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[session_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[session_id].discard(queue)
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    def publish(self, session_id: str, message: dict[str, Any]) -> None:
        for queue in self._subscribers.get(session_id, ()):
            if queue.full():
                with suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(message)

    def viewer_count(self, session_id: str) -> int:
        return len(self._subscribers.get(session_id, ()))
