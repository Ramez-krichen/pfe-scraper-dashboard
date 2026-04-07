"""Context pooling primitives for Playwright browser instances."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Page

if TYPE_CHECKING:
    from .browser_instance import BrowserInstance

logger = logging.getLogger(__name__)

ContextCreatedHook = Callable[[BrowserContext], Awaitable[None] | None]

_STORAGE_CLEAR_SCRIPT = """
async () => {
    try { localStorage.clear(); } catch (error) {}
    try { sessionStorage.clear(); } catch (error) {}

    try {
        if ('caches' in window) {
            const keys = await caches.keys();
            await Promise.all(keys.map((key) => caches.delete(key)));
        }
    } catch (error) {}

    try {
        if (indexedDB.databases) {
            const databases = await indexedDB.databases();
            await Promise.all(
                databases
                    .filter((database) => database && database.name)
                    .map((database) => new Promise((resolve) => {
                        const request = indexedDB.deleteDatabase(database.name);
                        request.onsuccess = () => resolve(null);
                        request.onerror = () => resolve(null);
                        request.onblocked = () => resolve(null);
                    }))
            );
        }
    } catch (error) {}
}
"""


@dataclass(slots=True)
class ContextSlot:
    """Tracks a reusable browser context and its lease state."""

    slot_id: str
    browser_instance: BrowserInstance
    context_pool: ContextPool
    context: BrowserContext
    created_at: float = field(default_factory=time.monotonic)
    pages_served: int = 0
    in_use: bool = False
    active: bool = True
    recycle_requested: bool = False
    recycle_reason: str | None = None
    visited_origins: set[str] = field(default_factory=set)

    def mark_for_recycle(self, reason: str) -> None:
        """Marks the slot for replacement after the current lease."""

        self.recycle_requested = True
        self.recycle_reason = reason


class ContextPool:
    """Owns all reusable contexts for a single Playwright browser."""

    def __init__(
        self,
        browser_instance: BrowserInstance,
        *,
        size: int,
        context_options: dict[str, Any] | None = None,
        on_context_created: ContextCreatedHook | None = None,
        operation_timeout_seconds: float = 10.0,
        reset_origin_timeout_seconds: float = 5.0,
        default_timeout_ms: float | None = None,
        default_navigation_timeout_ms: float | None = None,
    ) -> None:
        self.browser_instance = browser_instance
        self.size = size
        self.context_options = dict(context_options or {})
        self.on_context_created = on_context_created
        self.operation_timeout_seconds = operation_timeout_seconds
        self.reset_origin_timeout_seconds = reset_origin_timeout_seconds
        self.default_timeout_ms = default_timeout_ms
        self.default_navigation_timeout_ms = default_navigation_timeout_ms
        self._slots: dict[str, ContextSlot] = {}

    async def initialize(self) -> list[ContextSlot]:
        """Creates the initial context set for the browser instance."""

        slots: list[ContextSlot] = []
        for _ in range(self.size):
            slots.append(await self._create_slot())
        return slots

    async def replace(self, slot: ContextSlot, reason: str) -> ContextSlot | None:
        """Replaces a broken or expired context with a fresh one."""

        await self.retire(slot, reason)
        if not self.browser_instance.is_healthy:
            return None
        return await self._create_slot()

    async def retire(self, slot: ContextSlot, reason: str) -> None:
        """Permanently removes a slot from the pool and closes its context."""

        slot.active = False
        slot.mark_for_recycle(reason)
        self._slots.pop(slot.slot_id, None)
        await self._close_context(slot.context)

    async def reset(self, slot: ContextSlot) -> None:
        """
        Cleans a context so the next worker sees an isolated session.

        Cookies and permissions are cleared directly. Origin-scoped storage is
        cleared by revisiting each recorded origin with a short-lived page.
        """

        if not slot.active:
            raise RuntimeError(f"Context slot {slot.slot_id} is inactive")

        pages = list(slot.context.pages)
        for page in pages:
            await self._close_page(page)

        await self._run_with_timeout(
            slot.context.clear_cookies(),
            self.operation_timeout_seconds,
            f"clearing cookies for {slot.slot_id}",
        )
        await self._run_with_timeout(
            slot.context.clear_permissions(),
            self.operation_timeout_seconds,
            f"clearing permissions for {slot.slot_id}",
        )

        origins = {origin for origin in slot.visited_origins if origin.startswith(("http://", "https://"))}
        slot.visited_origins.clear()
        if not origins:
            return

        page = await self._run_with_timeout(
            slot.context.new_page(),
            self.operation_timeout_seconds,
            f"opening reset page for {slot.slot_id}",
        )
        try:
            for origin in origins:
                await self._run_with_timeout(
                    page.goto(origin, wait_until="domcontentloaded"),
                    self.reset_origin_timeout_seconds,
                    f"navigating to {origin} for {slot.slot_id}",
                )
                await self._run_with_timeout(
                    page.evaluate(_STORAGE_CLEAR_SCRIPT),
                    self.operation_timeout_seconds,
                    f"clearing storage for {origin} in {slot.slot_id}",
                )
        finally:
            await self._close_page(page)

    async def close(self) -> None:
        """Closes every managed context."""

        slots = list(self._slots.values())
        self._slots.clear()
        for slot in slots:
            slot.active = False
            await self._close_context(slot.context)

    def mark_all_unhealthy(self, reason: str) -> None:
        """Marks all slots as unusable after a browser-level failure."""

        for slot in self._slots.values():
            slot.active = False
            slot.mark_for_recycle(reason)

    async def _create_slot(self) -> ContextSlot:
        if self.browser_instance.browser is None:
            raise RuntimeError(f"Browser {self.browser_instance.instance_id} is not started")

        context = await self._run_with_timeout(
            self.browser_instance.browser.new_context(**self.context_options),
            self.operation_timeout_seconds,
            f"creating context for {self.browser_instance.instance_id}",
        )
        slot = ContextSlot(
            slot_id=f"{self.browser_instance.instance_id}-ctx-{uuid.uuid4().hex[:8]}",
            browser_instance=self.browser_instance,
            context_pool=self,
            context=context,
        )

        if self.default_timeout_ms is not None:
            context.set_default_timeout(self.default_timeout_ms)
        if self.default_navigation_timeout_ms is not None:
            context.set_default_navigation_timeout(self.default_navigation_timeout_ms)

        self._attach_context_listeners(slot)
        try:
            if self.on_context_created is not None:
                maybe_awaitable = self.on_context_created(context)
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
        except Exception:
            await self._close_context(context)
            raise

        self._slots[slot.slot_id] = slot
        return slot

    def _attach_context_listeners(self, slot: ContextSlot) -> None:
        slot.context.on("page", lambda page, slot=slot: self._attach_page_listeners(page, slot))
        slot.context.on("close", lambda _context, slot=slot: self._on_context_closed(slot))

        for page in list(slot.context.pages):
            self._attach_page_listeners(page, slot)

    def _attach_page_listeners(self, page: Page, slot: ContextSlot) -> None:
        page.on("framenavigated", lambda frame, slot=slot: self._on_frame_navigated(frame, slot))
        page.on("crash", lambda slot=slot: slot.mark_for_recycle("page crashed"))

        if page.url:
            self._record_origin(slot, page.url)

    def _on_frame_navigated(self, frame: Any, slot: ContextSlot) -> None:
        parent_frame = getattr(frame, "parent_frame", None)
        if callable(parent_frame):
            parent_frame = parent_frame()
        if parent_frame is not None:
            return
        url = getattr(frame, "url", "")
        if url:
            self._record_origin(slot, url)

    def _on_context_closed(self, slot: ContextSlot) -> None:
        if slot.active:
            slot.mark_for_recycle("context closed unexpectedly")
            slot.active = False

    def _record_origin(self, slot: ContextSlot, url: str) -> None:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return
        if parsed.scheme not in {"http", "https"}:
            return
        slot.visited_origins.add(f"{parsed.scheme}://{parsed.netloc}")

    async def _close_context(self, context: BrowserContext) -> None:
        with contextlib.suppress(Exception):
            await self._run_with_timeout(
                context.close(),
                self.operation_timeout_seconds,
                "closing browser context",
            )

    async def _close_page(self, page: Page) -> None:
        with contextlib.suppress(Exception):
            await self._run_with_timeout(
                page.close(),
                self.operation_timeout_seconds,
                "closing page",
            )

    async def _run_with_timeout(
        self,
        awaitable: Awaitable[Any],
        timeout_seconds: float,
        operation: str,
    ) -> Any:
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Timed out while {operation}") from exc
        except Exception:
            logger.exception("Context pool operation failed while %s", operation)
            raise
