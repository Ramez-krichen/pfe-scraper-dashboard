"""Worker-facing API for interacting with the distributed URL frontier."""

from __future__ import annotations

from .frontier_manager import FrontierConfig, FrontierManager
from .url_store import ScheduledURL


class FrontierWorkerAPI:
    """
    Thin worker-only facade over `FrontierManager`.

    Workers should lease work through `get_next_url()` and must always follow
    with either `complete_url()` or `fail_url()`.
    """

    def __init__(self, config: FrontierConfig) -> None:
        self._frontier = FrontierManager(config)

    async def __aenter__(self) -> FrontierWorkerAPI:
        await self._frontier.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._frontier.close()

    async def get_next_url(self, *, wait: bool = True) -> ScheduledURL | None:
        """Leases the next schedulable URL for this worker."""

        return await self._frontier.get_next_url(wait=wait)

    async def complete_url(self, url_id: str) -> bool:
        """Acknowledges successful processing."""

        return await self._frontier.complete_url(url_id)

    async def fail_url(self, url_id: str, error_message: str) -> str:
        """Acknowledges worker failure and triggers retry logic."""

        return await self._frontier.fail_url(url_id, error_message)

    async def recover_timed_out_urls(self, *, limit: int = 100) -> dict[str, int]:
        """Requeues expired inflight URLs."""

        return await self._frontier.recover_timed_out_urls(limit=limit)
