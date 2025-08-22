#!/usr/bin/env python3
"""Entry point for the JuicyFox posting worker (Plan A).

This script runs the asynchronous posting worker defined in
``modules.posting.worker``.  The worker is responsible for
sending scheduled posts from the queue to their respective channels,
handling retries and backoff.  To run it, simply execute this file
after configuring your environment and database.
"""

import asyncio
from modules.posting.worker import main as posting_worker_main  # type: ignore


def run() -> None:
    """Run the posting worker using asyncio."""
    asyncio.run(posting_worker_main())


if __name__ == "__main__":
    run()
