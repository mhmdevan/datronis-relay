from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite
import structlog

from datronis_relay.core.ports import (
    AuditStoreProtocol,
    CostStoreProtocol,
    ScheduledTaskStoreProtocol,
    SessionStoreProtocol,
)
from datronis_relay.domain.audit import AuditEntry
from datronis_relay.domain.cost import CostSummary
from datronis_relay.domain.ids import SessionId, UserId
from datronis_relay.domain.messages import Platform
from datronis_relay.domain.scheduled_task import ScheduledTask

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class SQLiteStorage(
    SessionStoreProtocol,
    AuditStoreProtocol,
    CostStoreProtocol,
    ScheduledTaskStoreProtocol,
):
    """Single-file SQLite storage implementing Session + Audit + Cost ports.

    Design choices:
      - One long-lived `aiosqlite.Connection` for the process; aiosqlite
        serializes writes internally over its background thread.
      - WAL journal mode for concurrent readers and crash safety.
      - Foreign keys ON.
      - Migrations applied on `open()` via the `schema_version` table.
      - `set()` closes any prior active session for the user before inserting
        the new one, so there is at most one active session per user.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.commit()
        await self._run_migrations()
        log.info("sqlite.storage.opened", path=self._path)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
            log.info("sqlite.storage.closed")

    async def _run_migrations(self) -> None:
        db = self._require_db()
        await db.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        async with db.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_version"
        ) as cur:
            row = await cur.fetchone()
            current: int = int(row[0]) if row is not None else 0

        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for path in files:
            version = int(path.stem.split("_", 1)[0])
            if version <= current:
                continue
            sql = path.read_text()
            await db.executescript(sql)
            await db.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            await db.commit()
            log.info("sqlite.migration.applied", version=version, file=path.name)

    # ----------------------------------------------------------------- sessions

    async def get(self, user_id: UserId) -> SessionId | None:
        db = self._require_db()
        async with db.execute(
            "SELECT id FROM sessions "
            "WHERE user_id = ? AND status = 'active' "
            "ORDER BY last_seen_at DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        await self._touch_session(str(row[0]))
        return SessionId(str(row[0]))

    async def set(self, user_id: UserId, session_id: SessionId) -> None:
        db = self._require_db()
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "INSERT INTO users (id, display_name, is_active, created_at) "
            "VALUES (?, NULL, 1, ?) ON CONFLICT(id) DO NOTHING",
            (user_id, now),
        )
        await db.execute(
            "UPDATE sessions SET status = 'closed' "
            "WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        await db.execute(
            "INSERT INTO sessions (id, user_id, started_at, last_seen_at, status) "
            "VALUES (?, ?, ?, ?, 'active')",
            (session_id, user_id, now, now),
        )
        await db.commit()

    async def drop(self, user_id: UserId) -> None:
        db = self._require_db()
        await db.execute(
            "UPDATE sessions SET status = 'closed' "
            "WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        await db.commit()

    async def _touch_session(self, session_id: str) -> None:
        db = self._require_db()
        await db.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), session_id),
        )
        await db.commit()

    # -------------------------------------------------------------------- audit

    async def record(self, entry: AuditEntry) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT INTO audit_log ("
            " ts, correlation_id, user_id, event_type, tool, command,"
            " exit_code, duration_ms, tokens_in, tokens_out, cost_usd, error_category"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.ts.isoformat(),
                entry.correlation_id,
                entry.user_id,
                entry.event_type.value,
                entry.tool,
                entry.command,
                entry.exit_code,
                entry.duration_ms,
                entry.tokens_in,
                entry.tokens_out,
                entry.cost_usd,
                entry.error_category,
            ),
        )
        await db.commit()

    # --------------------------------------------------------------------- cost

    async def record_usage(
        self,
        user_id: UserId,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        db = self._require_db()
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        await db.execute(
            "INSERT INTO cost_ledger (day, user_id, tokens_in, tokens_out, cost_usd) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(day, user_id) DO UPDATE SET "
            " tokens_in  = tokens_in  + excluded.tokens_in, "
            " tokens_out = tokens_out + excluded.tokens_out, "
            " cost_usd   = cost_usd   + excluded.cost_usd",
            (day, user_id, tokens_in, tokens_out, cost_usd),
        )
        await db.commit()

    async def summary(self, user_id: UserId) -> CostSummary:
        db = self._require_db()
        today = datetime.now(UTC).date()
        week_start = (today - timedelta(days=7)).isoformat()
        month_start = (today - timedelta(days=30)).isoformat()
        today_str = today.isoformat()

        async with db.execute(
            "SELECT COALESCE(tokens_in, 0), COALESCE(tokens_out, 0), "
            "       COALESCE(cost_usd, 0) "
            "FROM cost_ledger WHERE user_id = ? AND day = ?",
            (user_id, today_str),
        ) as cur:
            row = await cur.fetchone()
        if row is not None:
            today_in = int(row[0])
            today_out = int(row[1])
            today_cost = float(row[2])
        else:
            today_in = 0
            today_out = 0
            today_cost = 0.0

        week_cost = await self._sum_cost(user_id, week_start)
        month_cost = await self._sum_cost(user_id, month_start)
        total_cost = await self._sum_cost(user_id, None)

        return CostSummary(
            today_tokens_in=today_in,
            today_tokens_out=today_out,
            today_cost_usd=today_cost,
            week_cost_usd=week_cost,
            month_cost_usd=month_cost,
            total_cost_usd=total_cost,
        )

    async def _sum_cost(self, user_id: UserId, since_day: str | None) -> float:
        db = self._require_db()
        if since_day is None:
            query = "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_ledger WHERE user_id = ?"
            params: tuple[object, ...] = (user_id,)
        else:
            query = (
                "SELECT COALESCE(SUM(cost_usd), 0) FROM cost_ledger "
                "WHERE user_id = ? AND day >= ?"
            )
            params = (user_id, since_day)
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
        return float(row[0]) if row is not None else 0.0

    # ---------------------------------------------------------- scheduled tasks

    async def create_scheduled_task(
        self,
        user_id: UserId,
        platform: Platform,
        channel_ref: str,
        prompt: str,
        interval_seconds: int,
    ) -> ScheduledTask:
        db = self._require_db()
        now = datetime.now(UTC)
        next_run = now + timedelta(seconds=interval_seconds)
        # Make sure the user row exists (SQLiteStorage usually lazily
        # creates it on the first session, but /schedule can arrive first).
        await db.execute(
            "INSERT INTO users (id, display_name, is_active, created_at) "
            "VALUES (?, NULL, 1, ?) ON CONFLICT(id) DO NOTHING",
            (user_id, now.isoformat()),
        )
        cur = await db.execute(
            "INSERT INTO scheduled_tasks ("
            " user_id, platform, channel_ref, prompt,"
            " interval_seconds, next_run_at, created_at, is_active"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (
                user_id,
                platform.value,
                channel_ref,
                prompt,
                interval_seconds,
                next_run.isoformat(),
                now.isoformat(),
            ),
        )
        await db.commit()
        task_id = cur.lastrowid
        assert task_id is not None
        return ScheduledTask(
            id=task_id,
            user_id=user_id,
            platform=platform,
            channel_ref=channel_ref,
            prompt=prompt,
            interval_seconds=interval_seconds,
            next_run_at=next_run,
            created_at=now,
            is_active=True,
        )

    async def list_scheduled_tasks(
        self, user_id: UserId
    ) -> list[ScheduledTask]:
        db = self._require_db()
        async with db.execute(
            "SELECT id, user_id, platform, channel_ref, prompt, "
            "       interval_seconds, next_run_at, created_at, is_active "
            "FROM scheduled_tasks "
            "WHERE user_id = ? AND is_active = 1 "
            "ORDER BY id ASC",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_scheduled_task(row) for row in rows]

    async def delete_scheduled_task(
        self, user_id: UserId, task_id: int
    ) -> bool:
        db = self._require_db()
        cur = await db.execute(
            "UPDATE scheduled_tasks SET is_active = 0 "
            "WHERE id = ? AND user_id = ? AND is_active = 1",
            (task_id, user_id),
        )
        await db.commit()
        return cur.rowcount > 0

    async def count_scheduled_tasks(self, user_id: UserId) -> int:
        db = self._require_db()
        async with db.execute(
            "SELECT COUNT(*) FROM scheduled_tasks "
            "WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row is not None else 0

    async def claim_due_tasks(
        self, now: datetime, limit: int = 10
    ) -> list[ScheduledTask]:
        """Atomically select up to `limit` due tasks and advance their
        `next_run_at` so the next tick can't fire them again."""
        db = self._require_db()
        now_iso = now.isoformat()
        async with db.execute(
            "SELECT id, user_id, platform, channel_ref, prompt, "
            "       interval_seconds, next_run_at, created_at, is_active "
            "FROM scheduled_tasks "
            "WHERE is_active = 1 AND next_run_at <= ? "
            "ORDER BY next_run_at ASC "
            "LIMIT ?",
            (now_iso, limit),
        ) as cur:
            rows = await cur.fetchall()

        tasks: list[ScheduledTask] = [_row_to_scheduled_task(row) for row in rows]
        for task in tasks:
            next_run = now + timedelta(seconds=task.interval_seconds)
            await db.execute(
                "UPDATE scheduled_tasks SET next_run_at = ? WHERE id = ?",
                (next_run.isoformat(), task.id),
            )
        await db.commit()
        return tasks

    # -------------------------------------------------------------------- helpers

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SQLiteStorage not opened — call .open() first")
        return self._db


def _row_to_scheduled_task(row: tuple) -> ScheduledTask:  # type: ignore[type-arg]
    return ScheduledTask(
        id=int(row[0]),
        user_id=UserId(str(row[1])),
        platform=Platform(str(row[2])),
        channel_ref=str(row[3]),
        prompt=str(row[4]),
        interval_seconds=int(row[5]),
        next_run_at=datetime.fromisoformat(str(row[6])),
        created_at=datetime.fromisoformat(str(row[7])),
        is_active=bool(row[8]),
    )
