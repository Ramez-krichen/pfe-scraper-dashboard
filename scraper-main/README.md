# Distributed Stealth Browser Scraping System

A distributed, horizontally scalable, memory-safe, and stealthy browser scraping system powered by SeleniumBase (CDP Mode) and Playwright (Passive Mode).

## 1. System Architecture

```text
+---------------------------------------------------------------------------------------------------+
|                                       ORCHESTRATION LAYER                                         |
|                                                                                                   |
|  [ Job Publisher / API ] ----(push list of URLs)----> [ Redis Job Queue (Pending/InProgress) ]    |
|                                                                     |                             |
|                                         +---------------------------+                             |
|                                         |                           |                             |
|                                [ Dead-Letter Queue ]      [ Metrics / Prometheus ]                |
+-----------------------------------------|---------------------------|-----------------------------+
                                          |                           |
                                  Job & Retry logic               Telemetry
                                          |                           |
+-----------------------------------------|---------------------------|-----------------------------+
| WORKER NODE 1 (e.g. 16GB RAM)           v                           v                             |
|                                                                                                   |
|  +--------------------+    +--------------------+    +--------------------+                       |
|  | Worker Process 1   |    | Worker Process 2   |    | Worker Process K   |                       |
|  |--------------------|    |--------------------|    |--------------------|                       |
|  | sb_cdp.Chrome      |    | sb_cdp.Chrome      |    | sb_cdp.Chrome      |                       |
|  | <-> Playwright CDP |    | <-> Playwright CDP |    | <-> Playwright CDP |                       |
|  +--------------------+    +--------------------+    +--------------------+                       |
+---------------------------------------------------------------------------------------------------+
| WORKER NODE 2 ...                                                                                 |
+---------------------------------------------------------------------------------------------------+
```

## 2. Folder Structure

```
stealth_scraper/
├── config.yaml            # Environment and application configuration
├── docker-compose.yml     # Orchestration setup for Redis, Prometheus, and Worker nodes
├── queue_manager.py       # Distributed Job System (Redis interactions, idempotency, DLQ, etc)
├── worker.py              # Core node processor using multiprocessing and SeleniumBase/Playwright
├── requirements.txt       # Dependencies
└── README.md              # This file
```

## 3. Scaling Strategy & Concurrency

The system uses multiprocessing at the node level to ensure isolation and prevent single-process GIL/thread locking issues. No threading is used to manage browser instances.

### Safe Concurrency Recommendations (Memory Estimates)

Based on 300–400MB RAM per `sb_cdp.Chrome` headed/headless browser and OS overhead:

- **8GB RAM Node:**
  - OS + Redis + Supervisor overhead: ~1.5GB
  - Available: ~6.5GB
  - Safe Concurrency: **10-12 Worker Processes**

- **16GB RAM Node:**
  - OS + Redis + Supervisor overhead: ~2GB
  - Available: ~14GB
  - Safe Concurrency: **25-30 Worker Processes**

- **32GB RAM Node:**
  - OS + overhead: ~3GB
  - Available: ~29GB
  - Safe Concurrency: **55-65 Worker Processes**

### Node Scaling

Horizontally scale by adding more worker nodes running the `worker.py` script. The Redis queue acts as the centralized coordinator, allowing any external process or API to enqueue items effortlessly. 
