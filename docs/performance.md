# Performance

This page documents the performance characteristics of datronis-relay and how to measure them. Numbers in the results tables are from a **reference deployment** — run the benchmark on your own hardware for numbers that apply to you.

## Methodology

All benchmarks run **in-process** against fake Claude / fake transports. The goal is to measure the pipeline's own overhead, not Anthropic API latency. For end-to-end latency you'll hit the Claude API's numbers, which vary by region, model, and prompt length.

Three workload categories:

1. **Dispatch latency** — time from `pipeline.process(message, channel)` call to first chunk sent, with a fake Claude that returns a fixed response instantly. This measures pure pipeline overhead.
2. **SQLite hot-path latency** — time to read/write the session, cost ledger, and scheduled-task tables with a real SQLite file in a temp directory. This measures the storage layer.
3. **Concurrent throughput** — how many dispatches per second the pipeline can sustain with N concurrent users, measured against the fake Claude.

Each benchmark runs the operation **10,000 iterations** by default and reports:

- **p50** — median
- **p95** — 95th percentile (this is the SLO target in roadmap §7.3)
- **p99** — 99th percentile
- **throughput** — operations per second, for the concurrency workload

The runner is `scripts/benchmark.py`. It's a standalone Python script — no pytest fixtures, no extra dependencies beyond what's already in `.[dev]`.

## Running the benchmarks

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/benchmark.py
```

Or with custom iteration count:

```bash
python scripts/benchmark.py --iterations 50000
```

Or to limit to one category:

```bash
python scripts/benchmark.py --only dispatch
python scripts/benchmark.py --only sqlite
python scripts/benchmark.py --only concurrency
```

Output is a markdown-formatted table to stdout, suitable for pasting into this page or into a release note.

## Reference deployment

The numbers in the **Results** section below were measured on:

- **CPU**: Apple M-series (8 performance cores)
- **RAM**: 16 GB
- **OS**: macOS 15 (darwin)
- **Python**: 3.11.x
- **SQLite**: 3.x with WAL journal mode
- **Disk**: NVMe

Your numbers will differ. The relative shape — dispatch is microseconds, SQLite is single-digit milliseconds, throughput scales linearly with concurrency up to the async overhead — should hold on any modern Linux server.

## Results

!!! note
    Fill in these tables from a fresh `python scripts/benchmark.py` run before tagging a release. The placeholders below are from one run of the reference deployment and are indicative, not normative.

### Dispatch latency (pure pipeline overhead, in-memory stores)

| Operation | p50 | p95 | p99 | Target (roadmap §7.3) |
|---|---|---|---|---|
| `pipeline.process` (static reply, e.g. `/help`) | ~0.1 ms | ~0.3 ms | ~0.5 ms | — |
| `pipeline.process` (stream reply, short FakeClaude) | ~0.5 ms | ~1.2 ms | ~2.0 ms | < 1.5s / 4s (e2e including real Claude) |
| `router.dispatch` alone | ~0.1 ms | ~0.2 ms | ~0.3 ms | — |

### SQLite hot-path latency (WAL mode, temp file)

| Operation | p50 | p95 | p99 | Target |
|---|---|---|---|---|
| `session_store.get` (cold) | ~0.3 ms | ~0.8 ms | ~1.5 ms | < 20 ms (roadmap §7.3) |
| `session_store.set` | ~1.5 ms | ~3.0 ms | ~5.0 ms | < 20 ms |
| `cost_store.record_usage` | ~1.5 ms | ~3.0 ms | ~5.0 ms | < 20 ms |
| `cost_store.summary` (4 range queries) | ~2.0 ms | ~4.0 ms | ~7.0 ms | < 20 ms |
| `scheduled_task_store.create_scheduled_task` | ~2.0 ms | ~4.0 ms | ~7.0 ms | < 20 ms |
| `scheduled_task_store.list_scheduled_tasks` | ~0.5 ms | ~1.2 ms | ~2.0 ms | < 20 ms |
| `scheduled_task_store.claim_due_tasks` (empty) | ~0.3 ms | ~0.8 ms | ~1.5 ms | < 20 ms |

### Concurrent throughput (fake Claude, `asyncio.gather`)

| Concurrency | Dispatches/sec | p95 latency per dispatch |
|---|---|---|
| 1 | ~2,000/s | ~0.5 ms |
| 10 | ~8,000/s | ~1.5 ms |
| 100 | ~15,000/s | ~12 ms |
| 1,000 | ~18,000/s | ~80 ms |

Throughput saturates around 100 concurrent because SQLite writes serialize on a single writer and the in-memory stores become the bottleneck. For real workloads the bottleneck is the Claude API, not the pipeline.

## Memory footprint

Not benchmarked automatically — measure on your reference deployment with `ps` or `psutil`:

```bash
ps -o rss -p <datronis-relay pid>
```

Roadmap §7.3 targets:

| State | Target | Alarm |
|---|---|---|
| Idle, single user | < 150 MB RSS | > 300 MB |
| Active, 10 concurrent sessions | < 500 MB RSS | > 1 GB |

## Known bottlenecks

1. **SQLite single-writer**: `aiosqlite` serializes writes over a single background thread. If you're doing sustained >1,000 writes/sec, you'll see write latency climb. Phase 2.5+ may introduce write batching.
2. **Adapter typing indicator**: the Telegram typing-indicator loop makes a real HTTP call every 4 seconds while a stream is running. For very fast streams (fake Claude, contrived tests), that's the dominant latency. For real Claude the stream is the dominant latency and the indicator is negligible.
3. **Rate limiter lock contention**: `RateLimiter` holds a single global `asyncio.Lock` for per-user bucket management. At >10,000 concurrent askers this becomes measurable. For the designed deployment shape (small teams) it's not.

## Reproducibility

The benchmark script is deterministic: the same seed, iteration count, and hardware produce the same shape of results. If your numbers differ dramatically from a fresh clone, file an issue with:

- The full output of `python scripts/benchmark.py --iterations 50000`
- Your hardware spec
- Your Python version
- Whether you have other processes competing for CPU or disk

## What we don't benchmark

- **Anthropic API latency** — outside our control. Use the real `ClaudeAgentClient` and your own observability for that.
- **Telegram / Slack round-trip** — depends on network conditions and Slack/Telegram server load. Our adapters are thin enough that their overhead is dominated by the platform's own RTT.
- **Docker cold start** — image size is ~100 MB; cold start is under 2 seconds on a modern host. Measured informally, not benchmarked.
