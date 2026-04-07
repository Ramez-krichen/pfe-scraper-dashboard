"""Per-domain queue helpers for the distributed URL frontier."""

from __future__ import annotations

from collections.abc import Callable

from .url_store import FrontierKeys

PushSideSelector = Callable[[int], str]


class DomainQueue:
    """
    Encapsulates domain queue naming and insertion policy.

    The default policy gives lower numeric priorities a fast lane by pushing
    them to the front of the per-domain list while keeping normal URLs FIFO.
    """

    def __init__(
        self,
        keys: FrontierKeys,
        *,
        priority_boost_threshold: int = 3,
        push_side_selector: PushSideSelector | None = None,
    ) -> None:
        self.keys = keys
        self.priority_boost_threshold = priority_boost_threshold
        self.push_side_selector = push_side_selector

    def queue_key(self, domain: str) -> str:
        """Returns the Redis list key for one domain."""

        return self.keys.domain_queue(domain)

    def push_side_for_priority(self, priority: int) -> str:
        """
        Returns `left` or `right` for queue insertion.

        Lower numeric values represent higher priority.
        """

        if self.push_side_selector is not None:
            side = self.push_side_selector(priority)
            if side not in {"left", "right"}:
                raise ValueError("push_side_selector must return 'left' or 'right'")
            return side

        return "left" if priority <= self.priority_boost_threshold else "right"
