-- Phase 4: scheduled tasks.

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT    NOT NULL REFERENCES users(id),
    platform          TEXT    NOT NULL,                   -- 'telegram' | 'slack' | ...
    channel_ref       TEXT    NOT NULL,                   -- platform-specific reply ref
    prompt            TEXT    NOT NULL,
    interval_seconds  INTEGER NOT NULL,
    next_run_at       TEXT    NOT NULL,
    created_at        TEXT    NOT NULL,
    is_active         INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_claim
    ON scheduled_tasks(is_active, next_run_at);

CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user
    ON scheduled_tasks(user_id);
