"""High-level manager for the distributed Redis-backed URL frontier."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Mapping

from redis.asyncio import Redis

from .domain_queue import DomainQueue, PushSideSelector
from .scheduler import RedisFrontierScheduler
from .url_store import FrontierKeys, ScheduledURL, URLStore


@dataclass(slots=True)
class FrontierConfig:
    """Configuration for the Redis-backed frontier scheduler."""

    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db: int = 0
    key_prefix: str = "frontier"
    default_crawl_delay_seconds: float = 1.0
    inflight_timeout_seconds: float = 300.0
    max_retries: int = 3
    retry_delay_seconds: float = 10.0
    retry_backoff_multiplier: float = 2.0
    max_retry_delay_seconds: float = 300.0
    retry_promotion_batch_size: int = 100
    domain_delays: Mapping[str, float] = field(default_factory=dict)
    priority_boost_threshold: int = 3
    wait_max_sleep_seconds: float = 1.0


class FrontierManager:
    """Public API for URL ingestion, leasing, completion, and recovery."""

    def __init__(
        self,
        config: FrontierConfig,
        *,
        redis_client: Redis | None = None,
        push_side_selector: PushSideSelector | None = None,
    ) -> None:
        self.config = config
        self.keys = FrontierKeys(prefix=config.key_prefix)
        self.redis = redis_client or Redis(
            host=config.host,
            port=config.port,
            password=config.password,
            db=config.db,
            decode_responses=True,
        )
        self.url_store = URLStore(self.redis, self.keys)
        self.domain_queue = DomainQueue(
            self.keys,
            priority_boost_threshold=config.priority_boost_threshold,
            push_side_selector=push_side_selector,
        )
        self.scheduler = RedisFrontierScheduler(
            self.redis,
            keys=self.keys,
            domain_queue=self.domain_queue,
            default_crawl_delay_seconds=config.default_crawl_delay_seconds,
            inflight_timeout_seconds=config.inflight_timeout_seconds,
            max_retries=config.max_retries,
            retry_delay_seconds=config.retry_delay_seconds,
            retry_backoff_multiplier=config.retry_backoff_multiplier,
            max_retry_delay_seconds=config.max_retry_delay_seconds,
        )
        self._owns_redis = redis_client is None

    async def __aenter__(self) -> FrontierManager:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        """Initializes Redis connectivity and configured domain delays."""

        await self.redis.ping()
        await self.url_store.set_domain_delays(self.config.domain_delays)

    async def close(self) -> None:
        """Closes the Redis connection if this manager created it."""

        if self._owns_redis:
            await self.redis.aclose()

    async def add_url(
        self,
        url: str,
        priority: int = 5,
        *,
        job_type: str | None = None,
        budget_key: str | None = None,
        proxy_group: str | None = None,
        shard_key: str | None = None,
    ) -> str | None:
        """
        Adds one URL to the frontier.

        Returns the URL ID when inserted, or `None` if the URL was already seen.
        """

        normalized_url = self.url_store.normalize_url(url)
        url_id = self.url_store.make_url_id(normalized_url)
        domain = self.url_store.extract_domain(normalized_url)
        inserted = await self.scheduler.add_url(
            url_id=url_id,
            url=normalized_url,
            domain=domain,
            job_type=job_type or "",
            priority=priority,
            created_at=time.time(),
            budget_key=budget_key,
            proxy_group=proxy_group,
            shard_key=shard_key,
        )
        return url_id if inserted else None

    async def add_urls(
        self,
        entries: list[dict[str, str | int | None]],
    ) -> list[str | None]:
        """
        Adds multiple URLs to the frontier.

        Each entry may contain `url`, `priority`, `budget_key`, `proxy_group`,
        and `shard_key`. The return list preserves input order.
        """

        results: list[str | None] = []
        for entry in entries:
            url = entry["url"]
            if not isinstance(url, str):
                raise ValueError("Batch entry field 'url' must be a string")

            priority = entry.get("priority", 5)
            if not isinstance(priority, int):
                raise ValueError("Batch entry field 'priority' must be an integer")

            job_type = entry.get("job_type")
            budget_key = entry.get("budget_key")
            proxy_group = entry.get("proxy_group")
            shard_key = entry.get("shard_key")

            for field_name, value in (
                ("budget_key", budget_key),
                ("proxy_group", proxy_group),
                ("shard_key", shard_key),
                ("job_type", job_type),
            ):
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"Batch entry field '{field_name}' must be a string or null")

            results.append(
                await self.add_url(
                    url,
                    priority=priority,
                    job_type=str(job_type),
                    budget_key=str(budget_key),
                    proxy_group=str(proxy_group),
                    shard_key=str(shard_key),
                )
            )

        return results

    async def get_next_url(self, *, wait: bool = True) -> ScheduledURL | None:
        """
        Returns the next leaseable URL.

        If `wait=False`, returns immediately when nothing is ready.
        """

        while True:
            now = time.time()
            await self.scheduler.promote_due_retries(
                now=now,
                limit=self.config.retry_promotion_batch_size,
            )
            lease = await self.scheduler.lease_next_url(now=now)
            if lease is not None:
                scheduled_url = await self.url_store.get_url(lease.url_id)
                if scheduled_url is None:
                    await self.scheduler.drop_inflight(lease.url_id)
                    continue

                scheduled_url.started_at = now
                scheduled_url.lease_deadline = lease.lease_deadline
                scheduled_url.status = "inflight"
                return scheduled_url

            if not wait:
                return None

            ready_delay = await self.scheduler.next_ready_delay(now=now)
            retry_delay = await self.scheduler.next_retry_delay(now=now)

            if ready_delay is None and retry_delay is None:
                sleep_seconds = self.config.wait_max_sleep_seconds
            else:
                candidate_delays = [
                    delay
                    for delay in (ready_delay, retry_delay)
                    if delay is not None
                ]
                sleep_seconds = min(
                    self.config.wait_max_sleep_seconds,
                    max(0.05, min(candidate_delays)),
                )
            await asyncio.sleep(sleep_seconds)

    async def complete_url(self, url_id: str) -> bool:
        """Marks a leased URL as successfully processed."""

        return await self.scheduler.complete_url(url_id, now=time.time())

    async def fail_url(self, url_id: str, error_message: str) -> str:
        """Retries or dead-letters a leased URL."""

        scheduled_url = await self.url_store.get_url(url_id)
        if scheduled_url is None:
            await self.scheduler.drop_inflight(url_id)
            return "missing"

        return await self.scheduler.fail_url(
            scheduled_url,
            error_message=error_message,
            now=time.time(),
        )

    async def recover_timed_out_urls(
        self,
        *,
        limit: int = 100,
        error_message: str = "lease timeout",
    ) -> dict[str, int]:
        """Requeues or dead-letters expired inflight URLs."""

        expired_ids = await self.scheduler.expired_inflight_ids(now=time.time(), limit=limit)
        recovered = 0
        failed = 0
        missing = 0

        for url_id in expired_ids:
            result = await self.fail_url(url_id, error_message)
            if result == "requeued":
                recovered += 1
            elif result == "failed":
                failed += 1
            else:
                missing += 1

        return {
            "requeued": recovered,
            "failed": failed,
            "missing": missing,
        }

    async def set_domain_delay(self, domain: str, delay_seconds: float) -> None:
        """Updates one domain politeness rule."""

        await self.url_store.set_domain_delay(domain, delay_seconds)

    async def get_url_status(self, url_id: str) -> dict[str, Any] | None:
        """Returns the current Redis-backed status view for a URL."""

        return await self.url_store.get_url_status(url_id)
