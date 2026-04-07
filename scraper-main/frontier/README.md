# Frontier Redis Schema

The frontier package uses the following Redis keys.

`SET frontier:seen_urls`
- Deduplication fingerprints for normalized URLs.

`HASH frontier:url:{id}`
- Per-URL metadata.
- Core fields: `id`, `url`, `domain`, `priority`, `retries`, `created_at`.
- Runtime fields: `status`, `updated_at`, `started_at`, `lease_deadline`, `completed_at`, `failed_at`, `last_error`, `next_retry_at`.
- Extensibility fields: `budget_key`, `proxy_group`, `shard_key`.

`LIST frontier:domain_queue:{domain}`
- Queue of URL IDs waiting for a specific domain.
- Lower numeric priorities are biased to the front of the list.

`ZSET frontier:ready_domains`
- Score is the next allowed crawl timestamp for each domain.

`HASH frontier:inflight`
- Field is `url_id`.
- Value is a JSON lease record with `domain`, `leased_at`, and `lease_deadline`.

`ZSET frontier:inflight_timeouts`
- Score is the lease deadline timestamp.
- Used to recover timed-out URLs without scanning the inflight hash.

`ZSET frontier:retry_schedule`
- Score is the next retry timestamp for failed URLs waiting on backoff.

`HASH frontier:domain_delays`
- Per-domain crawl delay overrides in seconds.

`LIST frontier:failed`
- Dead-letter entries for URLs that exceeded retry limits.

## Scheduling Flow

1. `add_url()` normalizes the URL, deduplicates it through `frontier:seen_urls`, stores metadata, pushes it onto the appropriate domain queue, and activates the domain in `frontier:ready_domains`.
2. `get_next_url()` atomically leases the earliest eligible domain, pops one URL ID from that domain queue, records inflight state, and applies the domain crawl delay before making that domain ready again.
3. `complete_url()` removes inflight state and marks the URL completed.
4. `fail_url()` removes inflight state, increments retries, and either schedules the URL into `frontier:retry_schedule` with backoff or pushes a dead-letter payload to `frontier:failed`.
5. `recover_timed_out_urls()` reads expired IDs from `frontier:inflight_timeouts` and routes them back through the same retry path.
