"""High-throughput browser and context pooling for Playwright workers."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Sequence

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from .browser_instance import BrowserInstance
from .context_pool import ContextCreatedHook, ContextSlot

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BrowserPoolConfig:
    """
    Configuration for a reusable Playwright browser pool.

    `browser_proxies` are assigned per browser instance in round-robin order.
    All contexts created under the same browser share that browser-level proxy.
    """

    browsers: int = 4
    contexts_per_browser: int = 5
    browser_type: str = "chromium"
    headless: bool = True
    launch_options: dict[str, Any] = field(default_factory=dict)
    context_options: dict[str, Any] = field(default_factory=dict)
    browser_proxies: Sequence[Mapping[str, Any] | None] = ()
    on_context_created: ContextCreatedHook | None = None
    max_pages_per_context: int = 50
    acquire_timeout_seconds: float | None = None
    context_operation_timeout_seconds: float = 10.0
    reset_origin_timeout_seconds: float = 5.0
    browser_restart_backoff_seconds: float = 0.5
    default_timeout_ms: float | None = 30_000
    default_navigation_timeout_ms: float | None = 30_000

    def __post_init__(self) -> None:
        if self.browsers <= 0:
            raise ValueError("browsers must be greater than zero")
        if self.contexts_per_browser <= 0:
            raise ValueError("contexts_per_browser must be greater than zero")
        if self.max_pages_per_context <= 0:
            raise ValueError("max_pages_per_context must be greater than zero")


@dataclass(slots=True)
class BrowserPoolMetrics:
    """Operational counters for the browser pool."""

    contexts_in_use: int = 0
    total_pages_scraped: int = 0
    browser_restarts: int = 0
    context_recycles: int = 0

    def snapshot(self) -> dict[str, int]:
        """Returns a stable metrics snapshot for external exporters."""

        return {
            "contexts_in_use": self.contexts_in_use,
            "total_pages_scraped": self.total_pages_scraped,
            "browser_restarts": self.browser_restarts,
            "context_recycles": self.context_recycles,
        }


class BrowserPool:
    """
    Shared pool of Playwright browsers and reusable contexts.

    Workers acquire a context or use the higher-level `get_page()` helper. The
    pool handles context reset, context recycling, and browser replacement after
    crashes so worker failures do not poison the shared pool.
    """

    def __init__(self, config: BrowserPoolConfig) -> None:
        self.config = config
        self.metrics = BrowserPoolMetrics()

        self._playwright_manager: Any | None = None
        self._playwright: Playwright | None = None
        self._instances: dict[int, BrowserInstance] = {}
        self._available_contexts: asyncio.Queue[ContextSlot] = asyncio.Queue()
        self._checked_out: dict[int, ContextSlot] = {}
        self._lifecycle_lock = asyncio.Lock()
        self._replacement_lock = asyncio.Lock()
        self._maintenance_tasks: set[asyncio.Task[Any]] = set()
        self._closing = False
        self._started = False
        self._replacing_indexes: set[int] = set()

    async def __aenter__(self) -> BrowserPool:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> None:
        await self.shutdown()

    async def start(self) -> None:
        """Starts Playwright and pre-warms every browser and context."""

        async with self._lifecycle_lock:
            if self._started:
                return

            self._closing = False
            self._playwright_manager = async_playwright()
            self._playwright = await self._playwright_manager.start()

            try:
                for index in range(self.config.browsers):
                    instance, slots = await self._spawn_instance(index)
                    self._instances[index] = instance
                    for slot in slots:
                        self._available_contexts.put_nowait(slot)
            except Exception:
                await self._shutdown_started_resources()
                raise

            self._started = True

    async def shutdown(self) -> None:
        """Closes all contexts, browsers, and the Playwright driver."""

        async with self._lifecycle_lock:
            if not self._started:
                return

            self._closing = True

            tasks = list(self._maintenance_tasks)
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._maintenance_tasks.clear()

            await self._shutdown_started_resources()
            self._started = False

    async def acquire_context(self) -> BrowserContext:
        """
        Acquires a pooled context in O(1) time from the shared queue.

        When using this low-level API directly, call `release_context(...,
        discard=True)` if the worker hit a navigation or page-level failure.
        """

        slot = await self._acquire_slot()
        return slot.context

    async def release_context(
        self,
        context: BrowserContext,
        *,
        discard: bool = False,
        reason: str | None = None,
    ) -> None:
        """
        Releases a context back to the pool or recycles it if needed.

        Set `discard=True` when the worker saw an error that may have poisoned
        browser state inside the leased context.
        """

        slot = self._checked_out.get(id(context))
        if slot is None:
            logger.debug("Ignoring release for unknown context %s", id(context))
            return
        await self._release_slot(slot, discard=discard, reason=reason)

    @asynccontextmanager
    async def get_page(self) -> AsyncIterator[Page]:
        """
        Acquires a pooled context and yields a fresh page.

        Any exception from worker code marks the context unhealthy so the next
        lease gets a recycled context instead of inheriting broken state.
        """

        slot = await self._acquire_slot()
        page: Page | None = None
        had_error = False

        try:
            page = await asyncio.wait_for(
                slot.context.new_page(),
                timeout=self.config.context_operation_timeout_seconds,
            )
            yield page
            self.metrics.total_pages_scraped += 1
        except Exception as exc:
            had_error = True
            slot.mark_for_recycle(f"page lease failed: {type(exc).__name__}: {exc}")
            raise
        finally:
            if page is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(
                        page.close(),
                        timeout=self.config.context_operation_timeout_seconds,
                    )
            await self._release_slot(
                slot,
                discard=had_error or slot.recycle_requested,
                reason=slot.recycle_reason,
            )

    def snapshot_metrics(self) -> dict[str, int]:
        """Returns the current counters for monitoring exports."""

        return self.metrics.snapshot()

    async def _acquire_slot(self) -> ContextSlot:
        self._ensure_started()

        while True:
            if self.config.acquire_timeout_seconds is None:
                slot = await self._available_contexts.get()
            else:
                slot = await asyncio.wait_for(
                    self._available_contexts.get(),
                    timeout=self.config.acquire_timeout_seconds,
                )

            if not slot.active or not slot.browser_instance.is_healthy:
                continue

            slot.in_use = True
            self.metrics.contexts_in_use += 1
            self._checked_out[id(slot.context)] = slot
            return slot

    async def _release_slot(
        self,
        slot: ContextSlot,
        *,
        discard: bool,
        reason: str | None,
    ) -> None:
        self._checked_out.pop(id(slot.context), None)
        slot.in_use = False
        if self.metrics.contexts_in_use > 0:
            self.metrics.contexts_in_use -= 1

        slot.pages_served += 1
        if discard:
            slot.mark_for_recycle(reason or "caller requested recycle")
        elif slot.pages_served >= self.config.max_pages_per_context:
            slot.mark_for_recycle(
                f"context reached lease limit ({self.config.max_pages_per_context})"
            )

        if self._closing:
            await slot.context_pool.retire(slot, reason or "pool shutting down")
            return

        if not slot.active or not slot.browser_instance.is_healthy or slot.recycle_requested:
            await self._recycle_slot(slot, reason or slot.recycle_reason or "context unavailable")
            return

        try:
            await slot.context_pool.reset(slot)
        except Exception as exc:
            slot.mark_for_recycle(f"context reset failed: {type(exc).__name__}: {exc}")
            await self._recycle_slot(slot, slot.recycle_reason or "context reset failed")
            return

        if slot.active and slot.browser_instance.is_healthy and not self._closing:
            self._available_contexts.put_nowait(slot)

    async def _recycle_slot(self, slot: ContextSlot, reason: str) -> None:
        self.metrics.context_recycles += 1

        try:
            replacement = await slot.browser_instance.recycle_context(slot, reason)
        except Exception as exc:
            logger.exception(
                "Failed to recycle context %s on %s",
                slot.slot_id,
                slot.browser_instance.instance_id,
            )
            self._schedule_maintenance(self._replace_instance(slot.browser_instance))
            return

        if replacement is not None and not self._closing:
            self._available_contexts.put_nowait(replacement)

    async def _spawn_instance(self, index: int) -> tuple[BrowserInstance, list[ContextSlot]]:
        if self._playwright is None:
            raise RuntimeError("Playwright is not started")

        launch_options = dict(self.config.launch_options)
        launch_options.setdefault("headless", self.config.headless)

        instance = BrowserInstance(
            index=index,
            playwright=self._playwright,
            browser_type=self.config.browser_type,
            launch_options=launch_options,
            proxy=self._proxy_for_index(index),
            contexts_per_browser=self.config.contexts_per_browser,
            context_options=self.config.context_options,
            on_context_created=self.config.on_context_created,
            operation_timeout_seconds=self.config.context_operation_timeout_seconds,
            reset_origin_timeout_seconds=self.config.reset_origin_timeout_seconds,
            default_timeout_ms=self.config.default_timeout_ms,
            default_navigation_timeout_ms=self.config.default_navigation_timeout_ms,
            on_disconnected=self._on_browser_disconnected,
        )
        slots = await instance.start()
        return instance, slots

    def _proxy_for_index(self, index: int) -> Mapping[str, Any] | None:
        if not self.config.browser_proxies:
            return None
        proxy = self.config.browser_proxies[index % len(self.config.browser_proxies)]
        return proxy

    def _ensure_started(self) -> None:
        if not self._started or self._playwright is None:
            raise RuntimeError("BrowserPool.start() must be awaited before use")

    async def _shutdown_started_resources(self) -> None:
        instances = list(self._instances.values())
        self._instances.clear()
        for instance in instances:
            await instance.close()

        self._checked_out.clear()
        self.metrics.contexts_in_use = 0
        self._available_contexts = asyncio.Queue()

        if self._playwright is not None:
            await self._playwright.stop()
        self._playwright_manager = None
        self._playwright = None

    def _schedule_maintenance(self, coroutine: Any) -> None:
        task = asyncio.create_task(coroutine)
        self._maintenance_tasks.add(task)
        task.add_done_callback(self._maintenance_tasks.discard)

    async def _on_browser_disconnected(self, instance: BrowserInstance) -> None:
        if self._closing:
            return
        self._schedule_maintenance(self._replace_instance(instance))

    async def _replace_instance(self, instance: BrowserInstance) -> None:
        async with self._replacement_lock:
            if self._closing:
                return
            if instance.index in self._replacing_indexes:
                return

            current = self._instances.get(instance.index)
            if current is not None and current is not instance:
                return

            self._replacing_indexes.add(instance.index)

        try:
            self._instances.pop(instance.index, None)
            self.metrics.browser_restarts += 1
            await instance.close()

            while not self._closing:
                try:
                    await asyncio.sleep(self.config.browser_restart_backoff_seconds)
                    replacement, slots = await self._spawn_instance(instance.index)
                except Exception:
                    logger.exception("Failed to restart browser %s", instance.instance_id)
                    continue

                self._instances[replacement.index] = replacement
                for slot in slots:
                    self._available_contexts.put_nowait(slot)
                return
        finally:
            async with self._replacement_lock:
                self._replacing_indexes.discard(instance.index)
