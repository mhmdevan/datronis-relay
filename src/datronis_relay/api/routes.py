"""Route handlers for the dashboard REST API.

Every handler reads shared state from `request.app["config"]` and
`request.app["storage"]`. No global mutable state.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import UTC, datetime, timedelta

import structlog
from aiohttp import web

from datronis_relay import __version__
from datronis_relay.infrastructure.config import AppConfig
from datronis_relay.infrastructure.sqlite_storage import SQLiteStorage

log = structlog.get_logger(__name__)


def build_routes(app: web.Application) -> None:
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/config", handle_config_get)
    app.router.add_get("/api/users", handle_users_list)
    app.router.add_get("/api/adapters", handle_adapters_list)
    app.router.add_get("/api/tasks", handle_tasks_list)
    app.router.add_get("/api/cost/summary", handle_cost_summary)
    app.router.add_get("/api/cost/daily", handle_cost_daily)
    app.router.add_get("/api/cost/by-user", handle_cost_per_user)
    app.router.add_get("/api/audit", handle_audit_list)
    app.router.add_get("/api/monitoring/metrics", handle_monitoring_metrics)
    app.router.add_get("/api/monitoring/history", handle_monitoring_history)


def _config(request: web.Request) -> AppConfig:
    return request.app["config"]


def _storage(request: web.Request) -> SQLiteStorage:
    return request.app["storage"]


# -------------------------------------------------------------------- status


async def handle_status(request: web.Request) -> web.Response:
    config = _config(request)
    uptime = int(time.time() - request.app["start_time"])
    return web.json_response(
        {
            "version": __version__,
            "uptime_seconds": uptime,
            "adapters": {
                "telegram": config.telegram.enabled,
                "slack": config.slack.enabled,
            },
            "scheduler": config.scheduler.enabled,
        }
    )


# -------------------------------------------------------------------- config


async def handle_config_get(request: web.Request) -> web.Response:
    config = _config(request)
    return web.json_response(
        {
            "config": {
                "claude": {
                    "model": config.claude.model,
                    "max_turns": config.claude.max_turns,
                },
                "scheduler": {
                    "enabled": config.scheduler.enabled,
                    "poll_interval_seconds": int(config.scheduler.poll_interval_seconds),
                    "max_tasks_per_user": config.scheduler.max_tasks_per_user,
                },
                "metrics": {
                    "enabled": config.metrics.enabled,
                    "host": config.metrics.host,
                    "port": config.metrics.port,
                },
                "attachments": {
                    "enabled": config.attachments.enabled,
                    "max_file_size_bytes": config.attachments.max_bytes_per_file,
                },
                "logging": {
                    "level": config.logging.level,
                    "json_output": config.logging.json_output,
                },
            }
        }
    )


# --------------------------------------------------------------------- users


async def handle_users_list(request: web.Request) -> web.Response:
    config = _config(request)
    users = []
    for u in config.users:
        users.append(
            {
                "id": u.id,
                "display_name": u.display_name,
                "allowed_tools": u.allowed_tools,
                "rate_limit_per_minute": u.rate_limit.per_minute,
                "rate_limit_per_day": u.rate_limit.per_day,
                "last_active_at": None,
            }
        )
    return web.json_response({"users": users})


# ------------------------------------------------------------------ adapters


async def handle_adapters_list(request: web.Request) -> web.Response:
    config = _config(request)
    adapters = []
    if config.telegram.enabled:
        adapters.append(
            {
                "type": "telegram",
                "enabled": True,
                "token_set": bool(config.telegram.bot_token.get_secret_value()),
                "healthy": True,
                "last_error": None,
            }
        )
    else:
        adapters.append(
            {
                "type": "telegram",
                "enabled": False,
                "token_set": False,
                "healthy": False,
                "last_error": None,
            }
        )
    adapters.append(
        {
            "type": "slack",
            "enabled": config.slack.enabled,
            "token_set": bool(config.slack.bot_token.get_secret_value()),
            "healthy": config.slack.enabled,
            "last_error": None,
        }
    )
    return web.json_response({"adapters": adapters})


# --------------------------------------------------------------------- tasks


async def handle_tasks_list(request: web.Request) -> web.Response:
    storage = _storage(request)
    config = _config(request)
    all_tasks = []
    for user in config.users:
        tasks = await storage.list_scheduled_tasks(user.id)
        for t in tasks:
            all_tasks.append(
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "platform": t.platform.value,
                    "channel_ref": t.channel_ref,
                    "prompt": t.prompt,
                    "interval_seconds": t.interval_seconds,
                    "next_run_at": t.next_run_at.isoformat(),
                    "created_at": t.created_at.isoformat(),
                    "is_active": t.is_active,
                }
            )
    return web.json_response({"tasks": all_tasks})


# ---------------------------------------------------------------------- cost


async def handle_cost_summary(request: web.Request) -> web.Response:
    storage = _storage(request)
    config = _config(request)

    total_today = 0.0
    total_week = 0.0
    total_month = 0.0
    total_all = 0.0
    total_in = 0
    total_out = 0

    for user in config.users:
        s = await storage.summary(user.id)
        total_today += s.today_cost_usd
        total_week += s.week_cost_usd
        total_month += s.month_cost_usd
        total_all += s.total_cost_usd
        total_in += s.today_tokens_in
        total_out += s.today_tokens_out

    return web.json_response(
        {
            "summary": {
                "today": total_today,
                "week": total_week,
                "month": total_month,
                "total": total_all,
                "tokens_in": total_in,
                "tokens_out": total_out,
            }
        }
    )


async def handle_cost_daily(request: web.Request) -> web.Response:
    storage = _storage(request)
    days = int(request.query.get("days", "30"))
    db = storage._require_db()
    since = (datetime.now(UTC).date() - timedelta(days=days)).isoformat()

    async with db.execute(
        "SELECT day, SUM(tokens_in), SUM(tokens_out), SUM(cost_usd) "
        "FROM cost_ledger WHERE day >= ? GROUP BY day ORDER BY day ASC",
        (since,),
    ) as cur:
        rows = await cur.fetchall()

    daily = [
        {
            "day": str(r[0]),
            "tokens_in": int(r[1]),
            "tokens_out": int(r[2]),
            "cost_usd": float(r[3]),
        }
        for r in rows
    ]
    return web.json_response({"daily": daily})


async def handle_cost_per_user(request: web.Request) -> web.Response:
    storage = _storage(request)
    config = _config(request)
    db = storage._require_db()

    async with db.execute(
        "SELECT user_id, SUM(tokens_in), SUM(tokens_out), SUM(cost_usd) "
        "FROM cost_ledger GROUP BY user_id ORDER BY SUM(cost_usd) DESC",
    ) as cur:
        rows = await cur.fetchall()

    display_names = {u.id: u.display_name for u in config.users}
    result = [
        {
            "user_id": str(r[0]),
            "display_name": display_names.get(str(r[0])),
            "tokens_in": int(r[1]),
            "tokens_out": int(r[2]),
            "cost_usd": float(r[3]),
        }
        for r in rows
    ]
    return web.json_response({"rows": result})


# --------------------------------------------------------------------- audit


async def handle_audit_list(request: web.Request) -> web.Response:
    storage = _storage(request)
    db = storage._require_db()
    limit = int(request.query.get("limit", "50"))
    cursor = request.query.get("cursor")
    event_type = request.query.get("event_type")
    user_id = request.query.get("user_id")

    conditions = []
    params: list[object] = []

    if cursor:
        conditions.append("ts < ?")
        params.append(cursor)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit + 1)

    async with db.execute(
        f"SELECT ts, correlation_id, user_id, event_type, tool, command, "
        f"       exit_code, duration_ms, tokens_in, tokens_out, cost_usd, "
        f"       error_category "
        f"FROM audit_log {where} ORDER BY ts DESC LIMIT ?",
        tuple(params),
    ) as cur:
        rows = await cur.fetchall()

    entries = []
    for r in rows[:limit]:
        entries.append(
            {
                "ts": str(r[0]),
                "correlation_id": str(r[1]),
                "user_id": str(r[2]),
                "event_type": str(r[3]),
                "tool": r[4],
                "command": r[5],
                "exit_code": r[6],
                "duration_ms": r[7],
                "tokens_in": r[8],
                "tokens_out": r[9],
                "cost_usd": r[10],
                "error_category": r[11],
            }
        )

    next_cursor = str(rows[limit][0]) if len(rows) > limit else None
    return web.json_response({"entries": entries, "next_cursor": next_cursor})


# --------------------------------------------------------------- monitoring


async def handle_monitoring_metrics(request: web.Request) -> web.Response:
    metrics = await _collect_system_metrics()
    return web.json_response({"metrics": metrics})


async def handle_monitoring_history(request: web.Request) -> web.Response:
    # History requires a time-series store. Return empty for now —
    # the UI handles empty data gracefully with "No data" state.
    return web.json_response({"points": []})


async def _collect_system_metrics() -> dict:
    """Collect live system metrics via /proc and standard tools."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _collect_sync)


def _collect_sync() -> dict:
    """Synchronous system metric collection — runs in a thread."""
    cpu = _read_cpu()
    ram = _read_ram()
    swap = _read_swap()
    disk = _read_disk()
    os_info = _read_os_info()
    network = _read_network()
    docker = _read_docker()

    return {
        "cpu": cpu,
        "ram": ram,
        "swap": swap,
        "disk": disk,
        "os": os_info,
        "network": network,
        "docker": docker,
        "collected_at": datetime.now(UTC).isoformat(),
    }


def _read_cpu() -> dict:
    model = "Unknown"
    cores = 1
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                if line.startswith("processor"):
                    cores = int(line.split(":", 1)[1].strip()) + 1
    except (OSError, ValueError):
        pass

    usage = 0.0
    try:
        with open("/proc/stat") as f:
            line = f.readline()
            parts = line.split()
            if parts[0] == "cpu":
                idle = int(parts[4])
                total = sum(int(x) for x in parts[1:])
                usage = round((1 - idle / max(total, 1)) * 100, 1)
    except (OSError, ValueError, IndexError):
        pass

    load_avg = (0.0, 0.0, 0.0)
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            load_avg = (float(parts[0]), float(parts[1]), float(parts[2]))
    except (OSError, ValueError, IndexError):
        pass

    return {
        "model": model,
        "cores": cores,
        "usage_percent": usage,
        "load_avg": list(load_avg),
    }


def _read_ram() -> dict:
    info: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    info[key] = int(val) * 1024  # kB to bytes
    except (OSError, ValueError):
        pass

    total = info.get("MemTotal", 0)
    free = info.get("MemFree", 0)
    available = info.get("MemAvailable", total)
    buffers = info.get("Buffers", 0)
    cached = info.get("Cached", 0)
    used = total - free - buffers - cached
    usage = round(used / max(total, 1) * 100, 1)

    return {
        "total_bytes": total,
        "used_bytes": max(used, 0),
        "free_bytes": free,
        "available_bytes": available,
        "buff_cache_bytes": buffers + cached,
        "usage_percent": usage,
    }


def _read_swap() -> dict:
    total = 0
    free = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("SwapTotal:"):
                    total = int(line.split()[1]) * 1024
                elif line.startswith("SwapFree:"):
                    free = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass

    used = total - free
    usage = round(used / max(total, 1) * 100, 1) if total > 0 else 0.0
    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "usage_percent": usage,
    }


def _read_disk() -> list[dict]:
    disks = []
    try:
        result = subprocess.run(
            ["df", "-B1", "--output=source,target,size,used,avail,pcent"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            fs = parts[0]
            # Skip virtual filesystems
            if fs.startswith(("tmpfs", "devtmpfs", "overlay", "shm", "udev", "none")):
                continue
            mount = parts[1]
            total = int(parts[2])
            used = int(parts[3])
            avail = int(parts[4])
            pct = float(parts[5].rstrip("%"))
            if total == 0:
                continue
            disks.append(
                {
                    "filesystem": fs,
                    "mount": mount,
                    "total_bytes": total,
                    "used_bytes": used,
                    "available_bytes": avail,
                    "usage_percent": pct,
                }
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return disks


def _read_os_info() -> dict:
    name = "Unknown"
    kernel = "Unknown"
    hostname = "Unknown"
    uptime_seconds = 0
    users_online = 0

    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    name = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass

    try:
        result = subprocess.run(["uname", "-r"], capture_output=True, text=True, timeout=5)
        kernel = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    try:
        result = subprocess.run(["hostname"], capture_output=True, text=True, timeout=5)
        hostname = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    try:
        with open("/proc/uptime") as f:
            uptime_seconds = int(float(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    try:
        result = subprocess.run(["who"], capture_output=True, text=True, timeout=5)
        users_online = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return {
        "name": name,
        "kernel": kernel,
        "hostname": hostname,
        "uptime_seconds": uptime_seconds,
        "users_online": users_online,
    }


def _read_network() -> list[dict]:
    interfaces = []
    try:
        result = subprocess.run(
            ["ip", "-j", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        import json

        data = json.loads(result.stdout)
        for iface in data:
            name = iface.get("ifname", "")
            state = iface.get("operstate", "UNKNOWN").lower()
            status = "up" if state == "up" else "down" if state == "down" else "unknown"
            ipv4 = None
            ipv6 = None
            for addr_info in iface.get("addr_info", []):
                if addr_info.get("family") == "inet" and not ipv4:
                    ipv4 = addr_info.get("local")
                elif addr_info.get("family") == "inet6" and not ipv6:
                    ipv6 = addr_info.get("local")
            interfaces.append(
                {"name": name, "status": status, "ipv4": ipv4, "ipv6": ipv6}
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        pass
    return interfaces


def _read_docker() -> dict | None:
    try:
        result = subprocess.run(
            ["docker", "ps", "-q"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        containers = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
        return {"running": True, "containers": containers}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
