"""URL normalization, metadata storage, and Redis key helpers for the frontier."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class FrontierKeys:
    """Centralizes Redis key naming for the URL frontier."""

    prefix: str = "frontier"

    @property
    def seen_urls(self) -> str:
        return f"{self.prefix}:seen_urls"

    @property
    def ready_domains(self) -> str:
        return f"{self.prefix}:ready_domains"

    @property
    def inflight(self) -> str:
        return f"{self.prefix}:inflight"

    @property
    def inflight_timeouts(self) -> str:
        return f"{self.prefix}:inflight_timeouts"

    @property
    def retry_schedule(self) -> str:
        return f"{self.prefix}:retry_schedule"

    @property
    def failed(self) -> str:
        return f"{self.prefix}:failed"

    @property
    def domain_delays(self) -> str:
        return f"{self.prefix}:domain_delays"

    @property
    def url_prefix(self) -> str:
        return f"{self.prefix}:url:"

    @property
    def domain_queue_prefix(self) -> str:
        return f"{self.prefix}:domain_queue:"

    def url_key(self, url_id: str) -> str:
        return f"{self.url_prefix}{url_id}"

    def domain_queue(self, domain: str) -> str:
        return f"{self.domain_queue_prefix}{domain}"


@dataclass(slots=True)
class ScheduledURL:
    """Represents one scheduled URL lease returned to a worker."""

    id: str
    url: str
    job_type: str
    domain: str
    priority: int
    retries: int
    created_at: float
    status: str = "queued"
    started_at: float | None = None
    lease_deadline: float | None = None
    budget_key: str | None = None
    proxy_group: str | None = None
    shard_key: str | None = None
    last_error: str | None = None
    next_retry_at: float | None = None
    extra_fields: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_redis(cls, data: Mapping[str, str]) -> ScheduledURL | None:
        """Builds a typed URL record from Redis hash data."""

        if not data:
            return None

        known_fields = {
            "id",
            "url",
            "job_type",
            "domain",
            "priority",
            "retries",
            "created_at",
            "status",
            "started_at",
            "lease_deadline",
            "budget_key",
            "proxy_group",
            "shard_key",
            "last_error",
            "next_retry_at",
        }
        extra_fields = {
            key: value
            for key, value in data.items()
            if key not in known_fields
        }

        return cls(
            id=data["id"],
            url=data["url"],
            job_type=data["job_type"],
            domain=data["domain"],
            priority=int(data.get("priority", "5")),
            retries=int(data.get("retries", "0")),
            created_at=float(data.get("created_at", "0")),
            status=data.get("status", "queued"),
            started_at=_to_optional_float(data.get("started_at")),
            lease_deadline=_to_optional_float(data.get("lease_deadline")),
            budget_key=data.get("budget_key") or None,
            proxy_group=data.get("proxy_group") or None,
            shard_key=data.get("shard_key") or None,
            last_error=data.get("last_error") or None,
            next_retry_at=_to_optional_float(data.get("next_retry_at")),
            extra_fields=extra_fields,
        )


class URLStore:
    """Owns URL normalization and metadata access for the frontier."""

    def __init__(self, redis: Redis, keys: FrontierKeys) -> None:
        self.redis = redis
        self.keys = keys

    async def get_url(self, url_id: str) -> ScheduledURL | None:
        """Fetches one URL record by ID."""

        data = await self.redis.hgetall(self.keys.url_key(url_id))
        return ScheduledURL.from_redis(data)

    async def get_url_status(self, url_id: str) -> dict[str, Any] | None:
        """Returns the current Redis-backed URL status and metadata."""

        scheduled_url = await self.get_url(url_id)
        if scheduled_url is None:
            return None

        data = {
            "url_id": scheduled_url.id,
            "url": scheduled_url.url,
            "domain": scheduled_url.domain,
            "priority": scheduled_url.priority,
            "retries": scheduled_url.retries,
            "status": scheduled_url.status,
            "created_at": scheduled_url.created_at,
            "started_at": scheduled_url.started_at,
            "lease_deadline": scheduled_url.lease_deadline,
            "budget_key": scheduled_url.budget_key,
            "proxy_group": scheduled_url.proxy_group,
            "shard_key": scheduled_url.shard_key,
            "last_error": scheduled_url.last_error,
            "next_retry_at": scheduled_url.next_retry_at,
        }

        raw_hash = await self.redis.hgetall(self.keys.url_key(url_id))
        data["updated_at"] = _to_optional_float(raw_hash.get("updated_at"))
        data["completed_at"] = _to_optional_float(raw_hash.get("completed_at"))
        data["failed_at"] = _to_optional_float(raw_hash.get("failed_at"))

        return data

    async def set_domain_delay(self, domain: str, delay_seconds: float) -> None:
        """Sets or updates a domain politeness delay in Redis."""

        await self.redis.hset(
            self.keys.domain_delays,
            domain.lower(),
            str(max(0.0, delay_seconds)),
        )

    async def set_domain_delays(self, domain_delays: Mapping[str, float]) -> None:
        """Bulk loads politeness delays into Redis."""

        if not domain_delays:
            return

        mapping = {
            domain.lower(): str(max(0.0, delay))
            for domain, delay in domain_delays.items()
        }
        await self.redis.hset(self.keys.domain_delays, mapping=mapping)

    @staticmethod
    def normalize_url(url: str) -> str:
        """Returns a canonical URL string used for deduplication."""

        parsed = urlsplit(url.strip())
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"URL must include scheme and host: {url!r}")

        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError(f"URL host could not be parsed: {url!r}")

        port = parsed.port
        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        netloc = hostname
        if port and not default_port:
            netloc = f"{hostname}:{port}"

        path = parsed.path or "/"
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        normalized_query = urlencode(sorted(query_pairs), doseq=True)

        return urlunsplit((scheme, netloc, path, normalized_query, ""))

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extracts the politeness domain from a normalized URL."""

        parsed = urlsplit(url)
        domain = (parsed.hostname or "").lower()
        if not domain:
            raise ValueError(f"URL host could not be parsed: {url!r}")
        return domain

    @staticmethod
    def make_url_id(normalized_url: str) -> str:
        """Builds a deterministic URL ID from the normalized URL."""

        return hashlib.sha1(normalized_url.encode("utf-8"), usedforsecurity=False).hexdigest()


def _to_optional_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
