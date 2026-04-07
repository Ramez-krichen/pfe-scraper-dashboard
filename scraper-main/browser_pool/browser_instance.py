"""Browser instance lifecycle management for the shared browser pool."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping

from playwright.async_api import Browser

from .context_pool import ContextCreatedHook, ContextPool, ContextSlot

if TYPE_CHECKING:
    from playwright.async_api import Playwright

logger = logging.getLogger(__name__)

DisconnectedHook = Callable[["BrowserInstance"], Awaitable[None] | None]


class BrowserInstance:
    """Represents one launched Playwright browser plus its context pool."""

    def __init__(
        self,
        *,
        index: int,
        playwright: Playwright,
        browser_type: str,
        launch_options: dict[str, Any] | None = None,
        proxy: Mapping[str, Any] | None = None,
        contexts_per_browser: int,
        context_options: dict[str, Any] | None = None,
        on_context_created: ContextCreatedHook | None = None,
        operation_timeout_seconds: float = 10.0,
        reset_origin_timeout_seconds: float = 5.0,
        default_timeout_ms: float | None = None,
        default_navigation_timeout_ms: float | None = None,
        on_disconnected: DisconnectedHook | None = None,
    ) -> None:
        self.index = index
        self.playwright = playwright
        self.browser_type = browser_type
        self.launch_options = dict(launch_options or {})
        self.proxy = dict(proxy or {}) if proxy else None
        self.contexts_per_browser = contexts_per_browser
        self.context_options = dict(context_options or {})
        self.on_context_created = on_context_created
        self.operation_timeout_seconds = operation_timeout_seconds
        self.reset_origin_timeout_seconds = reset_origin_timeout_seconds
        self.default_timeout_ms = default_timeout_ms
        self.default_navigation_timeout_ms = default_navigation_timeout_ms
        self.on_disconnected = on_disconnected

        self.instance_id = f"browser-{index}-{uuid.uuid4().hex[:8]}"
        self.browser: Browser | None = None
        self.context_pool: ContextPool | None = None
        self._healthy = False
        self._disconnect_reported = False

    @property
    def is_healthy(self) -> bool:
        """Returns whether the browser is still expected to serve work."""

        return self._healthy and self.browser is not None

    async def start(self) -> list[ContextSlot]:
        """Launches the browser and provisions its context pool."""

        browser_type_impl = getattr(self.playwright, self.browser_type)
        launch_options = dict(self.launch_options)
        if self.proxy and "proxy" not in launch_options:
            launch_options["proxy"] = self.proxy

        self.browser = await browser_type_impl.launch(**launch_options)
        self._healthy = True
        self.browser.on("disconnected", lambda: self._handle_disconnect())

        self.context_pool = ContextPool(
            self,
            size=self.contexts_per_browser,
            context_options=self.context_options,
            on_context_created=self.on_context_created,
            operation_timeout_seconds=self.operation_timeout_seconds,
            reset_origin_timeout_seconds=self.reset_origin_timeout_seconds,
            default_timeout_ms=self.default_timeout_ms,
            default_navigation_timeout_ms=self.default_navigation_timeout_ms,
        )
        return await self.context_pool.initialize()

    async def recycle_context(self, slot: ContextSlot, reason: str) -> ContextSlot | None:
        """Replaces one context within this browser instance."""

        if self.context_pool is None:
            return None
        return await self.context_pool.replace(slot, reason)

    async def close(self) -> None:
        """Closes all contexts followed by the browser process."""

        self._healthy = False
        if self.context_pool is not None:
            await self.context_pool.close()
            self.context_pool = None

        if self.browser is not None:
            with contextlib.suppress(Exception):
                await self.browser.close()
            self.browser = None

    def _handle_disconnect(self) -> None:
        if self._disconnect_reported:
            return

        self._disconnect_reported = True
        self._healthy = False
        if self.context_pool is not None:
            self.context_pool.mark_all_unhealthy("browser disconnected")

        if self.on_disconnected is None:
            return

        maybe_awaitable = self.on_disconnected(self)
        if inspect.isawaitable(maybe_awaitable):
            try:
                asyncio.create_task(maybe_awaitable)
            except RuntimeError:
                close = getattr(maybe_awaitable, "close", None)
                if callable(close):
                    close()
                logger.debug("Event loop unavailable while handling disconnect for %s", self.instance_id)
