"""FastAPI ingestion service for the Redis-backed URL frontier."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from frontier import FrontierConfig, FrontierManager


def load_config(path: Path = Path.cwd() / "config.yaml") -> dict[str, Any]:
    """Loads application configuration from YAML."""

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_frontier_config(config: dict[str, Any]) -> FrontierConfig:
    """Builds frontier settings from the existing project config shape."""

    redis_cfg = config.get("redis", {})
    frontier_cfg = config.get("frontier", {})

    return FrontierConfig(
        host=redis_cfg.get("host", "localhost"),
        port=redis_cfg.get("port", 6379),
        password=redis_cfg.get("password"),
        db=redis_cfg.get("db", 0),
        key_prefix=frontier_cfg.get("key_prefix", "frontier"),
        default_crawl_delay_seconds=frontier_cfg.get("default_crawl_delay_seconds", 2.0),
        inflight_timeout_seconds=frontier_cfg.get(
            "inflight_timeout_seconds",
            redis_cfg.get("timeout_seconds", 300),
        ),
        max_retries=frontier_cfg.get(
            "max_retries",
            redis_cfg.get("max_retries", 3),
        ),
        domain_delays=frontier_cfg.get("domain_delays", {}),
        priority_boost_threshold=frontier_cfg.get("priority_boost_threshold", 3),
        wait_max_sleep_seconds=frontier_cfg.get("wait_max_sleep_seconds", 1.0),
    )


class AddUrlRequest(BaseModel):
    """Payload for URL ingestion."""

    url: HttpUrl
    priority: int = Field(default=5, ge=1, le=10)
    job_type: str | None = None
    budget_key: str | None = None
    proxy_group: str | None = None
    shard_key: str | None = None


class AddUrlResponse(BaseModel):
    """Response returned after URL ingestion."""

    url_id: str | None
    inserted: bool


class BatchAddUrlRequest(BaseModel):
    """Payload for batch URL ingestion."""

    urls: list[AddUrlRequest] = Field(min_length=1, max_length=1000)


class BatchAddUrlResult(BaseModel):
    """Per-item batch insertion result."""

    url: HttpUrl
    url_id: str | None
    inserted: bool


class BatchAddUrlResponse(BaseModel):
    """Response returned after batch ingestion."""

    total: int
    inserted: int
    duplicates: int
    results: list[BatchAddUrlResult]


class UrlStatusResponse(BaseModel):
    """Current URL metadata and frontier execution status."""

    url_id: str
    url: HttpUrl
    domain: str
    priority: int
    retries: int
    status: str
    created_at: float
    started_at: float | None = None
    lease_deadline: float | None = None
    completed_at: float | None = None
    failed_at: float | None = None
    updated_at: float | None = None
    budget_key: str | None = None
    proxy_group: str | None = None
    shard_key: str | None = None
    last_error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Creates and tears down the shared frontier manager."""

    config = load_config()
    frontier = FrontierManager(build_frontier_config(config))
    await frontier.start()
    app.state.frontier = frontier
    try:
        yield
    finally:
        await frontier.close()


app = FastAPI(
    title="Frontier Ingestion API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Basic liveness check."""

    return {"status": "ok"}


@app.post("/frontier/urls", response_model=AddUrlResponse)
async def add_frontier_url(payload: AddUrlRequest) -> AddUrlResponse:
    """Adds one URL to the frontier with deduplication and priority."""

    frontier: FrontierManager = app.state.frontier

    try:
        url_id = await frontier.add_url(
            str(payload.url),
            job_type=payload.job_type,
            priority=payload.priority,
            budget_key=payload.budget_key,
            proxy_group=payload.proxy_group,
            shard_key=payload.shard_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AddUrlResponse(
        url_id=url_id,
        inserted=url_id is not None,
    )


@app.post("/frontier/urls/batch", response_model=BatchAddUrlResponse)
async def add_frontier_urls_batch(payload: BatchAddUrlRequest) -> BatchAddUrlResponse:
    """Adds multiple URLs to the frontier in one request."""

    frontier: FrontierManager = app.state.frontier

    entries = [
        {
            "url": str(item.url),
            "job_type": item.job_type,
            "priority": item.priority,
            "budget_key": item.budget_key,
            "proxy_group": item.proxy_group,
            "shard_key": item.shard_key,
        }
        for item in payload.urls
    ]

    try:
        url_ids = await frontier.add_urls(entries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = [
        BatchAddUrlResult(
            url=item.url,
            url_id=url_id,
            inserted=url_id is not None,
        )
        for item, url_id in zip(payload.urls, url_ids, strict=True)
    ]
    inserted_count = sum(1 for result in results if result.inserted)

    return BatchAddUrlResponse(
        total=len(results),
        inserted=inserted_count,
        duplicates=len(results) - inserted_count,
        results=results,
    )


@app.get("/frontier/urls/{url_id}", response_model=UrlStatusResponse)
async def get_frontier_url_status(url_id: str) -> UrlStatusResponse:
    """Returns the latest Redis-backed status and result payload for a URL."""

    frontier: FrontierManager = app.state.frontier
    status = await frontier.get_url_status(url_id)
    if status is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return UrlStatusResponse(**status)
