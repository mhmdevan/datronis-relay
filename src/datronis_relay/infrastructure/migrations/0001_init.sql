-- Phase 2 initial schema.

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    display_name  TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    started_at    TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_status
    ON sessions(user_id, status);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    correlation_id  TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    tool            TEXT,
    command         TEXT,
    exit_code       INTEGER,
    duration_ms     INTEGER,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    cost_usd        REAL,
    error_category  TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user_ts
    ON audit_log(user_id, ts);

CREATE TABLE IF NOT EXISTS cost_ledger (
    day         TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    cost_usd    REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (day, user_id)
);

CREATE INDEX IF NOT EXISTS idx_cost_ledger_user_day
    ON cost_ledger(user_id, day);
