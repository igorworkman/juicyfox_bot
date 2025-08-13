import time
from typing import Any, Awaitable, Callable

from metrics import (
    posting_latency_seconds,
    posting_queue_depth,
    posting_send_errors_total,
)


async def worker_posting(
    queue,
    send_fn: Callable[[Any], Awaitable[None]],
) -> None:
    """Consume events from ``queue`` and send them using ``send_fn``.

    Metrics are recorded for queue depth, latency and send errors.
    Each event is expected to optionally contain ``enqueue_ts`` – the
    UNIX timestamp when it was queued. If missing, the current time is
    used instead, making the latency measurement best effort.
    """
    while True:
        event = await queue.get()
        posting_queue_depth.set(queue.qsize())

        # Determine when the event was enqueued
        enqueue_ts = None
        if isinstance(event, dict):
            enqueue_ts = event.get("enqueue_ts")
        if enqueue_ts is None:
            enqueue_ts = getattr(event, "enqueue_ts", None)
        if enqueue_ts is None:
            enqueue_ts = time.time()

        try:
            await send_fn(event)
            posting_latency_seconds.observe(time.time() - enqueue_ts)
        except Exception:
            posting_send_errors_total.inc()
        finally:
            queue.task_done()
            posting_queue_depth.set(queue.qsize())
